from decimal import Decimal

from django.core.exceptions import ValidationError


GT1_EXPECTED = {
    "A": {"count": 1, "task_type": "self_introduction", "max_points": Decimal("2"), "prep": 15, "response": 45},
    "B": {"count": 4, "task_type": "short_qa", "max_points": Decimal("4"), "prep": 10, "response": 40},
    "C1": {"count": 1, "task_type": "picture_description", "max_points": Decimal("2"), "prep": 60, "response": 60},
    "C2": {"count": 2, "task_type": "picture_follow_up", "max_points": Decimal("2"), "prep": 10, "response": 30},
}
PRONUNCIATION_EXPECTED = {
    "Đọc từ": {"count": 10, "max_points": Decimal("3")},
    "Đọc câu": {"count": 10, "max_points": Decimal("3")},
    "Đọc đoạn": {"count": 2, "max_points": Decimal("4")},
}


def _rules(slot):
    return slot.selection_rules if isinstance(slot.selection_rules, dict) else {}


def _count(slots, name):
    return sum(slot.question_count for slot in slots if slot.section_name == name)


def _check_rubric_weights(slot, expected_names):
    criteria = list(slot.rubric_version.criteria.all())
    names = {criterion.name for criterion in criteria}
    if names != set(expected_names):
        raise ValidationError(f"Slot '{slot.section_name}' cần đúng các criterion: {', '.join(expected_names)}.")
    weights = {criterion.name: Decimal(str(criterion.weight)) for criterion in criteria}
    if sum(weights.values(), Decimal("0")) != Decimal("100"):
        raise ValidationError(f"Rubric slot '{slot.section_name}' phải có tổng weight 100.")
    for criterion in criteria:
        levels = {descriptor.level for descriptor in criterion.descriptors.all() if descriptor.text.strip()}
        if levels != {"0", "1", "2", "3", "4"}:
            raise ValidationError(f"Rubric slot '{slot.section_name}' thiếu descriptor band 0–4.")
    return weights


def _check_timing(slot, expected, section):
    if slot.question_count != expected["count"]:
        raise ValidationError(f"GT1 {section} phải có {expected['count']} câu/thẻ, hiện có {slot.question_count}.")
    if expected.get("task_type") and slot.task_type != expected["task_type"]:
        raise ValidationError(f"GT1 {section} cần task_type '{expected['task_type']}'.")
    if Decimal(str(slot.max_points)) != expected["max_points"]:
        raise ValidationError(f"GT1 {section} phải có {expected['max_points']} điểm tối đa.")
    if slot.prep_seconds != expected["prep"] or slot.response_seconds != expected["response"]:
        raise ValidationError(f"GT1 {section} cần thời lượng chuẩn bị/trả lời {expected['prep']}/{expected['response']} giây.")


def validate_gt1(slots):
    by_name = {slot.section_name: slot for slot in slots}
    if set(by_name) != set(GT1_EXPECTED):
        raise ValidationError("Blueprint GT1 phải có đúng bốn phần A, B, C1 và C2.")
    for section, expected in GT1_EXPECTED.items():
        _check_timing(by_name[section], expected, section)
    _check_rubric_weights(by_name["A"], ("pronunciation", "fluency", "grammar", "vocabulary", "task_achievement"))
    _check_rubric_weights(by_name["B"], ("pronunciation", "fluency", "grammar", "vocabulary", "task_achievement"))
    _check_rubric_weights(by_name["C1"], ("pronunciation", "fluency", "grammar", "vocabulary", "organization", "task_achievement"))
    _check_rubric_weights(by_name["C2"], ("pronunciation", "fluency", "grammar", "vocabulary", "task_achievement"))
    b_rules = _rules(by_name["B"])
    topics = b_rules.get("topics")
    if not isinstance(topics, list) or len(topics) != 2 or len(set(topics)) != 2:
        raise ValidationError("GT1 B phải khai báo đúng hai topic khác nhau.")
    if b_rules.get("topic_distribution") != [2, 2]:
        raise ValidationError("GT1 B phải phân bổ 2 câu cho mỗi topic.")
    for section in ("C1", "C2"):
        if _rules(by_name[section]).get("content_family") != "picture":
            raise ValidationError(f"GT1 {section} phải có content_family='picture'.")


def validate_pronunciation(slots):
    by_name = {slot.section_name: slot for slot in slots}
    if set(by_name) != set(PRONUNCIATION_EXPECTED):
        raise ValidationError("Blueprint Ngữ âm phải có đúng các phần Đọc từ, Đọc câu và Đọc đoạn.")
    for section, expected in PRONUNCIATION_EXPECTED.items():
        slot = by_name[section]
        if slot.question_count != expected["count"] or Decimal(str(slot.max_points)) != expected["max_points"]:
            raise ValidationError(f"{section} cần {expected['count']} mục và {expected['max_points']} điểm.")
        rules = _rules(slot)
        if not rules.get("phoneme_targets"):
            raise ValidationError(f"{section} phải khai báo phoneme_targets.")
        if section == "Đọc từ" and not rules.get("syllable_groups"):
            raise ValidationError("Đọc từ phải khai báo syllable_groups để cân bằng độ dài từ.")
        if section == "Đọc câu":
            if set(rules.get("sentence_types", [])) != {"declarative", "yes_no", "wh"}:
                raise ValidationError("Đọc câu phải có đủ declarative, yes_no và wh.")
        if section == "Đọc đoạn":
            bounds = rules.get("word_count_range")
            if bounds != [40, 60]:
                raise ValidationError("Đọc đoạn phải khai báo word_count_range [40, 60].")
    _check_rubric_weights(by_name["Đọc câu"], ("target_sounds", "sentence_stress", "intonation", "phrasing"))
    _check_rubric_weights(by_name["Đọc đoạn"], ("target_sounds", "stress_intonation", "fluency", "phrasing", "content_completeness"))


def validate_blueprint_schema(blueprint_version):
    slots = list(blueprint_version.slots.select_related("rubric_version").prefetch_related("rubric_version__criteria__descriptors"))
    if blueprint_version.assessment_type == "gt1":
        validate_gt1(slots)
    elif blueprint_version.assessment_type == "pronunciation":
        validate_pronunciation(slots)
