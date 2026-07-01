"""Tests pour l'app quizzes — K1 (list/detail) + K2 (answer)."""

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from .models import Answer, Attempt, Question, Quiz

User = get_user_model()

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


def test_answer_requires_full_coverage(auth_client, sample_quiz):
    """Une seule réponse sur un quiz de 10 questions → 400 (couverture incomplète)."""
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


# --- F2 : soumission basée sur le NOMBRE RÉEL de questions (pas 10 en dur) ---


@pytest.fixture
def quiz_15(user) -> Quiz:
    """Quiz de 15 questions (num_questions variable, > 10) pour vérifier que la
    soumission n'est pas bloquée à 10 en dur."""
    quiz = Quiz.objects.create(
        user=user,
        title="Quiz 15 questions",
        source_text="Lorem ipsum.",
        score=None,
        num_questions=15,
    )
    for i in range(1, 16):
        Question.objects.create(
            quiz=quiz,
            index=i,
            prompt=f"Question {i} ?",
            options=["A", "B", "C", "D"],
            correct_index=0,
        )
    return quiz


def test_answer_15_questions_all_correct(auth_client, quiz_15):
    """Un quiz de 15 questions se soumet correctement : score /15, total=15."""
    response = auth_client.post(
        f"/api/quizzes/{quiz_15.id}/answer/",
        {"answers": [{"index": i, "selected_index": 0} for i in range(1, 16)]},
        format="json",
    )
    assert response.status_code == 200, response.data
    assert response.data["score"] == 15
    assert response.data["total"] == 15
    assert len(response.data["details"]) == 15
    quiz_15.refresh_from_db()
    assert quiz_15.score == 15
    # L'Attempt reflète bien le nombre réel de questions.
    attempt = Attempt.objects.get(quiz=quiz_15, student=quiz_15.user)
    assert attempt.total == 15
    assert attempt.score == 15
    assert Answer.objects.filter(attempt=attempt).count() == 15


def test_answer_15_questions_partial_score(auth_client, quiz_15):
    """Score partiel sur 15 : 10 bonnes + 5 mauvaises → 10/15."""
    answers = [{"index": i, "selected_index": 0} for i in range(1, 11)] + [
        {"index": i, "selected_index": 1} for i in range(11, 16)
    ]
    response = auth_client.post(
        f"/api/quizzes/{quiz_15.id}/answer/",
        {"answers": answers},
        format="json",
    )
    assert response.status_code == 200, response.data
    assert response.data["score"] == 10
    assert response.data["total"] == 15


def test_answer_10_on_a_15_question_quiz_is_rejected(auth_client, quiz_15):
    """Soumettre 10 réponses sur un quiz de 15 → 400 (ancien bug : passait)."""
    response = auth_client.post(
        f"/api/quizzes/{quiz_15.id}/answer/",
        {"answers": [{"index": i, "selected_index": 0} for i in range(1, 11)]},
        format="json",
    )
    assert response.status_code == 400


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


# ---------------------------------------------------------------------------
# Release 2 — Historique des tentatives (Attempt / Answer)
# ---------------------------------------------------------------------------


def _all_correct_payload():
    """10 bonnes réponses (correct_index=0 partout sur sample_quiz)."""
    return {"answers": [{"index": i, "selected_index": 0} for i in range(1, 11)]}


def test_answer_creates_attempt_and_answers(auth_client, sample_quiz):
    """À la soumission : un Attempt (number=1) + 10 Answer sont créés,
    et la réponse JSON expose attempt_id + number (rétro-compat)."""
    response = auth_client.post(
        f"/api/quizzes/{sample_quiz.id}/answer/",
        _all_correct_payload(),
        format="json",
    )
    assert response.status_code == 200, response.data
    # Ajouts rétro-compatibles.
    assert response.data["attempt_id"] is not None
    assert response.data["number"] == 1
    # La réponse existante reste intacte.
    assert response.data["score"] == 10
    assert response.data["total"] == 10
    assert len(response.data["details"]) == 10

    attempts = Attempt.objects.filter(quiz=sample_quiz, student=sample_quiz.user)
    assert attempts.count() == 1
    attempt = attempts.get()
    assert attempt.number == 1
    assert attempt.score == 10
    assert attempt.total == 10
    # question_order par défaut = séquence naturelle [1..10].
    assert attempt.question_order == list(range(1, 11))
    # Un Answer par question.
    assert Answer.objects.filter(attempt=attempt).count() == 10
    assert all(a.is_correct for a in attempt.answers.all())


def test_answer_accepts_custom_question_order(auth_client, sample_quiz):
    """Un question_order mélangé fourni au POST est persisté sur l'Attempt."""
    shuffled = [3, 1, 2, 5, 4, 7, 6, 9, 8, 10]
    payload = _all_correct_payload()
    payload["question_order"] = shuffled
    response = auth_client.post(
        f"/api/quizzes/{sample_quiz.id}/answer/",
        payload,
        format="json",
    )
    assert response.status_code == 200, response.data
    attempt = Attempt.objects.get(quiz=sample_quiz, student=sample_quiz.user)
    assert attempt.question_order == shuffled


def test_attempt_number_increments_on_retest(auth_client, sample_quiz):
    """Un 2e POST crée une 2e tentative avec number=2."""
    r1 = auth_client.post(
        f"/api/quizzes/{sample_quiz.id}/answer/", _all_correct_payload(), format="json"
    )
    assert r1.status_code == 200, r1.data
    assert r1.data["number"] == 1

    r2 = auth_client.post(
        f"/api/quizzes/{sample_quiz.id}/answer/", _all_correct_payload(), format="json"
    )
    assert r2.status_code == 200, r2.data
    assert r2.data["number"] == 2

    numbers = sorted(
        Attempt.objects.filter(quiz=sample_quiz, student=sample_quiz.user).values_list(
            "number", flat=True
        )
    )
    assert numbers == [1, 2]


def test_attempts_list_requires_auth(sample_quiz):
    response = APIClient().get(f"/api/quizzes/{sample_quiz.id}/attempts/")
    assert response.status_code in (401, 403)


def test_attempts_list_returns_user_attempts(auth_client, sample_quiz):
    """La liste renvoie les tentatives du user, récentes (number décroissant) d'abord."""
    auth_client.post(
        f"/api/quizzes/{sample_quiz.id}/answer/", _all_correct_payload(), format="json"
    )
    # 2e tentative, tout faux → score 0.
    auth_client.post(
        f"/api/quizzes/{sample_quiz.id}/answer/",
        {"answers": [{"index": i, "selected_index": 1} for i in range(1, 11)]},
        format="json",
    )

    response = auth_client.get(f"/api/quizzes/{sample_quiz.id}/attempts/")
    assert response.status_code == 200
    data = response.data
    assert len(data) == 2
    # Récentes d'abord : number 2 puis 1.
    assert [a["number"] for a in data] == [2, 1]
    for entry in data:
        assert set(entry.keys()) == {"id", "number", "score", "total", "created_at"}
    # Score de la dernière (tout faux) = 0, première = 10.
    assert data[0]["score"] == 0
    assert data[1]["score"] == 10


def test_attempts_list_empty_when_never_answered(auth_client, sample_quiz):
    response = auth_client.get(f"/api/quizzes/{sample_quiz.id}/attempts/")
    assert response.status_code == 200
    assert response.data == []


def test_attempt_detail_returns_answers(auth_client, sample_quiz):
    """Le détail d'une tentative expose ses réponses avec le contenu question."""
    # 7 bonnes + 3 mauvaises.
    answers = [{"index": i, "selected_index": 0} for i in range(1, 8)] + [
        {"index": i, "selected_index": 1} for i in range(8, 11)
    ]
    post = auth_client.post(
        f"/api/quizzes/{sample_quiz.id}/answer/",
        {"answers": answers},
        format="json",
    )
    assert post.status_code == 200, post.data
    attempt_id = post.data["attempt_id"]

    response = auth_client.get(f"/api/quizzes/{sample_quiz.id}/attempts/{attempt_id}/")
    assert response.status_code == 200
    data = response.data
    assert data["number"] == 1
    assert data["score"] == 7
    assert data["total"] == 10
    assert len(data["answers"]) == 10
    # Chaque réponse porte le contenu de la question + le choix + la correction.
    for a in data["answers"]:
        assert set(a.keys()) == {
            "index",
            "prompt",
            "options",
            "correct_index",
            "selected_index",
            "is_correct",
        }
        assert a["options"] == ["A", "B", "C", "D"]
        assert a["correct_index"] == 0
    # Les 3 dernières (index 8,9,10) sont fausses.
    wrong = sorted(a["index"] for a in data["answers"] if not a["is_correct"])
    assert wrong == [8, 9, 10]


def test_attempt_detail_404_for_other_users_attempt(auth_client, other_user):
    """Une tentative appartenant à un autre user → 404 (scoping strict)."""
    other_quiz = Quiz.objects.create(user=other_user, title="Privé", source_text="...")
    for i in range(1, 11):
        Question.objects.create(
            quiz=other_quiz,
            index=i,
            prompt=f"Q{i}",
            options=["A", "B", "C", "D"],
            correct_index=0,
        )
    bob_attempt = Attempt.objects.create(
        quiz=other_quiz, student=other_user, number=1, total=10, score=5
    )

    # Alice tente d'accéder à la tentative de Bob (via l'id du quiz de Bob).
    response = auth_client.get(f"/api/quizzes/{other_quiz.id}/attempts/{bob_attempt.id}/")
    assert response.status_code == 404


def test_attempts_isolation_between_users(auth_client, other_user, sample_quiz):
    """La liste des tentatives ne fuit pas celles d'un autre user sur le même quiz.

    Note : le quiz appartient à `user` (via sample_quiz) ; on vérifie qu'une
    tentative fabriquée pour `other_user` sur ce quiz n'apparaît jamais dans la
    liste d'Alice.
    """
    # Tentative d'Alice via l'endpoint.
    auth_client.post(
        f"/api/quizzes/{sample_quiz.id}/answer/", _all_correct_payload(), format="json"
    )
    # Tentative fabriquée pour Bob sur le même quiz (cas limite : scoping student).
    Attempt.objects.create(quiz=sample_quiz, student=other_user, number=1, total=10, score=3)

    response = auth_client.get(f"/api/quizzes/{sample_quiz.id}/attempts/")
    assert response.status_code == 200
    data = response.data
    # Seule la tentative d'Alice remonte.
    assert len(data) == 1
    assert data[0]["score"] == 10
