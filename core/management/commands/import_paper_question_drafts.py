import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction

from core.models import Course, Question, QuestionVersion


class Command(BaseCommand):
    help = "Import paper-exam conversion JSON as QuestionVersion drafts; never approves items automatically."

    def add_arguments(self, parser):
        parser.add_argument("--path", default="data/question_bank/paper_to_online_drafts.json")
        parser.add_argument("--course", default="GT1")
        parser.add_argument("--username", default="demo-teacher")

    @transaction.atomic
    def handle(self, *args, **options):
        path = Path(options["path"])
        if not path.exists():
            raise CommandError(f"Không tìm thấy file: {path}")
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise CommandError(f"Không đọc được JSON: {exc}") from exc
        if document.get("status") != "draft_only" or not isinstance(document.get("items"), list):
            raise CommandError("File phải có status=draft_only và items là list.")
        course = Course.objects.filter(code=options["course"]).first()
        creator = get_user_model().objects.filter(username=options["username"]).first()
        if not course or not creator:
            raise CommandError("Cần có course và user tương ứng trước khi import.")
        required = {"language", "task_type", "topic", "target_level_min", "target_level_max", "prompt_text", "prep_seconds", "response_seconds", "source_reference", "exam_metadata"}
        created = skipped = 0
        for index, item in enumerate(document["items"], start=1):
            if not isinstance(item, dict) or not required.issubset(item):
                raise CommandError(f"Item {index} thiếu trường bắt buộc.")
            if not isinstance(item["exam_metadata"], dict) or not item["exam_metadata"]:
                raise CommandError(f"Item {index} cần exam_metadata là object không rỗng.")
            duplicate = QuestionVersion.objects.filter(
                question__course=course, prompt_text=item["prompt_text"], source_reference=item["source_reference"],
            ).exists()
            if duplicate:
                skipped += 1
                continue
            question = Question.objects.create(course=course, created_by=creator)
            version = QuestionVersion(
                question=question, version=1, created_by=creator, status=QuestionVersion.Status.DRAFT,
                language=item["language"], task_type=item["task_type"], topic=item["topic"],
                target_level_min=item["target_level_min"], target_level_max=item["target_level_max"],
                prompt_text=item["prompt_text"], candidate_instructions=item.get("candidate_instructions", ""),
                prep_seconds=item["prep_seconds"], response_seconds=item["response_seconds"],
                required_points=item.get("required_points", []), optional_prompts=item.get("optional_prompts", []),
                allowed_alternatives=item.get("allowed_alternatives", []), criterion_refs=item.get("criterion_refs", []),
                source_reference=item["source_reference"], source_notes=item.get("source_notes", ""),
                exam_metadata=item["exam_metadata"],
            )
            try:
                version.full_clean()
                version.save()
            except ValidationError as exc:
                raise CommandError(f"Item {index} không hợp lệ: {exc}") from exc
            created += 1
        self.stdout.write(self.style.SUCCESS(f"Đã tạo {created} câu hỏi draft; bỏ qua {skipped} bản ghi trùng. Không có câu nào được tự động duyệt."))
