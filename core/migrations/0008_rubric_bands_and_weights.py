from decimal import Decimal

from django.db import migrations, models
from django.core.validators import MaxValueValidator, MinValueValidator


class Migration(migrations.Migration):
    dependencies = [("core", "0007_practice_score_scale_100")]

    operations = [
        migrations.AddField(
            model_name="rubriccriterion",
            name="signal",
            field=models.CharField(default="llm", max_length=64),
        ),
        migrations.AddField(
            model_name="rubriccriterion",
            name="bands",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="rubriccriterion",
            name="weight",
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal("0.00"),
                max_digits=5,
                validators=[MinValueValidator(Decimal("0.01")), MaxValueValidator(Decimal("100.00"))],
            ),
        ),
        migrations.AlterField(
            model_name="criterionleveldescriptor",
            name="level",
            field=models.CharField(
                choices=[("0", "0"), ("1", "1"), ("2", "2"), ("3", "3"), ("4", "4")],
                max_length=1,
            ),
        ),
    ]
