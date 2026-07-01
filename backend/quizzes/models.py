"""
Modèles métier d'EduTutor IA.

Un Quiz appartient à un utilisateur ; il contient le texte source du cours
(extrait du PDF ou collé en clair) et 10 Questions (QCM avec 4 options et
1 bonne réponse).
"""

from django.conf import settings
from django.db import models


class Quiz(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="quizzes",
        help_text="Propriétaire du quiz.",
    )
    title = models.CharField(max_length=200, help_text="Titre du cours / quiz (saisi ou déduit).")
    source_text = models.TextField(
        help_text="Texte source utilisé pour la génération (extrait PDF ou saisie).",
    )
    score = models.IntegerField(
        null=True,
        blank=True,
        help_text="Score /10 obtenu lors de la dernière tentative (None si pas encore passé).",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # --- Rattachement & personnalisation (build produit EduTutor) ---
    course = models.ForeignKey(
        "Course",
        on_delete=models.CASCADE,
        related_name="quizzes",
        null=True,
        blank=True,
        help_text="Cours source dont ce quiz est issu (null pour les quiz hérités).",
    )

    class Difficulty(models.TextChoices):
        EASY = "easy", "Facile"
        MEDIUM = "medium", "Moyen"
        HARD = "hard", "Difficile"

    difficulty = models.CharField(
        max_length=10,
        choices=Difficulty.choices,
        default=Difficulty.MEDIUM,
        help_text="Niveau de difficulté demandé à la génération.",
    )
    num_questions = models.PositiveSmallIntegerField(
        default=10,
        help_text="Nombre de questions du quiz (5 à 20).",
    )
    theme = models.CharField(
        max_length=200,
        blank=True,
        default="",
        help_text="Thème ou chapitre ciblé pour la génération (optionnel).",
    )
    is_published = models.BooleanField(
        default=False,
        help_text="Quiz publié par un enseignant, distribuable à une classe.",
    )
    assigned_classes = models.ManyToManyField(
        "Classroom",
        related_name="quizzes",
        blank=True,
        help_text="Classes auxquelles ce quiz est distribué.",
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Quiz"
        verbose_name_plural = "Quizz"

    def __str__(self) -> str:
        return f"{self.title} — {self.user.username}"


class Question(models.Model):
    quiz = models.ForeignKey(
        Quiz,
        on_delete=models.CASCADE,
        related_name="questions",
    )
    index = models.PositiveIntegerField(
        help_text="Position de la question dans le quiz (1 à 10).",
    )
    prompt = models.TextField(help_text="Énoncé de la question.")
    options = models.JSONField(
        help_text="Liste des 4 options (chaînes). Ex : ['Paris', 'Londres', 'Madrid', 'Berlin']",
    )
    correct_index = models.PositiveSmallIntegerField(
        help_text="Index (0 à 3) de la bonne réponse dans `options`.",
    )

    class QType(models.TextChoices):
        MCQ = "mcq", "QCM"
        TRUE_FALSE = "truefalse", "Vrai / Faux"
        SHORT = "short", "Réponse courte"

    qtype = models.CharField(
        max_length=12,
        choices=QType.choices,
        default=QType.MCQ,
        help_text="Type de question : QCM, Vrai/Faux ou réponse courte.",
    )
    correct_text = models.CharField(
        max_length=300,
        blank=True,
        default="",
        help_text="Bonne réponse attendue pour une question « réponse courte ».",
    )
    # [Lot 6 — Révision des erreurs] Dernière réponse donnée par l'utilisateur.
    # None = pas encore répondu. On stocke la DERNIÈRE tentative pour pouvoir
    # lister les questions ratées (selected_index != correct_index).
    selected_index = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text="Dernier index (0 à 3) choisi par l'utilisateur (None si pas répondu).",
    )

    class Meta:
        ordering = ["index"]
        unique_together = [("quiz", "index")]
        verbose_name = "Question"
        verbose_name_plural = "Questions"

    def __str__(self) -> str:
        return f"Q{self.index} — {self.prompt[:50]}…"


# ---------------------------------------------------------------------------
# Build produit EduTutor — Classes, Cours, Tentatives, Réponses
# ---------------------------------------------------------------------------


class Classroom(models.Model):
    """Classe créée par un enseignant ; les élèves la rejoignent via un code."""

    name = models.CharField(max_length=120, help_text="Nom de la classe (ex. « Terminale B »).")
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="classes_taught",
        help_text="Enseignant propriétaire de la classe.",
    )
    code = models.CharField(
        max_length=12,
        unique=True,
        db_index=True,
        help_text="Code d'invitation communiqué aux élèves pour rejoindre la classe.",
    )
    students = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name="classes_joined",
        blank=True,
        help_text="Élèves membres de la classe.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Classe"
        verbose_name_plural = "Classes"

    def __str__(self) -> str:
        return f"{self.name} ({self.code})"


class Course(models.Model):
    """Cours déposé par un utilisateur — source des quiz, fiches et résumés."""

    class Source(models.TextChoices):
        PDF = "pdf", "PDF"
        TEXT = "text", "Texte"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="courses",
        help_text="Propriétaire du cours.",
    )
    title = models.CharField(max_length=200, help_text="Titre du cours.")
    content = models.TextField(help_text="Texte source du cours (extrait PDF ou saisie).")
    source_type = models.CharField(
        max_length=10,
        choices=Source.choices,
        default=Source.TEXT,
        help_text="Origine du contenu : PDF importé ou texte collé.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Cours"
        verbose_name_plural = "Cours"

    def __str__(self) -> str:
        return f"{self.title} — {self.owner.username}"


class Attempt(models.Model):
    """Tentative d'un élève sur un quiz — permet le retest et l'historique par barre.

    Chaque nouvelle tentative crée une ligne (« cours-1 », « cours-2 »…). Les
    questions sont présentées dans un `question_order` mélangé pour forcer la
    mémorisation des réponses, pas de leur position.
    """

    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name="attempts")
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="attempts",
    )
    number = models.PositiveIntegerField(
        help_text="N° de tentative de cet élève sur ce quiz (1, 2, 3…) — libellé « cours-N »."
    )
    score = models.IntegerField(null=True, blank=True, help_text="Score obtenu à cette tentative.")
    total = models.PositiveSmallIntegerField(
        default=10, help_text="Nombre de questions de la tentative."
    )
    question_order = models.JSONField(
        default=list,
        blank=True,
        help_text="Ordre (mélangé) des index de questions pour cette tentative.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["quiz_id", "number"]
        unique_together = [("quiz", "student", "number")]
        verbose_name = "Tentative"
        verbose_name_plural = "Tentatives"

    def __str__(self) -> str:
        return f"{self.quiz.title} — {self.student.username} #{self.number}"


class Answer(models.Model):
    """Réponse d'un élève à une question, dans le cadre d'une tentative."""

    attempt = models.ForeignKey(Attempt, on_delete=models.CASCADE, related_name="answers")
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="answers")
    selected_index = models.PositiveSmallIntegerField(
        null=True, blank=True, help_text="Index choisi (QCM / Vrai-Faux)."
    )
    text_answer = models.CharField(
        max_length=300, blank=True, default="", help_text="Réponse saisie (réponse courte)."
    )
    is_correct = models.BooleanField(default=False)

    class Meta:
        unique_together = [("attempt", "question")]
        verbose_name = "Réponse"
        verbose_name_plural = "Réponses"

    def __str__(self) -> str:
        return f"Réponse<attempt={self.attempt_id} question={self.question_id}>"
