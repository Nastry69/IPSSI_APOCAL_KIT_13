"""
Endpoints LLM :
    GET  /api/llm/ping/               — vérifie l'intégration Ollama
    POST /api/llm/generate-quiz/      — génère un quiz à partir d'un PDF ou d'un texte
    POST /api/llm/generate-note/      — génère une fiche de révision (kind=note)
    POST /api/llm/generate-summary/   — génère un résumé (kind=summary)
    GET  /api/llm/study-docs/         — liste les documents de révision du user
    GET  /api/llm/study-docs/<id>/    — détail d'un document (scopé par owner)
"""

import requests
from django.conf import settings
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from quizzes.models import Question, Quiz, StudyDoc
from quizzes.serializers import QuizSerializer

from .pdf_utils import PDFError, extract_text_from_pdf
from .serializers import (
    GenerateQuizSerializer,
    GenerateStudyDocSerializer,
    StudyDocSerializer,
)
from .services import get_llm_client
from .services.base import LLMError
from .services.quiz_prompt import QuizValidationError


class PingView(APIView):
    """Vérifie que le backend voit Ollama (ou que le mock répond)."""

    permission_classes = [AllowAny]

    @extend_schema(
        responses={200: OpenApiResponse(description="{ backend, model, ollama_alive, message }")},
        description="Ping LLM — utile pour vérifier l'intégration Ollama.",
    )
    def get(self, _request):
        # Config EFFECTIVE (base prioritaire, repli .env) — Lot 8.
        from .services.factory import resolve_active

        conf = resolve_active()
        backend = conf["backend"]

        if backend == "mock":
            return Response(
                {
                    "backend": "mock",
                    "model": "mock-model",
                    "ollama_alive": False,
                    "message": "Mock LLM actif (choisissez un autre fournisseur dans l'admin).",
                }
            )

        if backend != "ollama":
            # Backend cloud : pas de ping HTTP ici (éviter de consommer du quota).
            return Response(
                {
                    "backend": backend,
                    "model": conf["model"],
                    "message": f"Backend cloud « {backend} » configuré.",
                }
            )

        host = conf["ollama_host"] or settings.OLLAMA_HOST
        model = conf["model"] or settings.OLLAMA_MODEL
        try:
            resp = requests.get(f"{host}/api/tags", timeout=2)
            resp.raise_for_status()
            tags = resp.json().get("models", [])
            target = model.split(":")[0]
            model_present = any(m.get("name", "").startswith(target) for m in tags)
            return Response(
                {
                    "backend": "ollama",
                    "model": model,
                    "ollama_alive": True,
                    "model_loaded": model_present,
                    "message": (
                        "Ollama répond ✓"
                        if model_present
                        else f"Ollama répond mais le modèle {model} n'est pas téléchargé. "
                        "Lancez : make pull-model"
                    ),
                }
            )
        except requests.RequestException as exc:
            return Response(
                {
                    "backend": "ollama",
                    "model": model,
                    "ollama_alive": False,
                    "message": f"Ollama injoignable : {exc}",
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )


# Nombre de tentatives de génération si la sortie LLM est structurellement
# invalide (défense J3 : valider → rejeter → retenter). On NE retente PAS les
# erreurs d'indisponibilité (réseau).
MAX_GENERATION_ATTEMPTS = 2


class GenerateQuizView(APIView):
    """Génère un quiz de 10 QCM à partir d'un PDF ou d'un texte collé."""

    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    @extend_schema(
        request=GenerateQuizSerializer,
        responses={201: QuizSerializer},
        description=(
            "Génère 10 QCM à partir d'un cours. Fournir soit `pdf` (multipart) "
            "soit `source_text` (≥ 200 caractères). Le quiz est sauvegardé en "
            "DB et associé à l'utilisateur connecté."
        ),
    )
    def post(self, request):
        # Lot 8 : si l'admin exige un email vérifié, on bloque sinon.
        from accounts.models import get_or_create_profile
        from administration.models import SiteConfig

        if (
            SiteConfig.load().require_email_verification
            and not get_or_create_profile(request.user).email_verified
        ):
            return Response(
                {"detail": "Veuillez confirmer votre adresse email avant de générer un quiz."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = GenerateQuizSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        title = serializer.validated_data["title"]
        pdf_file = serializer.validated_data.get("pdf")
        source_text = (serializer.validated_data.get("source_text") or "").strip()
        difficulty = serializer.validated_data.get("difficulty", "medium")
        num_questions = serializer.validated_data.get("num_questions", 10)
        theme = serializer.validated_data.get("theme", "") or ""

        # 1. Extraction du texte source
        if pdf_file:
            try:
                source_text = extract_text_from_pdf(pdf_file)
            except PDFError as exc:
                return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        # 2. Appel LLM (Ollama ou Mock) avec RE-TENTATIVE si la sortie est
        # structurellement invalide (défense J3 : « valider, rejeter, retenter »).
        questions_data = None
        last_error: QuizValidationError | None = None
        for _attempt in range(MAX_GENERATION_ATTEMPTS):
            try:
                questions_data = get_llm_client().generate_quiz(
                    source_text=source_text,
                    title=title,
                    num_questions=num_questions,
                    difficulty=difficulty,
                    theme=theme,
                )
                break
            except QuizValidationError as exc:
                last_error = exc  # sortie non conforme : on retente
                continue
            except LLMError as exc:
                # Indisponibilité (réseau) : inutile de retenter.
                return Response(
                    {"detail": f"Échec génération LLM : {exc}"},
                    status=status.HTTP_502_BAD_GATEWAY,
                )
        if questions_data is None:
            return Response(
                {
                    "detail": (
                        f"Sortie LLM invalide après {MAX_GENERATION_ATTEMPTS} tentatives : "
                        f"{last_error}"
                    )
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )

        # 3. Persistance — Quiz + 10 Questions dans une transaction
        from django.db import transaction

        with transaction.atomic():
            quiz = Quiz.objects.create(
                user=request.user,
                title=title,
                source_text=source_text,
                difficulty=difficulty,
                num_questions=num_questions,
                theme=theme,
            )
            for i, q in enumerate(questions_data, start=1):
                Question.objects.create(
                    quiz=quiz,
                    index=i,
                    prompt=q["prompt"],
                    options=q["options"],
                    correct_index=q["correct_index"],
                )

        return Response(QuizSerializer(quiz).data, status=status.HTTP_201_CREATED)


# ---------------------------------------------------------------------------
# Release 2 — Documents de révision (fiche de révision / résumé) en texte libre.
# ---------------------------------------------------------------------------


class _GenerateStudyDocView(APIView):
    """Base commune aux endpoints generate-note / generate-summary.

    Même flux que GenerateQuizView (extraction texte, garde email vérifié)
    mais appelle `generate_text(kind=...)` et persiste un StudyDoc.
    Les sous-classes fixent `kind` (« note » ou « summary »).
    """

    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    kind: str = ""

    def post(self, request):
        # Même garde que la génération de quiz (Lot 8) : email vérifié si exigé.
        from accounts.models import get_or_create_profile
        from administration.models import SiteConfig

        if (
            SiteConfig.load().require_email_verification
            and not get_or_create_profile(request.user).email_verified
        ):
            return Response(
                {"detail": "Veuillez confirmer votre adresse email avant de générer un document."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = GenerateStudyDocSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        title = serializer.validated_data["title"]
        pdf_file = serializer.validated_data.get("pdf")
        source_text = (serializer.validated_data.get("source_text") or "").strip()

        # 1. Extraction du texte source (PDF prioritaire).
        if pdf_file:
            try:
                source_text = extract_text_from_pdf(pdf_file)
            except PDFError as exc:
                return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        # 2. Génération de TEXTE libre (pas de re-tentative « validation JSON » :
        # la sortie n'est pas structurée). On rattrape seulement l'indisponibilité.
        try:
            content = get_llm_client().generate_text(
                source_text=source_text,
                title=title,
                kind=self.kind,
            )
        except LLMError as exc:
            return Response(
                {"detail": f"Échec génération LLM : {exc}"},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        if not content or not content.strip():
            return Response(
                {"detail": "Le LLM a renvoyé un document vide."},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        # 3. Persistance du document.
        study_doc = StudyDoc.objects.create(
            owner=request.user,
            kind=self.kind,
            title=title,
            content=content,
        )
        return Response(StudyDocSerializer(study_doc).data, status=status.HTTP_201_CREATED)


class GenerateNoteView(_GenerateStudyDocView):
    """Génère une fiche de révision (kind=note) à partir d'un PDF ou d'un texte."""

    kind = StudyDoc.Kind.NOTE

    @extend_schema(
        request=GenerateStudyDocSerializer,
        responses={201: StudyDocSerializer},
        description=(
            "Génère une fiche de révision (markdown) à partir d'un cours. "
            "Fournir soit `pdf` (multipart) soit `source_text` (≥ 200 caractères). "
            "Le document est sauvegardé et associé à l'utilisateur connecté."
        ),
    )
    def post(self, request):
        return super().post(request)


class GenerateSummaryView(_GenerateStudyDocView):
    """Génère un résumé (kind=summary) à partir d'un PDF ou d'un texte."""

    kind = StudyDoc.Kind.SUMMARY

    @extend_schema(
        request=GenerateStudyDocSerializer,
        responses={201: StudyDocSerializer},
        description=(
            "Génère un résumé structuré (markdown) à partir d'un cours. "
            "Fournir soit `pdf` (multipart) soit `source_text` (≥ 200 caractères). "
            "Le document est sauvegardé et associé à l'utilisateur connecté."
        ),
    )
    def post(self, request):
        return super().post(request)


class StudyDocListView(ListAPIView):
    """GET /api/llm/study-docs/ — liste les documents de révision du user connecté."""

    serializer_class = StudyDocSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None  # liste brute (contrat frontend + tests)

    def get_queryset(self):
        return StudyDoc.objects.filter(owner=self.request.user)


class StudyDocDetailView(RetrieveAPIView):
    """GET /api/llm/study-docs/<id>/ — détail d'un document (scopé par owner → 404)."""

    serializer_class = StudyDocSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return StudyDoc.objects.filter(owner=self.request.user)
