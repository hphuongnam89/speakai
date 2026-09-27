from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ValidationError

from core.models import ExamAttempt


def _band_score(band):
    if isinstance(band, bool) or not isinstance(band, int) or not 0 <= band <= 4:
        raise ValidationError("Band rubric phải là số nguyên từ 0 đến 4.")
    return Decimal(band) / Decimal(4) * Decimal(100)


def score_official_attempt(*, attempt, answers_payload, actor, reason):
    if attempt.status != ExamAttempt.Status.SUBMITTED:
        raise ValidationError("Chỉ được chấm lượt thi đã nộp.")
    if attempt.scoring_status == ExamAttempt.ScoringStatus.FINAL:
        raise ValidationError("Lượt thi đã có điểm final; hãy tạo quyết định hiệu chỉnh riêng.")
    if not reason or not reason.strip():
        raise ValidationError("Mọi quyết định điểm phải có lý do.")
    if not isinstance(answers_payload, list):
        raise ValidationError("Payload điểm phải là danh sách câu trả lời.")

    expected = {item["question_index"]: item for item in attempt.questions_snapshot}
    supplied = {item.get("question_index"): item for item in answers_payload if isinstance(item, dict)}
    if set(supplied) != set(expected):
        raise ValidationError("Payload phải có đúng tất cả câu trong snapshot đề.")

    question_results, task_points = [], Decimal("0")
    for question_index, question in expected.items():
        payload = supplied[question_index]
        rubric = question["rubric_snapshot"]
        criteria = rubric.get("criteria") or []
        submitted = payload.get("criteria")
        if not isinstance(submitted, list):
            raise ValidationError(f"Câu {question_index}: criteria phải là danh sách.")
        by_name = {item.get("name"): item for item in submitted if isinstance(item, dict)}
        expected_names = {criterion["name"] for criterion in criteria}
        if set(by_name) != expected_names:
            raise ValidationError(f"Câu {question_index}: phải có đúng các criterion trong rubric snapshot.")
        criterion_results = []
        unscorable = False
        weighted = Decimal("0")
        for criterion in criteria:
            item = by_name.get(criterion["name"])
            if not item or item.get("status") == "unscorable" or item.get("band") is None:
                unscorable = True
                criterion_results.append({"name": criterion["name"], "status": "unscorable", "band": None, "evidence": (item or {}).get("evidence", "")})
                continue
            band = item["band"]
            score = _band_score(band)
            weight = Decimal(str(criterion["weight"]))
            weighted += score * weight / Decimal(100)
            criterion_results.append({"name": criterion["name"], "status": "scored", "band": band, "score": str(score), "weight": str(weight), "evidence": str(item.get("evidence") or "")[:1000]})
        task_max = Decimal(str(question.get("task_max_points", "0")))
        question_score = None if unscorable else (weighted / Decimal(100) * task_max)
        if question_score is not None:
            task_points += question_score
        question_results.append({"question_index": question_index, "status": "unscorable" if unscorable else "scored", "score": str(question_score) if question_score is not None else None, "task_max_points": str(task_max), "criteria": criterion_results})

    result = {"status": "needs_review" if any(item["status"] == "unscorable" for item in question_results) else "scored", "score": str(task_points.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)) if all(item["status"] == "scored" for item in question_results) else None, "questions": question_results}
    attempt.scoring_result = result
    attempt.ai_score = None
    attempt.final_score = task_points.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) if result["status"] == "scored" else None
    attempt.passed = None if attempt.final_score is None or attempt.threshold is None else attempt.final_score >= attempt.threshold
    attempt.final_feedback = "" if result["status"] == "scored" else "Bài có câu thiếu bằng chứng và cần rà soát; không ép điểm 0."
    attempt.scoring_status = ExamAttempt.ScoringStatus.FINAL if result["status"] == "scored" else ExamAttempt.ScoringStatus.NEEDS_REVIEW
    attempt.reviewed_by = actor
    from django.utils import timezone
    attempt.reviewed_at = timezone.now()
    attempt.save(update_fields=("scoring_result", "ai_score", "final_score", "passed", "final_feedback", "scoring_status", "reviewed_by", "reviewed_at"))
    return result
