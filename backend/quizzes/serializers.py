"""Sérialiseurs pour Quiz et Question."""

from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import Answer, Attempt, Classroom, Question, Quiz

User = get_user_model()


class QuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Question
        fields = ["index", "prompt", "options", "correct_index"]


class QuestionPublicSerializer(serializers.ModelSerializer):
    """Version sans la bonne réponse — pour exposer le quiz à l'étudiant
    sans tricher (utilisée par K3 frontend si besoin)."""

    class Meta:
        model = Question
        fields = ["index", "prompt", "options"]


class QuizSerializer(serializers.ModelSerializer):
    """Renvoie un quiz complet avec toutes ses questions (incluant correct_index)."""

    questions = QuestionSerializer(many=True, read_only=True)

    class Meta:
        model = Quiz
        fields = ["id", "title", "source_text", "score", "created_at", "questions"]
        read_only_fields = ["id", "created_at"]


class QuizSummarySerializer(serializers.ModelSerializer):
    """Version compacte pour la liste d'historique."""

    nb_questions = serializers.SerializerMethodField()

    class Meta:
        model = Quiz
        fields = ["id", "title", "score", "nb_questions", "created_at"]

    def get_nb_questions(self, obj: Quiz) -> int:
        return obj.questions.count()


class AnswerItemSerializer(serializers.Serializer):
    """Une réponse fournie par l'utilisateur."""

    index = serializers.IntegerField(min_value=1, max_value=20)
    selected_index = serializers.IntegerField(min_value=0, max_value=3)


class SubmitAnswersSerializer(serializers.Serializer):
    """POST /api/quizzes/<id>/answer/ — le nombre de réponses doit correspondre
    au nombre RÉEL de questions du quiz.

    Le nombre attendu est transmis par la vue (qui connaît le quiz) via
    ``context["expected_count"]`` : la validation exige alors exactement N
    réponses couvrant les index 1..N, sans doublon. Si le contexte n'est pas
    fourni (usage hors vue), on se contente de contrôler l'absence de doublon —
    la vue garde de toute façon son propre contrôle final défensif.

    `question_order` (optionnel) : ordre d'affichage des questions pour le
    retest mélangé. Absent → ordre naturel [1..N] appliqué côté vue.
    """

    answers = AnswerItemSerializer(many=True)
    question_order = serializers.ListField(
        child=serializers.IntegerField(min_value=1, max_value=20),
        required=False,
        help_text="Ordre (mélangé) des index de questions pour cette tentative.",
    )

    def validate_answers(self, value):
        if not value:
            raise serializers.ValidationError("Aucune réponse fournie.")
        indices = [a["index"] for a in value]
        if len(set(indices)) != len(indices):
            raise serializers.ValidationError("Les indices de réponses ne doivent pas se répéter.")

        # Le nombre attendu vient du quiz (transmis par la vue). On vérifie que
        # les réponses couvrent EXACTEMENT les questions 1..N, où N est le nombre
        # réel de questions du quiz — jamais une constante en dur.
        expected = self.context.get("expected_count")
        if expected is not None and sorted(indices) != list(range(1, expected + 1)):
            raise serializers.ValidationError(
                f"{expected} réponses attendues, couvrant les questions 1..{expected}."
            )
        return value

    def validate_question_order(self, value):
        if value and len(set(value)) != len(value):
            raise serializers.ValidationError(
                "Les index de question_order ne doivent pas se répéter."
            )
        return value


# ---------------------------------------------------------------------------
# Release 2 — Historique des tentatives (Attempt / Answer)
# ---------------------------------------------------------------------------


class AttemptListSerializer(serializers.ModelSerializer):
    """Version compacte pour lister les tentatives d'un quiz."""

    class Meta:
        model = Attempt
        fields = ["id", "number", "score", "total", "created_at"]
        read_only_fields = fields


class AttemptAnswerSerializer(serializers.ModelSerializer):
    """Une réponse d'une tentative, enrichie du contenu de la question
    (pour rejouer / réviser la tentative)."""

    index = serializers.IntegerField(source="question.index", read_only=True)
    prompt = serializers.CharField(source="question.prompt", read_only=True)
    options = serializers.JSONField(source="question.options", read_only=True)
    correct_index = serializers.IntegerField(source="question.correct_index", read_only=True)

    class Meta:
        model = Answer
        fields = ["index", "prompt", "options", "correct_index", "selected_index", "is_correct"]
        read_only_fields = fields


class AttemptDetailSerializer(serializers.ModelSerializer):
    """Détail d'une tentative avec toutes ses réponses (pour rejouer)."""

    answers = serializers.SerializerMethodField()

    class Meta:
        model = Attempt
        fields = ["id", "number", "score", "total", "question_order", "created_at", "answers"]
        read_only_fields = fields

    def get_answers(self, obj: Attempt):
        # Tri par l'index de la question pour un rendu déterministe.
        qs = obj.answers.select_related("question").order_by("question__index")
        return AttemptAnswerSerializer(qs, many=True).data


# ---------------------------------------------------------------------------
# Classes (Classroom) — liaison enseignant / élèves via code d'invitation
# ---------------------------------------------------------------------------


class ClassroomSerializer(serializers.ModelSerializer):
    """Vue d'une classe (lecture)."""

    student_count = serializers.SerializerMethodField()
    teacher_name = serializers.SerializerMethodField()

    class Meta:
        model = Classroom
        fields = ["id", "name", "code", "student_count", "teacher_name", "created_at"]
        read_only_fields = fields

    def get_student_count(self, obj: Classroom) -> int:
        return obj.students.count()

    def get_teacher_name(self, obj: Classroom) -> str:
        return obj.teacher.get_full_name() or obj.teacher.username


class ClassroomCreateSerializer(serializers.ModelSerializer):
    """Création d'une classe : seul le nom est fourni (le code est généré)."""

    class Meta:
        model = Classroom
        fields = ["name"]


class JoinClassSerializer(serializers.Serializer):
    """Adhésion à une classe via son code d'invitation."""

    code = serializers.CharField(max_length=12)

    def validate_code(self, value: str) -> str:
        return value.strip().upper()


class ClassroomRenameSerializer(serializers.Serializer):
    """Renommage d'une classe (PATCH). Le frontend envoie `name` ; on accepte
    aussi `title` comme alias (les deux pointent vers le champ `name`)."""

    name = serializers.CharField(max_length=120, required=False, allow_blank=False)
    title = serializers.CharField(max_length=120, required=False, allow_blank=False)

    def validate(self, attrs):
        new_name = attrs.get("name") or attrs.get("title")
        if not new_name or not new_name.strip():
            raise serializers.ValidationError({"name": "Le nom de la classe est requis."})
        attrs["name"] = new_name.strip()
        return attrs


class AddStudentSerializer(serializers.Serializer):
    """Ajout d'un élève à une classe par son email OU son username."""

    identifier = serializers.CharField(max_length=254)

    def validate_identifier(self, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise serializers.ValidationError("L'identifiant (email ou username) est requis.")
        return cleaned


# ---------------------------------------------------------------------------
# Release 2 — Espace prof : suivi de la progression des élèves d'une classe
# ---------------------------------------------------------------------------


class StudentIdentitySerializer(serializers.ModelSerializer):
    """Identité minimale d'un élève exposée à son enseignant (pas d'email/rôle)."""

    class Meta:
        model = User
        fields = ["id", "first_name", "last_name", "username"]
        read_only_fields = fields


class ClassProgressStudentSerializer(serializers.Serializer):
    """Progression d'UN élève de la classe, agrégée sur toutes ses tentatives.

    Structure calculée dans la vue (`ClassProgressView`) à partir des `Attempt`
    de l'élève : KPIs (nombre de quiz passés, moyenne, meilleur / dernier score)
    et `evolution` (une entrée par tentative, triée chronologiquement, tous
    quizzes confondus) pour tracer le graphe d'évolution côté frontend.
    """

    student = StudentIdentitySerializer(read_only=True)
    quizzes_taken = serializers.IntegerField(read_only=True)
    average_score = serializers.FloatField(read_only=True, allow_null=True)
    best_score = serializers.IntegerField(read_only=True, allow_null=True)
    last_score = serializers.IntegerField(read_only=True, allow_null=True)
    evolution = serializers.ListField(child=serializers.DictField(), read_only=True)
