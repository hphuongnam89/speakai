import random
import secrets

from django.core.exceptions import ValidationError
from django.db import transaction

from core.models import BlueprintSample, BlueprintSlot, BlueprintVersion, QuestionVersion, RubricVersion


class InsufficientQuestionPool(Exception):
    def __init__(self, shortages):
        self.shortages = shortages
        super().__init__("Không đủ câu đã duyệt phù hợp cấu hình cho mọi phần.")


def question_snapshot(question):
    return {
        "question_id": question.question_id,
        "version_id": question.pk,
        "version": question.version,
        "status": question.status,
        "language": question.language,
        "task_type": question.task_type,
        "topic": question.topic,
        "target_level_min": question.target_level_min,
        "target_level_max": question.target_level_max,
        "prompt_text": question.prompt_text,
        "candidate_instructions": question.candidate_instructions,
        "prep_seconds": question.prep_seconds,
        "response_seconds": question.response_seconds,
        "required_points": question.required_points,
        "optional_prompts": question.optional_prompts,
        "allowed_alternatives": question.allowed_alternatives,
        "criterion_refs": question.criterion_refs,
        "source_reference": question.source_reference,
        "source_notes": question.source_notes,
        "tags": list(question.tags.order_by("slug").values_list("slug", flat=True)),
    }


@transaction.atomic
def sample_blueprint(*, blueprint_version, topic, created_by, seed=None):
    if not topic or len(topic) > 160:
        raise ValidationError("Chủ đề cần có nội dung và không vượt quá 160 ký tự.")
    blueprint_version = BlueprintVersion.objects.select_for_update().select_related(
        "blueprint", "blueprint__course"
    ).get(pk=blueprint_version.pk)
    if blueprint_version.status == BlueprintVersion.Status.RETIRED:
        raise ValidationError("Blueprint đã ngừng sử dụng.")
    slots = list(
        BlueprintSlot.objects.select_for_update().select_related(
            "rubric_version", "rubric_version__rubric"
        ).filter(blueprint_version=blueprint_version).order_by("position")
    )
    list(RubricVersion.objects.select_for_update().filter(
        pk__in=[slot.rubric_version_id for slot in slots]
    ).order_by("pk"))
    blueprint_version.validate_for_publication()
    seed = secrets.randbits(63) if seed is None else seed
    if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed < 2**63:
        raise ValidationError("Seed phải là số nguyên trong phạm vi 0 đến 2^63−1.")

    rng = random.Random(seed)
    pools = {}
    pool_snapshots = []
    exclusions = []
    base = QuestionVersion.objects.filter(question__course=blueprint_version.blueprint.course)

    for slot in slots:
        stage = base.filter(status=QuestionVersion.Status.APPROVED)
        unapproved_count = base.exclude(status=QuestionVersion.Status.APPROVED).count()
        other_topic_count = stage.exclude(topic=topic).count()
        topic_pool = stage.filter(topic=topic)
        other_task_count = topic_pool.exclude(task_type=slot.task_type).count()
        compatible = topic_pool.filter(
            task_type=slot.task_type,
            language=slot.language,
            response_seconds=slot.response_seconds,
            target_level_min__gt="",
            target_level_max__gt="",
            target_level_min__lte=slot.target_level_max,
            target_level_max__gte=slot.target_level_min,
            source_reference__gt="",
        )
        if slot.prep_seconds is not None:
            compatible = compatible.filter(prep_seconds=slot.prep_seconds)
        eligible = list(
            compatible.select_for_update(of=("self",)).select_related("question").prefetch_related("tags").order_by("pk")
        )
        incompatible_count = topic_pool.filter(task_type=slot.task_type).count() - len(eligible)
        rng.shuffle(eligible)
        pools[slot.pk] = eligible
        pool_snapshots.append({
            "slot_id": slot.pk,
            "section_name": slot.section_name,
            "task_type": slot.task_type,
            "candidate_version_ids": [item.pk for item in eligible],
        })
        exclusions.append({
            "slot_id": slot.pk,
            "not_approved": unapproved_count,
            "different_topic": other_topic_count,
            "different_task_type": other_task_count,
            "metadata_or_source_mismatch": max(incompatible_count, 0),
        })

    demands = [
        (slot.pk, item_number)
        for slot in slots
        for item_number in range(slot.question_count)
    ]
    tie_order = {demand: rng.random() for demand in demands}
    demands.sort(key=lambda demand: (len(pools[demand[0]]), tie_order[demand]))
    candidate_owner = {}
    demand_selection = {}

    def assign(demand, visited):
        for candidate in pools[demand[0]]:
            if candidate.pk in visited:
                continue
            visited.add(candidate.pk)
            current = candidate_owner.get(candidate.pk)
            if current is None or assign(current, visited):
                candidate_owner[candidate.pk] = demand
                demand_selection[demand] = candidate
                return True
        return False

    for demand in demands:
        assign(demand, set())

    if len(demand_selection) != len(demands):
        shortages = []
        for slot in slots:
            allocated = sum(1 for slot_id, _ in demand_selection if slot_id == slot.pk)
            if allocated < slot.question_count:
                shortages.append({
                    "section_name": slot.section_name,
                    "required": slot.question_count,
                    "eligible_pool": len(pools[slot.pk]),
                    "uniquely_allocated": allocated,
                })
        raise InsufficientQuestionPool(shortages)

    selected = []
    for slot in slots:
        questions = [
            demand_selection[(slot.pk, item_number)]
            for item_number in range(slot.question_count)
        ]
        selected.append({
            "slot": {
                "section_name": slot.section_name,
                "task_type": slot.task_type,
                "question_count": slot.question_count,
                "target_level_min": slot.target_level_min,
                "target_level_max": slot.target_level_max,
                "language": slot.language,
                "prep_seconds": slot.prep_seconds,
                "response_seconds": slot.response_seconds,
            },
            "rubric_version_id": slot.rubric_version_id,
            "rubric_version": slot.rubric_version.version,
            "rubric_snapshot": slot.rubric_version.content_snapshot(),
            "questions": [question_snapshot(question) for question in questions],
        })

    return BlueprintSample.objects.create(
        blueprint_version=blueprint_version,
        created_by=created_by,
        topic=topic,
        seed=seed,
        blueprint_snapshot=blueprint_version.content_snapshot(),
        candidate_pool_snapshot=pool_snapshots,
        exclusion_snapshot=exclusions,
        selected_snapshot=selected,
    )
