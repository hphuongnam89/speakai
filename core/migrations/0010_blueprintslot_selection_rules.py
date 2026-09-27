from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("core", "0009_questionversion_exam_metadata")]

    operations = [
        migrations.AddField(
            model_name="blueprintslot",
            name="selection_rules",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
