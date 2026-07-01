# Generated for Release 2 — StudyDoc (fiche de révision / résumé).

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("quizzes", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="StudyDoc",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                (
                    "kind",
                    models.CharField(
                        choices=[("note", "Fiche de révision"), ("summary", "Résumé")],
                        help_text="Format du document : fiche de révision ou résumé.",
                        max_length=10,
                    ),
                ),
                (
                    "title",
                    models.CharField(help_text="Titre du cours / document.", max_length=200),
                ),
                ("content", models.TextField(help_text="Contenu généré (texte / markdown).")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "owner",
                    models.ForeignKey(
                        help_text="Propriétaire du document de révision.",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="study_docs",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Document de révision",
                "verbose_name_plural": "Documents de révision",
                "ordering": ["-created_at"],
            },
        ),
    ]
