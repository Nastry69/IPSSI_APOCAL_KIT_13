"""
Tests ciblés du FALLBACK LLM (F3 — Mistral par défaut + Groq en secours).

On vérifie SANS réseau ni vraie clé :
  1. Le wrapper FallbackLLMClient : délègue au primaire, bascule sur le secours
     en cas d'échec de disponibilité, NE bascule PAS sur une QuizValidationError
     (contrat de re-tentative de la vue, défense J3), et remonte une LLMError
     claire si les deux échouent.
  2. Le câblage de get_llm_client() : PAS de wrapper en mode mock (les tests
     forcent LLM_BACKEND=mock), et un wrapper quand primaire=cloud + secours
     configuré avec une clé.

Ces tests sont volontairement séparés de tests.py (géré ailleurs).
"""

import pytest
from django.test import override_settings

from llm.services.base import LLMClient, LLMError
from llm.services.factory import (
    FallbackLLMClient,
    get_llm_client,
    resolve_fallback,
)
from llm.services.mock_client import MockLLMClient
from llm.services.quiz_prompt import QuizValidationError

# resolve_fallback() / get_llm_client() lisent LLMConfig en base -> django_db.
pytestmark = pytest.mark.django_db


# --------------------------------------------------------------------------- #
# Doubles de test (clients factices, sans réseau).
# --------------------------------------------------------------------------- #
class _OkClient(LLMClient):
    """Client qui réussit toujours et signe ses réponses (name)."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.quiz_calls = 0
        self.text_calls = 0

    def generate_quiz(self, source_text, title, *, num_questions=10, difficulty="medium", theme=""):
        self.quiz_calls += 1
        return [{"from": self.name, "num": num_questions, "difficulty": difficulty, "theme": theme}]

    def generate_text(self, source_text, title, kind):
        self.text_calls += 1
        return f"{self.name}:{kind}"


class _BoomClient(LLMClient):
    """Client qui échoue toujours avec l'exception fournie."""

    def __init__(self, exc: Exception) -> None:
        self.exc = exc
        self.quiz_calls = 0
        self.text_calls = 0

    def generate_quiz(self, source_text, title, *, num_questions=10, difficulty="medium", theme=""):
        self.quiz_calls += 1
        raise self.exc

    def generate_text(self, source_text, title, kind):
        self.text_calls += 1
        raise self.exc


# --------------------------------------------------------------------------- #
# 1. FallbackLLMClient (unitaire, pas de config/DB).
# --------------------------------------------------------------------------- #
def test_wrapper_uses_primary_when_it_succeeds():
    primary, backup = _OkClient("primary"), _OkClient("backup")
    wrapped = FallbackLLMClient(primary, backup, backup_name="groq")

    result = wrapped.generate_quiz("texte source", "Titre", num_questions=5, difficulty="hard")

    assert result[0]["from"] == "primary"
    assert result[0]["num"] == 5 and result[0]["difficulty"] == "hard"
    assert primary.quiz_calls == 1 and backup.quiz_calls == 0


def test_wrapper_falls_back_on_llmerror():
    primary = _BoomClient(LLMError("Groq indisponible (réseau)"))
    backup = _OkClient("backup")
    wrapped = FallbackLLMClient(primary, backup, backup_name="groq")

    result = wrapped.generate_quiz("texte source", "Titre")

    assert result[0]["from"] == "backup"
    assert primary.quiz_calls == 1 and backup.quiz_calls == 1


def test_wrapper_falls_back_on_generate_text_too():
    primary = _BoomClient(LLMError("timeout"))
    backup = _OkClient("backup")
    wrapped = FallbackLLMClient(primary, backup, backup_name="groq")

    assert wrapped.generate_text("texte", "Titre", "note") == "backup:note"
    assert backup.text_calls == 1


def test_wrapper_falls_back_on_unexpected_exception():
    # Exception réseau « brute » (pas une LLMError) -> bascule quand même.
    primary = _BoomClient(ConnectionError("connexion refusée"))
    backup = _OkClient("backup")
    wrapped = FallbackLLMClient(primary, backup, backup_name="groq")

    assert wrapped.generate_quiz("texte", "Titre")[0]["from"] == "backup"


def test_wrapper_does_not_fall_back_on_quiz_validation_error():
    # QuizValidationError = QUALITÉ de sortie : la vue re-tente sur le MÊME
    # backend. Le wrapper doit la relayer telle quelle, SANS toucher au secours.
    primary = _BoomClient(QuizValidationError("sortie non conforme"))
    backup = _OkClient("backup")
    wrapped = FallbackLLMClient(primary, backup, backup_name="groq")

    with pytest.raises(QuizValidationError):
        wrapped.generate_quiz("texte", "Titre")
    assert backup.quiz_calls == 0


def test_wrapper_raises_llmerror_when_both_fail():
    primary = _BoomClient(LLMError("primaire KO"))
    backup = _BoomClient(LLMError("secours KO"))
    wrapped = FallbackLLMClient(primary, backup, backup_name="groq")

    with pytest.raises(LLMError) as exc_info:
        wrapped.generate_quiz("texte", "Titre")
    msg = str(exc_info.value)
    assert "primaire KO" in msg and "secours KO" in msg


# --------------------------------------------------------------------------- #
# 2. Câblage get_llm_client() / resolve_fallback() via settings.
# --------------------------------------------------------------------------- #
@override_settings(LLM_BACKEND="mock", LLM_FALLBACK_BACKEND="groq")
def test_no_fallback_in_mock_mode():
    # En mode mock (tests), AUCUN fallback : client mock nu, pas de wrapper.
    assert resolve_fallback() is None
    client = get_llm_client()
    assert isinstance(client, MockLLMClient)
    assert not isinstance(client, FallbackLLMClient)


@override_settings(LLM_BACKEND="ollama", LLM_FALLBACK_BACKEND="groq", GROQ_API_KEY="k-test")
def test_no_fallback_when_primary_is_ollama():
    # Ollama (local/souverain) : pas de bascule cloud à son insu.
    assert resolve_fallback() is None


@override_settings(LLM_BACKEND="mistral", LLM_FALLBACK_BACKEND="groq", GROQ_API_KEY="")
def test_no_fallback_when_backup_has_no_key():
    # Secours sans clé -> pas de wrapper : l'erreur primaire remontera telle quelle.
    assert resolve_fallback() is None


@override_settings(LLM_BACKEND="mistral", LLM_FALLBACK_BACKEND="mistral", MISTRAL_API_KEY="k")
def test_no_fallback_when_backup_equals_primary():
    assert resolve_fallback() is None


@override_settings(
    LLM_BACKEND="mistral",
    LLM_FALLBACK_BACKEND="groq",
    MISTRAL_API_KEY="k-mistral",
    GROQ_API_KEY="k-groq",
)
def test_wrapper_built_when_primary_cloud_and_backup_has_key():
    # Mistral (primaire) + Groq (secours, clé présente) -> FallbackLLMClient.
    conf = resolve_fallback()
    assert conf is not None and conf["backend"] == "groq"

    client = get_llm_client()
    assert isinstance(client, FallbackLLMClient)
    # Le secours est bien un client Groq (format OpenAI-compatible), clé injectée.
    from llm.services.groq_client import GroqLLMClient

    assert isinstance(client.backup, GroqLLMClient)


@override_settings(
    LLM_BACKEND="mistral",
    LLM_FALLBACK_BACKEND="groq",
    MISTRAL_API_KEY="",  # primaire non instanciable (clé manquante)
    GROQ_API_KEY="k-groq",
)
def test_backup_used_directly_when_primary_cannot_be_built():
    # Le primaire lève LLMError dès __init__ (clé manquante) : on renvoie
    # directement le client de secours (Groq) au lieu de tout faire échouer.
    from llm.services.groq_client import GroqLLMClient

    client = get_llm_client()
    assert isinstance(client, GroqLLMClient)
