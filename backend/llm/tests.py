"""Tests pour l'app llm — K1 (ping) + K2 (generate-quiz).

Complété par les tests de FIABILISATION :
  - F2 : extraction / limites PDF (llm/pdf_utils.py)
  - F3 : validation du quiz (llm/services/quiz_prompt.py)

Ces tests verrouillent le comportement ACTUEL du code (ils ne le corrigent pas).
"""

import io
import json

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from pypdf import PdfReader, PdfWriter
from pypdf.generic import (
    DecodedStreamObject,
    DictionaryObject,
    NameObject,
)
from rest_framework.test import APIClient

from quizzes.models import Quiz, StudyDoc

from .pdf_utils import MAX_PDF_SIZE_BYTES, PDFError, extract_text_from_pdf
from .serializers import GenerateQuizSerializer
from .services.base import LLMError
from .services.quiz_prompt import parse_and_validate_quiz

User = get_user_model()

pytestmark = pytest.mark.django_db


@pytest.fixture
def auth_client() -> APIClient:
    user = User.objects.create_user(username="alice", password="motdepasse123")
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@override_settings(LLM_BACKEND="mock")
def test_ping_in_mock_mode():
    response = APIClient().get("/api/llm/ping/")
    assert response.status_code == 200
    assert response.data["backend"] == "mock"


@override_settings(LLM_BACKEND="mock")
def test_generate_quiz_with_text(auth_client):
    response = auth_client.post(
        "/api/llm/generate-quiz/",
        {
            "title": "Mon cours de test",
            "source_text": "Lorem ipsum " * 50,
        },
        format="multipart",
    )
    assert response.status_code == 201, response.data
    assert response.data["title"] == "Mon cours de test"
    assert len(response.data["questions"]) == 10
    assert Quiz.objects.filter(title="Mon cours de test").count() == 1


@override_settings(LLM_BACKEND="mock")
def test_generate_quiz_requires_text_or_pdf(auth_client):
    response = auth_client.post(
        "/api/llm/generate-quiz/",
        {"title": "Sans contenu"},
        format="multipart",
    )
    assert response.status_code == 400


@override_settings(LLM_BACKEND="mock")
def test_generate_quiz_rejects_short_text(auth_client):
    response = auth_client.post(
        "/api/llm/generate-quiz/",
        {"title": "Trop court", "source_text": "Court"},
        format="multipart",
    )
    assert response.status_code == 400


def test_generate_quiz_requires_auth():
    response = APIClient().post(
        "/api/llm/generate-quiz/",
        {"title": "X", "source_text": "x" * 200},
        format="multipart",
    )
    assert response.status_code in (401, 403)


# ===========================================================================
# F2 — Extraction / limites PDF (llm/pdf_utils.py)
# Tests unitaires DIRECTS de extract_text_from_pdf. Ces tests verrouillent le
# comportement actuel : texte extrait, tailles, chiffrement, PDF scanné/vide.
# ===========================================================================


def _make_text_pdf(text: str = "Contenu de cours extractible pour test") -> bytes:
    """Construit un vrai PDF d'une page contenant du texte EXTRACTIBLE.

    reportlab n'est pas disponible dans l'environnement de test ; on assemble
    donc la page à la main avec pypdf : une page vierge + un content stream qui
    dessine le texte (opérateur `Tj`) + une ressource police Helvetica. pypdf
    ré-extrait bien ce texte via page.extract_text().
    """
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)

    # Content stream : BT ... Tj ET dessine `text` à la position (72, 720).
    escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    content = f"BT /F1 24 Tf 72 720 Td ({escaped}) Tj ET".encode("latin-1")
    stream = DecodedStreamObject()
    stream.set_data(content)
    stream_ref = writer._add_object(stream)
    page[NameObject("/Contents")] = stream_ref

    # Ressource police référencée par /F1 dans le content stream.
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    font_ref = writer._add_object(font)
    page[NameObject("/Resources")] = DictionaryObject(
        {NameObject("/Font"): DictionaryObject({NameObject("/F1"): font_ref})}
    )

    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def _make_blank_pdf() -> bytes:
    """PDF valide d'une page SANS aucun texte (simule un scan / page image)."""
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def _make_encrypted_pdf(password: str = "secret") -> bytes:
    """PDF valide chiffré (protégé par mot de passe)."""
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    writer.encrypt(password)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def test_pdf_extract_helper_is_extractable():
    """Garde-fou : le PDF construit par _make_text_pdf est bien lisible par pypdf.

    (Sanity check du helper lui-même — évite un faux positif où l'extraction
    « échoue » à cause du helper et non du code testé.)
    """
    reader = PdfReader(io.BytesIO(_make_text_pdf("Sanity check")))
    assert reader.is_encrypted is False
    assert "Sanity check" in (reader.pages[0].extract_text() or "")


def test_extract_text_from_valid_pdf_bytes():
    """F2 : un PDF valide avec texte -> l'extraction renvoie le texte."""
    pdf_bytes = _make_text_pdf("Bonjour cours extractible")
    result = extract_text_from_pdf(pdf_bytes)  # accepte les bytes directement
    assert "Bonjour cours extractible" in result


def test_extract_text_from_valid_pdf_file_object():
    """F2 : même chose via un file-like (SimpleUploadedFile, comme request.FILES)."""
    upload = SimpleUploadedFile(
        "cours.pdf",
        _make_text_pdf("Texte via fichier uploade"),
        content_type="application/pdf",
    )
    result = extract_text_from_pdf(upload)
    assert "Texte via fichier uploade" in result


def test_extract_text_rejects_oversized_pdf():
    """F2 : un fichier > 5 Mo (MAX_PDF_SIZE_BYTES) -> PDFError.

    Le contrôle de taille se fait sur `.size` AVANT tout parsing : le contenu
    n'a donc pas besoin d'être un PDF valide, seul le dépassement compte.
    """
    oversized = SimpleUploadedFile(
        "gros.pdf",
        b"%PDF-1.4\n" + b"0" * (MAX_PDF_SIZE_BYTES + 1),
        content_type="application/pdf",
    )
    assert oversized.size > MAX_PDF_SIZE_BYTES
    with pytest.raises(PDFError):
        extract_text_from_pdf(oversized)


def test_extract_text_accepts_pdf_at_size_limit():
    """F2 : un PDF pile à la limite (== MAX_PDF_SIZE_BYTES) n'est PAS rejeté
    pour la taille (la borne est un `>` strict). Il échoue ensuite au parsing
    (contenu non-PDF) -> PDFError « Impossible d'ouvrir »."""
    at_limit = SimpleUploadedFile(
        "limite.pdf",
        b"x" * MAX_PDF_SIZE_BYTES,
        content_type="application/pdf",
    )
    assert at_limit.size == MAX_PDF_SIZE_BYTES
    with pytest.raises(PDFError) as excinfo:
        extract_text_from_pdf(at_limit)
    # Ce n'est PAS l'erreur de taille : la borne stricte laisse passer == limite.
    assert "trop volumineux" not in str(excinfo.value)


def test_extract_text_rejects_encrypted_pdf():
    """F2 : un PDF chiffré (protégé par mot de passe) -> PDFError."""
    with pytest.raises(PDFError) as excinfo:
        extract_text_from_pdf(_make_encrypted_pdf())
    assert "mot de passe" in str(excinfo.value).lower()


def test_extract_text_rejects_scanned_or_empty_pdf():
    """F2 : un PDF valide sans texte extractible (scanné/vide) -> PDFError."""
    with pytest.raises(PDFError) as excinfo:
        extract_text_from_pdf(_make_blank_pdf())
    assert "extractible" in str(excinfo.value).lower()


def test_extract_text_rejects_corrupted_pdf():
    """F2 : un contenu qui n'est pas un PDF ouvrable -> PDFError.

    (Verrouille la branche `except Exception -> PDFError` autour de PdfReader.)
    """
    with pytest.raises(PDFError):
        extract_text_from_pdf(b"ceci n'est pas un pdf du tout")


def test_serializer_rejects_non_pdf_extension():
    """F2 : extension non .pdf -> rejet côté serializer (avant toute extraction).

    On teste le serializer DIRECTEMENT (pas d'appel HTTP -> aucun throttling).
    """
    upload = SimpleUploadedFile(
        "cours.txt",
        b"contenu quelconque",
        content_type="text/plain",
    )
    serializer = GenerateQuizSerializer(data={"title": "Cours", "pdf": upload})
    assert serializer.is_valid() is False
    assert "pdf" in serializer.errors


def test_serializer_accepts_pdf_extension_case_insensitive():
    """F2 : l'extension .PDF (majuscules) est acceptée (validation `.lower()`)."""
    upload = SimpleUploadedFile(
        "COURS.PDF",
        _make_text_pdf("peu importe"),
        content_type="application/pdf",
    )
    serializer = GenerateQuizSerializer(data={"title": "Cours", "pdf": upload})
    assert serializer.is_valid() is True, serializer.errors


# ===========================================================================
# F3 — Validation du quiz (llm/services/quiz_prompt.parse_and_validate_quiz)
# Tests unitaires DIRECTS. Verrouillent : 10 questions exactes, troncature si
# > 10, LLMError si < 10, 4 options, correct_index dans 0..3.
# ===========================================================================


def _valid_question(i: int = 0) -> dict:
    """Une question valide : prompt non vide, 4 options, correct_index 0..3."""
    return {
        "prompt": f"Question {i} ?",
        "options": ["Option A", "Option B", "Option C", "Option D"],
        "correct_index": i % 4,
    }


def _quiz_payload(n: int) -> dict:
    """Payload dict {'questions': [...]} avec `n` questions valides."""
    return {"questions": [_valid_question(i) for i in range(n)]}


def _quiz_json(n: int) -> str:
    """Même chose sérialisé en JSON (entrée réelle de parse_and_validate_quiz)."""

    return json.dumps(_quiz_payload(n))


def test_parse_valid_10_questions():
    """F3 : payload de 10 questions valides -> ok (10 questions nettoyées)."""
    cleaned = parse_and_validate_quiz(_quiz_json(10))
    assert isinstance(cleaned, list)
    assert len(cleaned) == 10
    first = cleaned[0]
    assert set(first.keys()) == {"prompt", "options", "correct_index"}
    assert len(first["options"]) == 4
    assert first["correct_index"] in (0, 1, 2, 3)


def test_parse_truncates_more_than_10_questions():
    """F3 : payload > 10 -> tronqué à 10 (tolérance du code actuel)."""
    cleaned = parse_and_validate_quiz(_quiz_json(15))
    assert len(cleaned) == 10


def test_parse_raises_on_fewer_than_10_questions():
    """F3 : payload < 10 -> LLMError."""
    with pytest.raises(LLMError):
        parse_and_validate_quiz(_quiz_json(9))


def test_parse_raises_on_wrong_option_count():
    """F3 : une question sans exactement 4 options -> LLMError."""
    payload = _quiz_payload(10)
    payload["questions"][3]["options"] = ["Une", "Deux", "Trois"]  # 3 options

    with pytest.raises(LLMError):
        parse_and_validate_quiz(json.dumps(payload))


def test_parse_raises_on_correct_index_out_of_range():
    """F3 : correct_index hors 0..3 -> LLMError."""
    payload = _quiz_payload(10)
    payload["questions"][0]["correct_index"] = 4  # hors bornes

    with pytest.raises(LLMError):
        parse_and_validate_quiz(json.dumps(payload))


def test_parse_raises_on_negative_correct_index():
    """F3 : correct_index négatif -> LLMError (borne basse)."""
    payload = _quiz_payload(10)
    payload["questions"][0]["correct_index"] = -1

    with pytest.raises(LLMError):
        parse_and_validate_quiz(json.dumps(payload))


def test_parse_extracts_json_wrapped_in_text():
    """F3 : le JSON entouré de texte parasite est quand même extrait (fallback
    regex du premier bloc { ... })."""
    raw = "Voici votre quiz :\n" + _quiz_json(10) + "\nFin de la réponse."
    cleaned = parse_and_validate_quiz(raw)
    assert len(cleaned) == 10


def test_parse_raises_on_empty_response():
    """F3 : réponse vide -> LLMError."""
    with pytest.raises(LLMError):
        parse_and_validate_quiz("   ")


def test_parse_raises_on_non_json():
    """F3 : aucune structure JSON -> LLMError."""
    with pytest.raises(LLMError):
        parse_and_validate_quiz("pas du tout du json")


def test_parse_raises_on_missing_questions_key():
    """F3 : JSON valide mais sans clé 'questions' -> LLMError."""
    with pytest.raises(LLMError):
        parse_and_validate_quiz('{"autre_cle": []}')


def test_parse_strips_whitespace_in_prompt_and_options():
    """F3 : verrouille le nettoyage — prompt/options sont strip()és en sortie."""
    payload = _quiz_payload(10)
    payload["questions"][0]["prompt"] = "  Question espacee  "
    payload["questions"][0]["options"] = ["  A  ", "B ", " C", "D"]

    cleaned = parse_and_validate_quiz(json.dumps(payload))
    assert cleaned[0]["prompt"] == "Question espacee"
    assert cleaned[0]["options"] == ["A", "B", "C", "D"]


# ===========================================================================
# Release 2 — Documents de révision : fiche de révision (note) & résumé (summary)
# Endpoints generate-note / generate-summary + study-docs (liste / détail).
# ===========================================================================

_LONG_TEXT = "Lorem ipsum dolor sit amet " * 20  # > 200 caractères


@override_settings(LLM_BACKEND="mock")
def test_generate_note_creates_studydoc(auth_client):
    response = auth_client.post(
        "/api/llm/generate-note/",
        {"title": "Ma fiche de cours", "source_text": _LONG_TEXT},
        format="multipart",
    )
    assert response.status_code == 201, response.data
    assert response.data["kind"] == "note"
    assert response.data["title"] == "Ma fiche de cours"
    assert response.data["content"].strip()
    assert set(response.data.keys()) == {"id", "kind", "title", "content", "created_at"}
    doc = StudyDoc.objects.get(id=response.data["id"])
    assert doc.kind == StudyDoc.Kind.NOTE
    assert doc.title == "Ma fiche de cours"


@override_settings(LLM_BACKEND="mock")
def test_generate_summary_creates_studydoc(auth_client):
    response = auth_client.post(
        "/api/llm/generate-summary/",
        {"title": "Mon résumé", "source_text": _LONG_TEXT},
        format="multipart",
    )
    assert response.status_code == 201, response.data
    assert response.data["kind"] == "summary"
    assert StudyDoc.objects.filter(title="Mon résumé", kind=StudyDoc.Kind.SUMMARY).count() == 1


@override_settings(LLM_BACKEND="mock")
def test_generate_note_rejects_short_text(auth_client):
    response = auth_client.post(
        "/api/llm/generate-note/",
        {"title": "Trop court", "source_text": "Court"},
        format="multipart",
    )
    assert response.status_code == 400
    assert StudyDoc.objects.count() == 0


@override_settings(LLM_BACKEND="mock")
def test_generate_summary_requires_text_or_pdf(auth_client):
    response = auth_client.post(
        "/api/llm/generate-summary/",
        {"title": "Sans contenu"},
        format="multipart",
    )
    assert response.status_code == 400


def test_generate_note_requires_auth():
    response = APIClient().post(
        "/api/llm/generate-note/",
        {"title": "X", "source_text": "x" * 200},
        format="multipart",
    )
    assert response.status_code in (401, 403)


def test_generate_summary_requires_auth():
    response = APIClient().post(
        "/api/llm/generate-summary/",
        {"title": "X", "source_text": "x" * 200},
        format="multipart",
    )
    assert response.status_code in (401, 403)


@override_settings(LLM_BACKEND="mock")
def test_study_docs_list_and_detail(auth_client):
    # Crée une fiche et un résumé pour l'utilisateur authentifié.
    note = auth_client.post(
        "/api/llm/generate-note/",
        {"title": "Fiche A", "source_text": _LONG_TEXT},
        format="multipart",
    ).data
    auth_client.post(
        "/api/llm/generate-summary/",
        {"title": "Résumé B", "source_text": _LONG_TEXT},
        format="multipart",
    )

    # Liste : les deux documents du user.
    listing = auth_client.get("/api/llm/study-docs/")
    assert listing.status_code == 200
    ids = {d["id"] for d in listing.data}
    assert note["id"] in ids
    assert len(listing.data) == 2

    # Détail : même forme que le contrat frontend.
    detail = auth_client.get(f"/api/llm/study-docs/{note['id']}/")
    assert detail.status_code == 200
    assert detail.data["id"] == note["id"]
    assert detail.data["kind"] == "note"
    assert set(detail.data.keys()) == {"id", "kind", "title", "content", "created_at"}


def test_study_docs_requires_auth():
    response = APIClient().get("/api/llm/study-docs/")
    assert response.status_code in (401, 403)


@override_settings(LLM_BACKEND="mock")
def test_study_doc_detail_is_scoped_by_owner():
    """Un document d'un autre utilisateur → 404 (isolation par owner)."""
    owner = User.objects.create_user(username="bob", password="motdepasse123")
    doc = StudyDoc.objects.create(
        owner=owner,
        kind=StudyDoc.Kind.NOTE,
        title="Privé de Bob",
        content="# secret",
    )

    intruder = User.objects.create_user(username="mallory", password="motdepasse123")
    client = APIClient()
    client.force_authenticate(user=intruder)

    # Détail scopé : 404 pour un doc qui ne lui appartient pas.
    assert client.get(f"/api/llm/study-docs/{doc.id}/").status_code == 404
    # Liste : ne voit pas le doc de Bob.
    listing = client.get("/api/llm/study-docs/")
    assert listing.status_code == 200
    assert listing.data == []
