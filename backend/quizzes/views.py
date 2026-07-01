"""
Endpoints quizz :
    GET   /api/quizzes/                — historique du user connecté
    GET   /api/quizzes/<id>/           — détail (avec les 10 questions)
    POST  /api/quizzes/<id>/answer/    — soumet 10 réponses, renvoie le score
"""

import secrets

from django.db import transaction
from django.db.models import Avg, Count, F, Max
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsTeacher

from .models import Answer, Attempt, Classroom, Question, Quiz
from .serializers import (
    AttemptDetailSerializer,
    AttemptListSerializer,
    ClassProgressStudentSerializer,
    ClassroomCreateSerializer,
    ClassroomSerializer,
    JoinClassSerializer,
    QuizSerializer,
    QuizSummarySerializer,
    StudentIdentitySerializer,
    SubmitAnswersSerializer,
)


class QuizListView(generics.ListAPIView):
    """Historique des quizz du user connecté."""

    serializer_class = QuizSummarySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Quiz.objects.filter(user=self.request.user).order_by("-created_at")

    @extend_schema(description="Liste paginée des quizz de l'utilisateur connecté.")
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class QuizDetailView(generics.RetrieveAPIView):
    """Détail d'un quiz (les 10 questions complètes)."""

    serializer_class = QuizSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Quiz.objects.filter(user=self.request.user)


class AnswerQuizView(APIView):
    """Reçoit 10 réponses, calcule le score, met à jour le quiz."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=SubmitAnswersSerializer,
        responses={200: OpenApiResponse(description="{ score, total, details }")},
        description=(
            "Soumet les 10 réponses et reçoit le détail de la correction. "
            "Le score est persisté sur le quiz."
        ),
    )
    def post(self, request, pk: int):
        quiz = get_object_or_404(Quiz, pk=pk, user=request.user)

        serializer = SubmitAnswersSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        answers = serializer.validated_data["answers"]
        question_order = serializer.validated_data.get("question_order")

        # Index pour lookup rapide
        questions_by_idx = {q.index: q for q in quiz.questions.all()}
        expected = len(questions_by_idx)
        if expected == 0:
            return Response(
                {"detail": "Ce quiz n'a aucune question — état incohérent."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # Le nombre de réponses doit couvrir exactement les questions 1..expected.
        submitted = sorted(a["index"] for a in answers)
        if submitted != list(range(1, expected + 1)):
            return Response(
                {"detail": f"{expected} réponses attendues, couvrant les questions 1..{expected}."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        details = []
        score = 0
        # [Release 2] On collecte les réponses par question pour créer les Answer
        # de la tentative sans re-parcourir la liste.
        answer_rows = []
        for ans in answers:
            q = questions_by_idx[ans["index"]]
            correct = q.correct_index == ans["selected_index"]
            if correct:
                score += 1
            # [Lot 6] On mémorise la réponse choisie pour la révision des erreurs.
            q.selected_index = ans["selected_index"]
            answer_rows.append((q, ans["selected_index"], correct))
            details.append(
                {
                    "index": ans["index"],
                    "selected_index": ans["selected_index"],
                    "correct_index": q.correct_index,
                    "correct": correct,
                }
            )

        # Ordre d'affichage : payload fourni sinon séquence naturelle [1..expected].
        order = question_order if question_order else list(range(1, expected + 1))

        # [Release 2] Persistance atomique : dernière réponse par question
        # (compat Lot 6), score du quiz, et nouvelle tentative + réponses.
        with transaction.atomic():
            for q, _selected_index, _correct in answer_rows:
                q.save(update_fields=["selected_index"])

            quiz.score = score
            quiz.save(update_fields=["score", "updated_at"])

            # N° de tentative = max existant (ce user + ce quiz) + 1.
            last_number = (
                Attempt.objects.filter(quiz=quiz, student=request.user).aggregate(m=Max("number"))[
                    "m"
                ]
                or 0
            )
            attempt = Attempt.objects.create(
                quiz=quiz,
                student=request.user,
                number=last_number + 1,
                total=expected,
                score=score,
                question_order=order,
            )
            Answer.objects.bulk_create(
                [
                    Answer(
                        attempt=attempt,
                        question=q,
                        selected_index=selected_index,
                        is_correct=correct,
                    )
                    for q, selected_index, correct in answer_rows
                ]
            )

        return Response(
            {
                "score": score,
                "total": expected,
                "details": details,
                "attempt_id": attempt.id,
                "number": attempt.number,
            }
        )


class AttemptListView(generics.ListAPIView):
    """GET /api/quizzes/<id>/attempts/ — tentatives du user sur ce quiz.

    Scoping STRICT : uniquement les tentatives de request.user, les plus
    récentes d'abord.
    """

    serializer_class = AttemptListSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None

    def get_queryset(self):
        quiz = get_object_or_404(Quiz, pk=self.kwargs["pk"], user=self.request.user)
        return Attempt.objects.filter(quiz=quiz, student=self.request.user).order_by(
            "-number", "-created_at"
        )

    @extend_schema(
        responses={200: AttemptListSerializer(many=True)},
        description="Liste des tentatives de l'utilisateur pour ce quiz (récentes d'abord).",
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class AttemptDetailView(generics.RetrieveAPIView):
    """GET /api/quizzes/<id>/attempts/<attempt_id>/ — détail d'une tentative
    avec ses réponses (pour rejouer). 404 si la tentative n'appartient pas au user."""

    serializer_class = AttemptDetailSerializer
    permission_classes = [IsAuthenticated]
    lookup_url_kwarg = "attempt_id"

    def get_queryset(self):
        return Attempt.objects.filter(quiz_id=self.kwargs["pk"], student=self.request.user)


# ---------------------------------------------------------------------------
# MVP2 — Dashboard de progression (Lot 6)
# ---------------------------------------------------------------------------


class StatsView(APIView):
    """Statistiques de progression de l'utilisateur connecté.

    [Note pédagogique] On agrège côté base de données (Avg, Count, Max…) plutôt
    que de tout charger en Python : c'est plus rapide et ça montre la puissance
    de l'ORM Django. `taken` = quiz réellement passés (score non nul).
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: OpenApiResponse(description="KPIs + historique des scores")})
    def get(self, request):
        quizzes = Quiz.objects.filter(user=request.user)
        taken = quizzes.filter(score__isnull=False)

        agg = taken.aggregate(avg=Avg("score"), best=Max("score"), nb=Count("id"))
        nb_taken = agg["nb"] or 0

        # Précision globale sur les questions répondues (toutes tentatives confondues).
        answered = Question.objects.filter(quiz__user=request.user, selected_index__isnull=False)
        nb_answered = answered.count()
        nb_correct = answered.filter(selected_index=F("correct_index")).count()

        # Historique chronologique des scores (pour le graphique de progression).
        history = [
            {
                "id": q.id,
                "title": q.title,
                "score": q.score,
                "created_at": q.created_at,
            }
            for q in taken.order_by("created_at")
        ]

        return Response(
            {
                "total_quizzes": quizzes.count(),
                "quizzes_taken": nb_taken,
                "average_score": round(agg["avg"], 1) if agg["avg"] is not None else None,
                "best_score": agg["best"],
                "last_score": history[-1]["score"] if history else None,
                "questions_answered": nb_answered,
                "questions_correct": nb_correct,
                "accuracy": round(100 * nb_correct / nb_answered) if nb_answered else None,
                "history": history,
            }
        )


# ---------------------------------------------------------------------------
# MVP2 — Révision des erreurs (Lot 6)
# ---------------------------------------------------------------------------


class MistakesView(APIView):
    """Liste les questions ratées (dernière réponse incorrecte) de l'utilisateur."""

    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: OpenApiResponse(description="Liste des questions ratées")})
    def get(self, request):
        wrong = (
            Question.objects.filter(quiz__user=request.user, selected_index__isnull=False)
            .exclude(selected_index=F("correct_index"))
            .select_related("quiz")
            .order_by("-quiz__created_at", "index")
        )
        items = [
            {
                "quiz_id": q.quiz_id,
                "quiz_title": q.quiz.title,
                "index": q.index,
                "prompt": q.prompt,
                "options": q.options,
                "correct_index": q.correct_index,
                "selected_index": q.selected_index,
            }
            for q in wrong
        ]
        return Response({"count": len(items), "mistakes": items})


# ---------------------------------------------------------------------------
# Classes (Classroom) — création par l'enseignant, adhésion par code
# ---------------------------------------------------------------------------

# Alphabet sans caractères ambigus (ni I, L, O, 0, 1) pour un code lisible.
_CLASS_CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


def _unique_class_code(length: int = 6) -> str:
    """Génère un code de classe unique, lisible et non ambigu."""
    for _ in range(20):
        code = "".join(secrets.choice(_CLASS_CODE_ALPHABET) for _ in range(length))
        if not Classroom.objects.filter(code=code).exists():
            return code
    # Repli extrêmement improbable : on allonge le code pour garantir l'unicité.
    return "".join(secrets.choice(_CLASS_CODE_ALPHABET) for _ in range(length + 4))


class ClassesView(APIView):
    """GET : les classes du caller (selon son rôle). POST : création (enseignant)."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses={200: OpenApiResponse(description="Liste des classes du caller")},
        description="Enseignant : ses classes ; élève : les classes rejointes.",
    )
    def get(self, request):
        user = request.user
        if getattr(user, "is_teacher", False):
            qs = Classroom.objects.filter(teacher=user)
        else:
            qs = user.classes_joined.all()
        return Response(ClassroomSerializer(qs, many=True).data)

    @extend_schema(request=ClassroomCreateSerializer, responses={201: ClassroomSerializer})
    def post(self, request):
        if not getattr(request.user, "is_teacher", False):
            return Response(
                {"detail": "Seuls les enseignants peuvent créer une classe."},
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = ClassroomCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        classroom = Classroom.objects.create(
            teacher=request.user,
            name=serializer.validated_data["name"],
            code=_unique_class_code(),
        )
        return Response(ClassroomSerializer(classroom).data, status=status.HTTP_201_CREATED)


class JoinClassView(APIView):
    """POST { code } : l'utilisateur rejoint la classe correspondante."""

    permission_classes = [IsAuthenticated]

    @extend_schema(request=JoinClassSerializer, responses={200: ClassroomSerializer})
    def post(self, request):
        serializer = JoinClassSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        code = serializer.validated_data["code"]
        try:
            classroom = Classroom.objects.get(code=code)
        except Classroom.DoesNotExist:
            return Response(
                {"detail": "Code de classe invalide."},
                status=status.HTTP_404_NOT_FOUND,
            )
        classroom.students.add(request.user)
        return Response(ClassroomSerializer(classroom).data)


class ClassroomDetailView(APIView):
    """GET : détail d'une classe + liste des élèves (enseignant propriétaire)."""

    permission_classes = [IsAuthenticated, IsTeacher]

    @extend_schema(responses={200: OpenApiResponse(description="Classe + élèves")})
    def get(self, request, pk: int):
        classroom = get_object_or_404(Classroom, pk=pk, teacher=request.user)
        data = ClassroomSerializer(classroom).data
        data["students"] = [
            {
                "id": s.id,
                "name": s.get_full_name() or s.username,
                "email": s.email,
            }
            for s in classroom.students.all()
        ]
        return Response(data)


# ---------------------------------------------------------------------------
# Release 2 — Espace prof : suivi de la progression des élèves d'une classe
# ---------------------------------------------------------------------------


def _get_owned_classroom_or_404(user, class_id: int) -> Classroom:
    """Récupère la classe `class_id` UNIQUEMENT si `user` en est le teacher.

    SÉCURITÉ : le filtre `teacher=user` garantit qu'un enseignant ne peut jamais
    ouvrir la progression d'une classe qu'il ne possède pas — on renvoie 404
    (et non 403) pour ne pas divulguer l'existence de la classe.
    """
    return get_object_or_404(Classroom, pk=class_id, teacher=user)


class ClassProgressView(APIView):
    """GET /api/classes/<class_id>/progress/ — progression des élèves de la classe.

    Réservé à l'enseignant PROPRIÉTAIRE de la classe (404 sinon). Pour chaque
    élève de la classe, on agrège ses `Attempt` (tous quizzes confondus) en KPIs
    (nombre de quiz passés, moyenne, meilleur / dernier score) et en une liste
    `evolution` triée chronologiquement — même logique d'agrégation que
    `StatsView`, mais côté enseignant et par élève.
    """

    permission_classes = [IsAuthenticated, IsTeacher]

    @extend_schema(
        responses={200: ClassProgressStudentSerializer(many=True)},
        description=(
            "Progression de chaque élève de la classe (KPIs + évolution "
            "chronologique). Enseignant propriétaire uniquement (404 sinon)."
        ),
    )
    def get(self, request, class_id: int):
        classroom = _get_owned_classroom_or_404(request.user, class_id)

        # On récupère toutes les tentatives des élèves de la classe en une seule
        # requête (select_related pour éviter le N+1 sur quiz.title), puis on
        # regroupe en Python par élève — tri chronologique global.
        students = list(classroom.students.all())
        attempts_by_student: dict[int, list[Attempt]] = {s.id: [] for s in students}
        attempts = (
            Attempt.objects.filter(student__in=students)
            .select_related("quiz")
            .order_by("created_at", "id")
        )
        for attempt in attempts:
            # Un élève a pu quitter la classe entre-temps : on ne garde que les
            # tentatives des élèves actuellement membres.
            if attempt.student_id in attempts_by_student:
                attempts_by_student[attempt.student_id].append(attempt)

        payload = []
        for student in students:
            student_attempts = attempts_by_student[student.id]
            evolution = [
                {
                    "attempt_id": a.id,
                    "quiz_id": a.quiz_id,
                    "quiz_title": a.quiz.title,
                    "number": a.number,
                    "score": a.score,
                    "total": a.total,
                    "created_at": a.created_at,
                }
                for a in student_attempts
            ]
            # `quizzes_taken` = tentatives avec un score renseigné (comme StatsView).
            scored = [a.score for a in student_attempts if a.score is not None]
            payload.append(
                {
                    "student": StudentIdentitySerializer(student).data,
                    "quizzes_taken": len(scored),
                    "average_score": round(sum(scored) / len(scored), 1) if scored else None,
                    "best_score": max(scored) if scored else None,
                    "last_score": scored[-1] if scored else None,
                    "evolution": evolution,
                }
            )

        return Response(payload)


class StudentAttemptDetailView(APIView):
    """GET /api/classes/<class_id>/students/<student_id>/attempts/<attempt_id>/

    Détail d'une tentative (avec ses réponses) d'un élève, pour l'enseignant.

    SÉCURITÉ (triple contrôle, sinon 404) :
      1. la classe `class_id` appartient à l'enseignant connecté ;
      2. l'élève `student_id` est membre de cette classe ;
      3. la tentative `attempt_id` appartient bien à cet élève.
    """

    permission_classes = [IsAuthenticated, IsTeacher]

    @extend_schema(
        responses={200: AttemptDetailSerializer},
        description=(
            "Détail (réponses) d'une tentative d'un élève de la classe. "
            "Autorisé seulement si la classe appartient à l'enseignant, que "
            "l'élève est membre de la classe et que la tentative est la sienne "
            "(404 sinon)."
        ),
    )
    def get(self, request, class_id: int, student_id: int, attempt_id: int):
        # 1. La classe doit appartenir à l'enseignant connecté.
        classroom = _get_owned_classroom_or_404(request.user, class_id)
        # 2. L'élève doit être membre de CETTE classe.
        if not classroom.students.filter(pk=student_id).exists():
            return Response(
                {"detail": "Élève introuvable dans cette classe."},
                status=status.HTTP_404_NOT_FOUND,
            )
        # 3. La tentative doit appartenir à cet élève.
        attempt = get_object_or_404(Attempt, pk=attempt_id, student_id=student_id)
        return Response(AttemptDetailSerializer(attempt).data)
