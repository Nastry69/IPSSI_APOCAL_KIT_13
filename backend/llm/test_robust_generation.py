"""
Tests de la génération robuste de quiz — perturbation J4 « qualité ».

On vérifie que `generate_quiz_robust` :
- récupère les questions valides et régénère SEULEMENT le manque (complément) ;
- dé-duplique les énoncés répétés d'une tentative à l'autre ;
- ignore les questions invalides sans faire échouer tout le lot ;
- garantit EXACTEMENT 10 questions, ou lève un message clair après N essais.

Ces tests sont des tests UNITAIRES (pas de DB, pas de vrai Ollama) : on injecte
une fonction `complete_fn` factice qui renvoie des réponses LLM canned.
"""

import json

import pytest

from llm.services.base import LLMError
from llm.services.quiz_prompt import (
    generate_quiz_robust,
    parse_and_validate_quiz,
    parse_valid_questions,
    validate_question,
)

SOURCE = "Contenu du cours de test. " * 20
TITLE = "Cours de test"


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def make_question(n: int, *, options: list | None = None, correct: int = 0) -> dict:
    """Construit une question valide (ou volontairement cassée via `options`)."""
    return {
        "prompt": f"Question numéro {n} ?",
        "options": options if options is not None else [f"Opt {n}.{j}" for j in range(4)],
        "correct_index": correct,
    }


def payload(questions: list[dict]) -> str:
    return json.dumps({"questions": questions})


class FakeLLM:
    """`complete_fn` factice : renvoie les réponses fournies, dans l'ordre.

    Mémorise les appels (system, user) pour pouvoir vérifier le prompt de
    complément. Une fois la liste épuisée, renvoie un quiz vide.
    """

    def __init__(self, responses: list[str]) -> None:
        self.responses = list(responses)
        self.calls: list[tuple[str, str]] = []

    def __call__(self, system: str, user: str) -> str:
        self.calls.append((system, user))
        return self.responses.pop(0) if self.responses else payload([])


# --------------------------------------------------------------------------- #
# generate_quiz_robust
# --------------------------------------------------------------------------- #
def test_completes_partial_then_backfills():
    """1ʳᵉ tentative incomplète (8) → un complément ciblé de 2 → 10 questions."""
    fake = FakeLLM(
        [
            payload([make_question(i) for i in range(8)]),
            payload([make_question(i) for i in range(8, 10)]),
        ]
    )
    result = generate_quiz_robust(fake, SOURCE, TITLE)

    assert len(result) == 10
    assert len(fake.calls) == 2  # initial + 1 complément
    # Le complément demande EXACTEMENT le manque (2), pas 10.
    assert "2 NOUVELLE" in fake.calls[1][1]


def test_dedupes_across_attempts():
    """Les doublons d'énoncés entre tentatives ne sont pas comptés deux fois."""
    fake = FakeLLM(
        [
            payload([make_question(i) for i in range(6)]),
            # 2 doublons (0, 1) + 4 nouvelles (6..9)
            payload(
                [make_question(0), make_question(1)] + [make_question(i) for i in range(6, 10)]
            ),
        ]
    )
    result = generate_quiz_robust(fake, SOURCE, TITLE)
    prompts = [q["prompt"] for q in result]

    assert len(result) == 10
    assert len(set(prompts)) == 10  # toutes distinctes


def test_filters_invalid_questions_without_failing():
    """Questions invalides ignorées ; les 10 valides du même lot suffisent."""
    bad_options = make_question(0, options=["seulement", "trois", "options"])
    bad_index = make_question(1, correct=7)
    valid = [make_question(i) for i in range(2, 12)]  # 10 valides
    fake = FakeLLM([payload([bad_options, bad_index, *valid])])

    result = generate_quiz_robust(fake, SOURCE, TITLE)

    assert len(result) == 10
    assert len(fake.calls) == 1  # 10 valides dès le 1er appel, pas de complément


def test_truncates_overshoot_to_target():
    """Plus de 10 questions valides → on tronque à 10."""
    fake = FakeLLM([payload([make_question(i) for i in range(12)])])
    result = generate_quiz_robust(fake, SOURCE, TITLE)
    assert len(result) == 10


def test_raises_clear_error_when_target_unreached():
    """3 mêmes questions à chaque essai → jamais 10 → LLMError explicite."""
    same = payload([make_question(i) for i in range(3)])
    fake = FakeLLM([same, same, same])

    with pytest.raises(LLMError) as exc:
        generate_quiz_robust(fake, SOURCE, TITLE)

    assert "3/10" in str(exc.value)
    assert len(fake.calls) == 3  # bien borné à max_attempts


def test_respects_custom_attempt_budget():
    """Le budget d'essais est paramétrable."""
    fake = FakeLLM([payload([make_question(0)])] * 5)
    with pytest.raises(LLMError):
        generate_quiz_robust(fake, SOURCE, TITLE, max_attempts=2)
    assert len(fake.calls) == 2


# --------------------------------------------------------------------------- #
# validate_question
# --------------------------------------------------------------------------- #
def test_validate_question_accepts_and_strips():
    cleaned, error = validate_question(
        {"prompt": "  Q ?  ", "options": [" a ", "b", "c", "d"], "correct_index": 2}
    )
    assert error is None
    assert cleaned["prompt"] == "Q ?"
    assert cleaned["options"][0] == "a"
    assert cleaned["correct_index"] == 2


@pytest.mark.parametrize(
    "question, expected_fragment",
    [
        ("pas un dict", "n'est pas un objet"),
        ({"options": ["a", "b", "c", "d"], "correct_index": 0}, "prompt manquant"),
        ({"prompt": "Q", "options": ["a", "b", "c"], "correct_index": 0}, "exactement 4 options"),
        ({"prompt": "Q", "options": ["a", "", "c", "d"], "correct_index": 0}, "options invalides"),
        ({"prompt": "Q", "options": ["a", "b", "c", "d"], "correct_index": 7}, "correct_index"),
        # bool est une sous-classe de int : True ne doit PAS passer.
        ({"prompt": "Q", "options": ["a", "b", "c", "d"], "correct_index": True}, "correct_index"),
    ],
)
def test_validate_question_rejects(question, expected_fragment):
    cleaned, error = validate_question(question)
    assert cleaned is None
    assert expected_fragment in error


# --------------------------------------------------------------------------- #
# parse_valid_questions (tolérant)
# --------------------------------------------------------------------------- #
def test_parse_valid_questions_keeps_only_valid():
    raw = payload([make_question(0), make_question(1, options=["x"]), make_question(2)])
    assert len(parse_valid_questions(raw)) == 2


def test_parse_valid_questions_returns_empty_on_garbage():
    assert parse_valid_questions("ceci n'est pas du JSON") == []
    assert parse_valid_questions("") == []
    assert parse_valid_questions(json.dumps({"autre": []})) == []


# --------------------------------------------------------------------------- #
# parse_and_validate_quiz (strict, comportement préservé)
# --------------------------------------------------------------------------- #
def test_strict_parse_accepts_ten_valid():
    result = parse_and_validate_quiz(payload([make_question(i) for i in range(10)]))
    assert len(result) == 10


def test_strict_parse_rejects_whole_batch_on_one_bad_question():
    """Reproduit l'erreur d'origine : la 4ᵉ question sans 4 options fait tout échouer."""
    questions = [make_question(i) for i in range(10)]
    questions[3]["options"] = ["seulement", "trois", "options"]
    with pytest.raises(LLMError) as exc:
        parse_and_validate_quiz(payload(questions))
    assert "Question 4" in str(exc.value)
    assert "exactement 4 options" in str(exc.value)
