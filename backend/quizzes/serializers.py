"""Sérialiseurs pour Quiz et Question."""

from rest_framework import serializers

from .models import Answer, Attempt, Classroom, Question, Quiz


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
    """Renvoie un quiz complet avec ses 10 questions (incluant correct_index)."""

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
    au nombre de questions du quiz (contrôle final dans la vue, qui connaît le
    quiz ; ici on vérifie seulement l'absence de doublon d'index).

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
