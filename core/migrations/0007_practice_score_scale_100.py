from decimal import Decimal

from django.db import migrations, models


def convert_legacy_ten_point_scores(apps, schema_editor):
    PracticeAttempt = apps.get_model("core", "PracticeAttempt")
    for attempt in PracticeAttempt.objects.exclude(ai_score=None):
        attempt.ai_score = attempt.ai_score * Decimal("10")
        attempt.save(update_fields=("ai_score",))
    for attempt in PracticeAttempt.objects.exclude(final_score=None):
        attempt.final_score = attempt.final_score * Decimal("10")
        attempt.save(update_fields=("final_score",))


class Migration(migrations.Migration):
    dependencies = [("core", "0006_practice_scoring")]

    operations = [
        migrations.AlterField(model_name="practiceattempt", name="ai_score", field=models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True)),
        migrations.AlterField(model_name="practiceattempt", name="final_score", field=models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True)),
        migrations.RunPython(convert_legacy_ten_point_scores, migrations.RunPython.noop),
    ]
