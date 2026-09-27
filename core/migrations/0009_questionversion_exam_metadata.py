from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("core", "0008_rubric_bands_and_weights")]

    operations = [
        migrations.AddField(
            model_name="questionversion",
            name="exam_metadata",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
