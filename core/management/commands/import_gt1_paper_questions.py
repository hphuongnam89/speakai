from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core.models import Course, Question, QuestionVersion


# Verbatim Task 1B prompts transcribed from the three scanned GT1 examination PDFs.
PAPERS = {
    "1": {
        "Free Time & Hobbies": [
            "What do you do in your free time?", "Do you like watching TV?",
            "Do you like sports?", "What do you do at weekend?",
            "Do you prefer staying at home or going out?",
        ],
        "Food & Drinks": [
            "What is your favourite food?", "What do you usually eat for breakfast?",
            "Do you like fast food?", "What is your favorite drink?",
            "Can you cook? What can you cook?",
        ],
    },
    "2": {
        "Home & Neighborhood": [
            "Where do you live (house or apartment)?", "How many rooms are there in your home?",
            "What is your favorite room?", "Is your neighborhood quiet or busy?",
            "Is there a supermarket near your home?",
        ],
        "Transportation": [
            "How do you go to school / work?", "How long does it take?",
            "Do you use a bike, motorbike, bus, or car?", "Do you like traveling by bus?",
            "How often do you walk?",
        ],
    },
    "3": {
        "Food & Drinks": [
            "What is your favorite food?", "What do you usually eat for breakfast?",
            "Do you like fast food?", "What is your favorite drink?",
            "Can you cook? What can you cook?",
        ],
        "Transportation": [
            "How do you go to school / work?", "How long does it take?",
            "Do you use a bike, motorbike, bus, or car?", "Do you like traveling by bus?",
            "How often do you walk?",
        ],
    },
}


class Command(BaseCommand):
    help = "Import source-checked GT1 Task 1B questions as drafts, then submit them for independent review."

    @transaction.atomic
    def handle(self, *args, **options):
        User = get_user_model()
        teacher = User.objects.filter(username="demo-teacher").first()
        course = Course.objects.filter(code="GT1").first()
        if not teacher or not course:
            raise CommandError("Run seed_demo first; demo-teacher and course GT1 are required.")

        imported = 0
        existing = 0
        for paper, topics in PAPERS.items():
            source = f"Đề thi giấy Giao tiếp 1, đề {paper}, trang 1, Task 1B"
            for topic, prompts in topics.items():
                for prompt in prompts:
                    version = QuestionVersion.objects.filter(
                        question__course=course, source_reference=source, prompt_text=prompt,
                    ).first()
                    if version:
                        existing += 1
                        continue
                    question = Question.objects.create(course=course, created_by=teacher)
                    version = QuestionVersion.objects.create(
                        question=question, version=1, created_by=teacher, language="en",
                        task_type="short_question", topic=topic,
                        target_level_min="A1", target_level_max="A2",
                        prompt_text=prompt,
                        candidate_instructions="Answer the question individually.",
                        prep_seconds=0, response_seconds=45,
                        source_reference=source,
                        source_notes=(
                            "Transcribed from the cited scanned source. Timing and online delivery "
                            "are demo settings, not specified by the paper. Imported as draft; "
                            "requires independent teacher/admin review before random exam use."
                        ),
                    )
                    version.status = QuestionVersion.Status.IN_REVIEW
                    version.save(update_fields=["status"])
                    imported += 1

        self.stdout.write(self.style.SUCCESS(
            f"GT1 source questions submitted for review: {imported} new, {existing} already imported."
        ))
