"""Tests pour l'app quizzes — K1 (list/detail) + K2 (answer)."""

import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from .models import Question, Quiz

pytestmark = pytest.mark.django_db


@pytest.fixture
def user() -> User:
    return User.objects.create_user(username="alice", password="motdepasse123")


@pytest.fixture
def other_user() -> User:
    return User.objects.create_user(username="bob", password="motdepasse123")


@pytest.fixture
def auth_client(user) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def sample_quiz(user) -> Quiz:
    quiz = Quiz.objects.create(
        user=user,
        title="Cours de test",
        source_text="Lorem ipsum dolor sit amet.",
        score=None,
    )
    for i in range(1, 11):
        Question.objects.create(
            quiz=quiz,
            index=i,
            prompt=f"Question {i} ?",
            options=["A", "B", "C", "D"],
            correct_index=0,  # bonne réponse = A pour toutes
        )
    return quiz


def test_quiz_list_requires_auth():
    response = APIClient().get("/api/quizzes/")
    assert response.status_code in (401, 403)


def test_quiz_list_returns_user_quizzes(auth_client, sample_quiz):
    response = auth_client.get("/api/quizzes/")
    assert response.status_code == 200
    assert response.data["count"] == 1
    assert response.data["results"][0]["nb_questions"] == 10


def test_quiz_list_does_not_leak_other_users_quizzes(auth_client, other_user):
    Quiz.objects.create(user=other_user, title="Quiz de Bob", source_text="...")
    response = auth_client.get("/api/quizzes/")
    assert response.data["count"] == 0


def test_quiz_detail(auth_client, sample_quiz):
    response = auth_client.get(f"/api/quizzes/{sample_quiz.id}/")
    assert response.status_code == 200
    assert len(response.data["questions"]) == 10


def test_quiz_detail_404_for_other_users_quiz(auth_client, other_user):
    other_quiz = Quiz.objects.create(user=other_user, title="Privé", source_text="...")
    response = auth_client.get(f"/api/quizzes/{other_quiz.id}/")
    assert response.status_code == 404


# --- K2 : answer endpoint ---


def test_answer_all_correct(auth_client, sample_quiz):
    """Toutes les bonnes réponses (= 0 partout) → score 10/10."""
    response = auth_client.post(
        f"/api/quizzes/{sample_quiz.id}/answer/",
        {"answers": [{"index": i, "selected_index": 0} for i in range(1, 11)]},
        format="json",
    )
    assert response.status_code == 200, response.data
    assert response.data["score"] == 10
    assert response.data["total"] == 10
    assert all(d["correct"] for d in response.data["details"])
    sample_quiz.refresh_from_db()
    assert sample_quiz.score == 10


def test_answer_all_wrong(auth_client, sample_quiz):
    response = auth_client.post(
        f"/api/quizzes/{sample_quiz.id}/answer/",
        {"answers": [{"index": i, "selected_index": 1} for i in range(1, 11)]},
        format="json",
    )
    assert response.data["score"] == 0


def test_answer_partial(auth_client, sample_quiz):
    """5 bonnes + 5 mauvaises."""
    answers = [{"index": i, "selected_index": 0} for i in range(1, 6)] + [
        {"index": i, "selected_index": 1} for i in range(6, 11)
    ]
    response = auth_client.post(
        f"/api/quizzes/{sample_quiz.id}/answer/",
        {"answers": answers},
        format="json",
    )
    assert response.data["score"] == 5


def test_answer_requires_10(auth_client, sample_quiz):
    response = auth_client.post(
        f"/api/quizzes/{sample_quiz.id}/answer/",
        {"answers": [{"index": 1, "selected_index": 0}]},
        format="json",
    )
    assert response.status_code == 400


def test_answer_404_for_other_users_quiz(auth_client, other_user):
    other_quiz = Quiz.objects.create(user=other_user, title="Privé", source_text="...")
    for i in range(1, 11):
        Question.objects.create(
            quiz=other_quiz,
            index=i,
            prompt=f"Q{i}",
            options=["A", "B", "C", "D"],
            correct_index=0,
        )
    response = auth_client.post(
        f"/api/quizzes/{other_quiz.id}/answer/",
        {"answers": [{"index": i, "selected_index": 0} for i in range(1, 11)]},
        format="json",
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# F6 — StatsView (dashboard) : /api/quizzes/stats/
# ---------------------------------------------------------------------------


def _make_taken_quiz(user, title, score, created_at=None):
    """Crée un quiz déjà passé (score non nul) avec 10 questions.

    Si `created_at` est fourni, on force la valeur malgré `auto_now_add`
    (via un update ciblé) pour pouvoir tester le tri chronologique.
    """
    quiz = Quiz.objects.create(
        user=user,
        title=title,
        source_text="Lorem ipsum.",
        score=score,
    )
    for i in range(1, 11):
        Question.objects.create(
            quiz=quiz,
            index=i,
            prompt=f"Q{i}",
            options=["A", "B", "C", "D"],
            correct_index=0,
        )
    if created_at is not None:
        Quiz.objects.filter(pk=quiz.pk).update(created_at=created_at)
        quiz.refresh_from_db()
    return quiz


def test_stats_requires_auth():
    response = APIClient().get("/api/quizzes/stats/")
    assert response.status_code in (401, 403)


def test_stats_empty_for_new_user(auth_client):
    """Aucun quiz : compteurs à zéro, moyennes/accuracy à None, history vide."""
    response = auth_client.get("/api/quizzes/stats/")
    assert response.status_code == 200
    data = response.data
    assert data["total_quizzes"] == 0
    assert data["quizzes_taken"] == 0
    assert data["average_score"] is None
    assert data["best_score"] is None
    assert data["last_score"] is None
    assert data["questions_answered"] == 0
    assert data["questions_correct"] == 0
    assert data["accuracy"] is None
    assert data["history"] == []


def test_stats_aggregates_multiple_quizzes(auth_client, user):
    """Plusieurs quiz passés : nombre, moyenne, meilleur score, dernier score."""
    import datetime

    from django.utils import timezone

    base = timezone.now()
    _make_taken_quiz(user, "Quiz 1", score=4, created_at=base)
    _make_taken_quiz(user, "Quiz 2", score=8, created_at=base + datetime.timedelta(hours=1))
    _make_taken_quiz(user, "Quiz 3", score=6, created_at=base + datetime.timedelta(hours=2))

    response = auth_client.get("/api/quizzes/stats/")
    assert response.status_code == 200
    data = response.data

    assert data["total_quizzes"] == 3
    assert data["quizzes_taken"] == 3
    # (4 + 8 + 6) / 3 = 6.0, arrondi à 1 décimale
    assert data["average_score"] == 6.0
    assert data["best_score"] == 8
    # last_score = score du quiz le plus récent (tri chronologique croissant)
    assert data["last_score"] == 6


def test_stats_history_content_and_order(auth_client, user):
    """history contient {id, title, score, created_at} trié par created_at croissant."""
    import datetime

    from django.utils import timezone

    base = timezone.now()
    # Créés dans le désordre chronologique volontairement.
    _make_taken_quiz(user, "Deuxième", score=8, created_at=base + datetime.timedelta(hours=1))
    _make_taken_quiz(user, "Premier", score=4, created_at=base)
    _make_taken_quiz(user, "Troisième", score=6, created_at=base + datetime.timedelta(hours=2))

    response = auth_client.get("/api/quizzes/stats/")
    history = response.data["history"]

    assert len(history) == 3
    # Chaque entrée porte les clés attendues.
    for entry in history:
        assert set(entry.keys()) == {"id", "title", "score", "created_at"}
    # Tri chronologique croissant (le plus ancien d'abord).
    titles = [e["title"] for e in history]
    assert titles == ["Premier", "Deuxième", "Troisième"]
    scores = [e["score"] for e in history]
    assert scores == [4, 8, 6]


def test_stats_ignores_not_taken_quizzes(auth_client, user, sample_quiz):
    """Un quiz sans score (score=None) compte dans total_quizzes mais pas dans quizzes_taken."""
    # sample_quiz a score=None.
    _make_taken_quiz(user, "Passé", score=7)

    response = auth_client.get("/api/quizzes/stats/")
    data = response.data
    assert data["total_quizzes"] == 2  # sample_quiz (non passé) + le quiz passé
    assert data["quizzes_taken"] == 1
    assert data["best_score"] == 7
    assert data["average_score"] == 7.0
    # Seul le quiz passé apparaît dans l'historique.
    assert len(data["history"]) == 1
    assert data["history"][0]["title"] == "Passé"


def test_stats_accuracy_from_answered_questions(auth_client, sample_quiz):
    """La précision est calculée sur les questions répondues (selected_index non nul).

    Sur sample_quiz (correct_index=0 partout), on répond 7 bonnes + 3 mauvaises.
    """
    answers = [{"index": i, "selected_index": 0} for i in range(1, 8)] + [
        {"index": i, "selected_index": 1} for i in range(8, 11)
    ]
    resp = auth_client.post(
        f"/api/quizzes/{sample_quiz.id}/answer/",
        {"answers": answers},
        format="json",
    )
    assert resp.status_code == 200, resp.data

    response = auth_client.get("/api/quizzes/stats/")
    data = response.data
    assert data["questions_answered"] == 10
    assert data["questions_correct"] == 7
    # round(100 * 7 / 10) = 70
    assert data["accuracy"] == 70


def test_stats_isolation_between_users(auth_client, user, other_user):
    """Les quiz d'un autre user n'influencent pas les stats du user connecté."""
    _make_taken_quiz(user, "À moi", score=5)
    _make_taken_quiz(other_user, "À Bob 1", score=10)
    _make_taken_quiz(other_user, "À Bob 2", score=9)

    response = auth_client.get("/api/quizzes/stats/")
    data = response.data
    assert data["total_quizzes"] == 1
    assert data["quizzes_taken"] == 1
    assert data["best_score"] == 5
    assert data["average_score"] == 5.0
    assert len(data["history"]) == 1
    assert data["history"][0]["title"] == "À moi"


# ---------------------------------------------------------------------------
# F5 — MistakesView (révision) : /api/quizzes/mistakes/
# ---------------------------------------------------------------------------


def test_mistakes_requires_auth():
    response = APIClient().get("/api/quizzes/mistakes/")
    assert response.status_code in (401, 403)


def test_mistakes_empty_when_nothing_answered(auth_client, sample_quiz):
    """Aucune question répondue (selected_index=None) → aucune erreur listée."""
    response = auth_client.get("/api/quizzes/mistakes/")
    assert response.status_code == 200
    assert response.data["count"] == 0
    assert response.data["mistakes"] == []


def test_mistakes_lists_only_wrong_answers(auth_client, sample_quiz):
    """Après réponse (7 bonnes + 3 mauvaises), seules les 3 ratées sont renvoyées."""
    answers = [{"index": i, "selected_index": 0} for i in range(1, 8)] + [
        {"index": i, "selected_index": 1} for i in range(8, 11)
    ]
    resp = auth_client.post(
        f"/api/quizzes/{sample_quiz.id}/answer/",
        {"answers": answers},
        format="json",
    )
    assert resp.status_code == 200, resp.data

    response = auth_client.get("/api/quizzes/mistakes/")
    data = response.data
    assert data["count"] == 3
    # Seules les questions d'index 8, 9, 10 (mauvaises) sont présentes.
    wrong_indices = sorted(m["index"] for m in data["mistakes"])
    assert wrong_indices == [8, 9, 10]
    # Chaque item porte les clés attendues et les bonnes valeurs.
    for m in data["mistakes"]:
        assert set(m.keys()) == {
            "quiz_id",
            "quiz_title",
            "index",
            "prompt",
            "options",
            "correct_index",
            "selected_index",
        }
        assert m["quiz_id"] == sample_quiz.id
        assert m["quiz_title"] == sample_quiz.title
        assert m["correct_index"] == 0
        assert m["selected_index"] == 1
        assert m["options"] == ["A", "B", "C", "D"]


def test_mistakes_disappear_when_reanswered_correctly(auth_client, sample_quiz):
    """Une question ratée puis re-répondue correctement disparaît de la liste.

    Le POST answer écrase selected_index (dernière tentative). On soumet d'abord
    tout faux, puis tout juste : plus aucune erreur.
    """
    all_wrong = {"answers": [{"index": i, "selected_index": 1} for i in range(1, 11)]}
    resp1 = auth_client.post(f"/api/quizzes/{sample_quiz.id}/answer/", all_wrong, format="json")
    assert resp1.status_code == 200, resp1.data
    # 10 erreurs après la première tentative (tout faux).
    assert auth_client.get("/api/quizzes/mistakes/").data["count"] == 10

    all_right = {"answers": [{"index": i, "selected_index": 0} for i in range(1, 11)]}
    resp2 = auth_client.post(f"/api/quizzes/{sample_quiz.id}/answer/", all_right, format="json")
    assert resp2.status_code == 200, resp2.data
    # Après re-réponse correcte, plus aucune erreur.
    assert auth_client.get("/api/quizzes/mistakes/").data["count"] == 0


def test_mistakes_isolation_between_users(auth_client, user, other_user):
    """Les erreurs d'un autre user ne remontent pas pour le user connecté."""
    # Quiz de Bob avec une réponse fausse enregistrée en base.
    bob_quiz = Quiz.objects.create(user=other_user, title="Quiz de Bob", source_text="...", score=0)
    for i in range(1, 11):
        Question.objects.create(
            quiz=bob_quiz,
            index=i,
            prompt=f"Q{i}",
            options=["A", "B", "C", "D"],
            correct_index=0,
            selected_index=1,  # réponse fausse
        )

    # Alice répond faux à 2 questions de son propre quiz.
    alice_quiz = _make_taken_quiz(user, "Quiz d'Alice", score=8)
    Question.objects.filter(quiz=alice_quiz, index__in=[1, 2]).update(selected_index=3)

    response = auth_client.get("/api/quizzes/mistakes/")
    data = response.data
    # Seules les 2 erreurs d'Alice remontent, pas les 10 de Bob.
    assert data["count"] == 2
    for m in data["mistakes"]:
        assert m["quiz_id"] == alice_quiz.id
        assert m["quiz_title"] == "Quiz d'Alice"
