from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("core", "0013_examattempt_reviewed_at_alter_examanswer_audio")]

    operations = [
        migrations.AddField(
            model_name="blueprintversion",
            name="pass_threshold",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True),
        ),
        migrations.AddField(
            model_name="examattempt",
            name="passed",
            field=models.BooleanField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="examattempt",
            name="started_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="examattempt",
            name="expires_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
