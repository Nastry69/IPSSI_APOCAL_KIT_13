# Generated for the RGPD consent tracking (Sprint A — M3).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="profile",
            name="consent_accepted_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="profile",
            name="consent_version",
            field=models.CharField(blank=True, default="", max_length=20),
        ),
    ]
