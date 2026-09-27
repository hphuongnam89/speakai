from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("core", "0014_official_threshold_timebox")]

    operations = [
        migrations.AddField(
            model_name="blueprintversion",
            name="assessment_type",
            field=models.CharField(
                choices=[("custom", "Custom"), ("gt1", "GT1"), ("pronunciation", "Ngữ âm")],
                default="custom", max_length=20,
            ),
        ),
    ]
