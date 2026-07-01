"""Tests de la génération personnalisable : difficulté / nombre de questions / thème.

On utilise le backend `mock` (déterministe, sans réseau) via override_settings.
"""

import pytest
from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework.test import APIClient

from quizzes.models import Quiz

User = get_user_model()

pytestmark = pytest.mark.django_db

# Source > 200 caractères (contrainte du serializer sans PDF).
SOURCE = "Un cours de test suffisamment long pour dépasser la limite. " * 6


def _auth_client() -> APIClient:
    user = User.objects.create_user(
        username="lea@test.com", email="lea@test.com", password="motdepasse123"
    )
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@override_settings(LLM_BACKEND="mock")
def test_generate_with_custom_count_difficulty_and_theme():
    client = _auth_client()
    resp = client.post(
        "/api/llm/generate-quiz/",
        {
            "title": "Histoire",
            "source_text": SOURCE,
            "num_questions": 5,
            "difficulty": "hard",
            "theme": "Guerre froide",
        },
        format="json",
    )
    assert resp.status_code == 201, resp.data
    quiz = Quiz.objects.get(id=resp.data["id"])
    assert quiz.questions.count() == 5
    assert quiz.num_questions == 5
    assert quiz.difficulty == "hard"
    assert quiz.theme == "Guerre froide"


@override_settings(LLM_BACKEND="mock")
def test_default_generation_is_ten_questions():
    client = _auth_client()
    resp = client.post(
        "/api/llm/generate-quiz/",
        {"title": "X", "source_text": SOURCE},
        format="json",
    )
    assert resp.status_code == 201, resp.data
    assert Quiz.objects.get(id=resp.data["id"]).questions.count() == 10


@override_settings(LLM_BACKEND="mock")
def test_num_questions_out_of_range_is_rejected():
    client = _auth_client()
    resp = client.post(
        "/api/llm/generate-quiz/",
        {"title": "X", "source_text": SOURCE, "num_questions": 50},
        format="json",
    )
    assert resp.status_code == 400


@override_settings(LLM_BACKEND="mock")
def test_answer_flow_supports_custom_count():
    client = _auth_client()
    gen = client.post(
        "/api/llm/generate-quiz/",
        {"title": "X", "source_text": SOURCE, "num_questions": 5},
        format="json",
    )
    quiz_id = gen.data["id"]
    ans = client.post(
        f"/api/quizzes/{quiz_id}/answer/",
        {"answers": [{"index": i, "selected_index": 0} for i in range(1, 6)]},
        format="json",
    )
    assert ans.status_code == 200, ans.data
    assert ans.data["total"] == 5


@override_settings(LLM_BACKEND="mock")
def test_answer_flow_rejects_wrong_count_for_custom_quiz():
    client = _auth_client()
    gen = client.post(
        "/api/llm/generate-quiz/",
        {"title": "X", "source_text": SOURCE, "num_questions": 5},
        format="json",
    )
    quiz_id = gen.data["id"]
    # 10 réponses pour un quiz de 5 questions -> 400.
    ans = client.post(
        f"/api/quizzes/{quiz_id}/answer/",
        {"answers": [{"index": i, "selected_index": 0} for i in range(1, 11)]},
        format="json",
    )
    assert ans.status_code == 400
