import core.models
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("core", "0012_blueprintslot_max_points")]

    operations = [
        migrations.AddField(
            model_name="examattempt",
            name="reviewed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="examanswer",
            name="audio",
            field=models.FileField(upload_to=core.models.exam_audio_upload_path),
        ),
    ]
