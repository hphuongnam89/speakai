import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0010_blueprintslot_selection_rules"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ExamAttempt",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("seed", models.PositiveBigIntegerField()),
                ("blueprint_snapshot", models.JSONField()),
                ("questions_snapshot", models.JSONField()),
                ("threshold", models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True)),
                ("status", models.CharField(choices=[("in_progress", "Đang làm"), ("submitted", "Đã nộp")], default="in_progress", max_length=16)),
                ("scoring_status", models.CharField(choices=[("not_started", "Chưa chấm"), ("needs_review", "Cần rà soát"), ("final", "Đã duyệt điểm")], default="not_started", max_length=16)),
                ("scoring_result", models.JSONField(blank=True, default=dict)),
                ("ai_score", models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True)),
                ("final_score", models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True)),
                ("final_feedback", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("submitted_at", models.DateTimeField(blank=True, null=True)),
                ("blueprint_version", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="exam_attempts", to="core.blueprintversion")),
                ("course", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="exam_attempts", to="core.course")),
                ("reviewed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="reviewed_exam_attempts", to=settings.AUTH_USER_MODEL)),
                ("student", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="exam_attempts", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ("-created_at", "-id")},
        ),
        migrations.CreateModel(
            name="ExamAnswer",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("question_index", models.PositiveSmallIntegerField()),
                ("audio", models.FileField(upload_to="core.models.exam_audio_upload_path")),
                ("audio_extension", models.CharField(max_length=5)),
                ("content_type", models.CharField(max_length=32)),
                ("duration_seconds", models.PositiveSmallIntegerField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("attempt", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="answers", to="core.examattempt")),
            ],
            options={"ordering": ("question_index",), "constraints": [models.UniqueConstraint(fields=("attempt", "question_index"), name="unique_exam_answer_per_question")]},
        ),
        migrations.CreateModel(
            name="ExamScoreDecision",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("decision", models.CharField(max_length=32)),
                ("score", models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True)),
                ("payload", models.JSONField(blank=True, default=dict)),
                ("reason", models.TextField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("actor", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="exam_score_decisions", to=settings.AUTH_USER_MODEL)),
                ("attempt", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="score_decisions", to="core.examattempt")),
            ],
        ),
    ]
