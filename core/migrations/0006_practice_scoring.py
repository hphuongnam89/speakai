from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("core", "0005_practiceattempt_practiceanswer_and_more")]

    operations = [
        migrations.AddField(model_name="practiceattempt", name="scoring_status", field=models.CharField(choices=[("not_started", "Chưa chấm"), ("ai_processing", "AI đang chấm"), ("ai_draft", "AI nháp"), ("final", "Đã duyệt điểm"), ("failed", "AI chấm lỗi")], default="not_started", max_length=16)),
        migrations.AddField(model_name="practiceattempt", name="ai_score", field=models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True)),
        migrations.AddField(model_name="practiceattempt", name="ai_result", field=models.JSONField(blank=True, default=dict)),
        migrations.AddField(model_name="practiceattempt", name="ai_scored_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="practiceattempt", name="scoring_error", field=models.TextField(blank=True)),
        migrations.AddField(model_name="practiceattempt", name="final_score", field=models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True)),
        migrations.AddField(model_name="practiceattempt", name="final_feedback", field=models.TextField(blank=True)),
        migrations.AddField(model_name="practiceattempt", name="reviewed_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="practiceattempt", name="reviewed_by", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="reviewed_practice_attempts", to=settings.AUTH_USER_MODEL)),
    ]
