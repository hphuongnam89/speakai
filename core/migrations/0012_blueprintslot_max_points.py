from decimal import Decimal

from django.db import migrations, models
from django.core.validators import MinValueValidator


class Migration(migrations.Migration):
    dependencies = [("core", "0011_official_exam_flow")]

    operations = [
        migrations.AddField(
            model_name="blueprintslot",
            name="max_points",
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal("1.00"),
                max_digits=5,
                validators=[MinValueValidator(Decimal("0.01"))],
            ),
        ),
    ]
