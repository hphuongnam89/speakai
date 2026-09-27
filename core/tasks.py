import json
import os
from urllib.request import Request, urlopen

from celery import shared_task
from django.core.files.storage import default_storage
from django.utils import timezone

from core.models import PracticeAttempt


def _text_items(value, limit, max_items):
    if isinstance(value, str):
        return [value.strip()[:limit]] if value.strip() else []
    if not isinstance(value, list):
        return []
    return [item.strip()[:limit] for item in value if isinstance(item, str) and item.strip()][:max_items]


def _ollama_score(*, attempt, transcripts):
    endpoint = os.getenv("LOCAL_AI_BASE_URL", "http://host.docker.internal:11434").rstrip("/") + "/api/chat"
    model = os.getenv("LOCAL_AI_MODEL", "ornith-1.5:9b")
    payload = {
        "model": model, "stream": False, "think": False, "format": "json",
        "messages": [
            {"role": "system", "content": (
                "You are an English speaking practice assessor. Return only valid JSON. "
                "Use a 0-100 practice scale and assess each question separately. For every question return "
                "question_index, score, strengths (array), weaknesses (array), feedback, and criteria. "
                "criteria must contain task_achievement, fluency, grammar, vocabulary, coherence and pronunciation. "
                "Each criterion has score (0-100 or null), strengths, weaknesses, evidence and status. "
                "Pronunciation must be null with status not_assessed because transcript text alone cannot prove pronunciation. "
                "Use concrete evidence from the transcript, not generic encouragement. Write feedback in Vietnamese. "
                "This is practice feedback, not an official grade."
            )},
            {"role": "user", "content": json.dumps({
                "level": attempt.cefr_level, "topic": attempt.topic,
                "questions": attempt.questions, "transcripts": transcripts,
                "rubric": [
                    {"key": "task_achievement", "weight": 15}, {"key": "pronunciation", "weight": 20},
                    {"key": "fluency", "weight": 20}, {"key": "grammar", "weight": 20},
                    {"key": "vocabulary", "weight": 15}, {"key": "coherence", "weight": 10},
                ],
                "shape": {"score": 0, "feedback": "", "per_question": [{"question_index": 1, "score": 0, "strengths": [], "weaknesses": [], "feedback": "", "criteria": []}]},
            }, ensure_ascii=False)},
        ],
    }
    # Score each speaking part independently below. A single large JSON response
    # is intentionally avoided because local models often drop nested rubric data.
    parsed = {"score": 0, "feedback": ""}
    score = float(parsed["score"])
    if not 0 <= score <= 100:
        raise ValueError("AI score outside 0-100")
    raw_questions = parsed.get("per_question")
    if not isinstance(raw_questions, list) or len(raw_questions) != len(transcripts):
        raw_questions = []
        for question, transcript in zip(attempt.questions, transcripts):
            question_payload = {
                "model": model, "stream": False, "think": False, "format": "json",
                "messages": [
                    {"role": "system", "content": (
                        "Đánh giá đúng một câu trả lời nói tiếng Anh. Chỉ trả JSON với question_index, score (0-100), "
                        "strengths, weaknesses, feedback và criteria. criteria gồm task_achievement, fluency, grammar, "
                        "vocabulary, coherence, pronunciation; mỗi tiêu chí có score (0-100 hoặc null), status, "
                        "strengths, weaknesses, evidence. pronunciation phải score null/status not_assessed vì transcript "
                        "không đủ bằng chứng. Nhận xét bằng tiếng Việt, nêu bằng chứng cụ thể, không nhận xét chung chung."
                    )},
                    {"role": "user", "content": json.dumps({"question": question, "transcript": transcript}, ensure_ascii=False)},
                ],
            }
            question_request = Request(endpoint, data=json.dumps(question_payload).encode(), headers={"Content-Type": "application/json"})
            with urlopen(question_request, timeout=int(os.getenv("LOCAL_AI_TIMEOUT_SECONDS", "150"))) as question_response:
                question_result = json.loads(question_response.read().decode())
            raw_questions.append(json.loads(question_result["message"]["content"]))
    per_question = []
    for position, raw in enumerate(raw_questions, start=1):
        if not isinstance(raw, dict):
            raise ValueError("AI returned an invalid question review")
        question_score = float(raw.get("score", 0))
        if not 0 <= question_score <= 100:
            raise ValueError("Question score outside 0-100")
        criteria = []
        raw_criteria = raw.get("criteria") or []
        if isinstance(raw_criteria, dict):
            raw_criteria = [dict(value, key=key) if isinstance(value, dict) else {"key": key, "score": value} for key, value in raw_criteria.items()]
        labels = {
            "task_achievement": "Đáp ứng yêu cầu",
            "pronunciation": "Phát âm",
            "fluency": "Độ trôi chảy",
            "grammar": "Ngữ pháp",
            "vocabulary": "Từ vựng",
            "coherence": "Mạch lạc",
        }
        for item in raw_criteria:
            if not isinstance(item, dict) or not item.get("key"):
                continue
            criterion_score = item.get("score")
            if criterion_score is not None:
                criterion_score = float(criterion_score)
                if not 0 <= criterion_score <= 100:
                    raise ValueError("Criterion score outside 0-100")
            key = str(item["key"])[:64]
            criteria.append({
                "key": key, "label": labels.get(key, key), "score": criterion_score,
                "status": str(item.get("status", "assessed"))[:32],
                "strengths": _text_items(item.get("strengths"), 300, 3),
                "weaknesses": _text_items(item.get("weaknesses"), 300, 3),
                "evidence": str(item.get("evidence") or "")[:500],
            })
        per_question.append({
            "question_index": position, "score": round(question_score, 2),
            "strengths": _text_items(raw.get("strengths"), 300, 4),
            "weaknesses": _text_items(raw.get("weaknesses"), 300, 4),
            "feedback": "; ".join(raw.get("feedback", [])) if isinstance(raw.get("feedback"), list) else str(raw.get("feedback", ""))[:1200], "criteria": criteria,
        })
    score = round(sum(item["score"] for item in per_question) / len(per_question), 2)
    return {"score": score, "feedback": str(parsed.get("feedback", ""))[:4000], "per_question": per_question}


@shared_task(bind=True, autoretry_for=(), max_retries=0)
def score_practice_attempt(self, attempt_id):
    try:
        attempt = PracticeAttempt.objects.prefetch_related("answers").get(pk=attempt_id)
    except PracticeAttempt.DoesNotExist:
        return
    if attempt.status != PracticeAttempt.Status.SUBMITTED:
        return
    try:
        from faster_whisper import WhisperModel
        whisper = WhisperModel(os.getenv("WHISPER_MODEL", "small"), device=os.getenv("WHISPER_DEVICE", "cpu"), compute_type=os.getenv("WHISPER_COMPUTE_TYPE", "int8"))
        transcripts = []
        for answer in attempt.answers.all():
            path = default_storage.path(answer.audio.name)
            segments, info = whisper.transcribe(path, language="en", vad_filter=True)
            transcripts.append({"question_index": answer.question_index, "text": " ".join(segment.text.strip() for segment in segments), "language": info.language})
        result = _ollama_score(attempt=attempt, transcripts=transcripts)
        attempt.ai_score = result["score"]
        attempt.ai_result = {"transcripts": transcripts, "feedback": result["feedback"], "per_question": result["per_question"]}
        attempt.ai_scored_at = timezone.now()
        attempt.scoring_status = PracticeAttempt.ScoringStatus.AI_DRAFT
        attempt.scoring_error = ""
        attempt.save(update_fields=("ai_score", "ai_result", "ai_scored_at", "scoring_status", "scoring_error"))
    except Exception as exc:
        attempt.scoring_status = PracticeAttempt.ScoringStatus.FAILED
        attempt.scoring_error = f"{type(exc).__name__}: {str(exc)[:500]}"
        attempt.save(update_fields=("scoring_status", "scoring_error"))
