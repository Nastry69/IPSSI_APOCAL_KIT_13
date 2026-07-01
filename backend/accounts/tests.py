"""Tests pédagogiques pour l'app accounts.

Ces tests servent d'exemples : signup, login, logout, accès protégé.
Lancez : pytest accounts/
"""

import pytest
from django.contrib.auth.models import User
from django.test import override_settings
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db


@pytest.fixture
def client() -> APIClient:
    return APIClient()


@pytest.fixture
def user(db) -> User:
    return User.objects.create_user(
        username="alice", email="alice@test.com", password="motdepasse123"
    )


def test_signup_creates_user(client):
    # Lot 3 : inscription par EMAIL (username = email en interne).
    # Sprint A RGPD : `accept_terms=True` est désormais requis (consentement).
    response = client.post(
        "/api/accounts/signup/",
        {
            "email": "bob@test.com",
            "password": "motdepasse123",
            "accept_terms": True,
        },
        format="json",
    )
    assert response.status_code == 201, response.data
    assert User.objects.filter(email="bob@test.com").exists()


def test_signup_requires_email(client):
    response = client.post(
        "/api/accounts/signup/",
        {"password": "motdepasse123"},
        format="json",
    )
    assert response.status_code == 400


def test_login_returns_token(client, user):
    response = client.post(
        "/api/accounts/login/",
        {"email": "alice@test.com", "password": "motdepasse123"},
        format="json",
    )
    assert response.status_code == 200, response.data
    assert "token" in response.data
    assert response.data["user"]["email"] == "alice@test.com"


def test_login_with_wrong_password(client, user):
    response = client.post(
        "/api/accounts/login/",
        {"email": "alice@test.com", "password": "wrong"},
        format="json",
    )
    assert response.status_code == 400


def test_me_requires_auth(client):
    response = client.get("/api/accounts/me/")
    assert response.status_code in (401, 403)


def test_me_with_token(client, user):
    from rest_framework.authtoken.models import Token

    token = Token.objects.create(user=user)
    client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
    response = client.get("/api/accounts/me/")
    assert response.status_code == 200
    assert response.data["username"] == "alice"


def test_logout_invalidates_token(client, user):
    from rest_framework.authtoken.models import Token

    token = Token.objects.create(user=user)
    client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
    response = client.post("/api/accounts/logout/")
    assert response.status_code == 204
    # Le token n'existe plus
    assert not Token.objects.filter(key=token.key).exists()


# ---------------------------------------------------------------------------
# Sprint A RGPD — Throttling (M5)
# ---------------------------------------------------------------------------


def test_login_is_throttled(client, user):
    # ScopedRateThrottle stocke l'historique dans le cache : on le vide d'abord
    # pour partir d'un compteur propre (les autres tests peuvent l'avoir rempli).
    from django.core.cache import cache

    cache.clear()

    payload = {"email": "alice@test.com", "password": "wrong"}
    statuses = []
    # Rate "login" = 10/min : les 10 premiers passent (400 = échec d'auth), le 11e -> 429.
    for _ in range(11):
        resp = client.post("/api/accounts/login/", payload, format="json")
        statuses.append(resp.status_code)

    assert statuses[-1] == 429, statuses
    assert statuses[:10] == [400] * 10, statuses


# ---------------------------------------------------------------------------
# Sprint A RGPD — Consentement à l'inscription (M3)
# ---------------------------------------------------------------------------


def test_signup_requires_consent(client):
    from accounts.models import CURRENT_CONSENT_VERSION, get_or_create_profile

    base = {"email": "carol@test.com", "password": "motdepasse123"}

    # Sans accept_terms -> 400 (champ requis).
    resp = client.post("/api/accounts/signup/", base, format="json")
    assert resp.status_code == 400, resp.data
    assert not User.objects.filter(email="carol@test.com").exists()

    # accept_terms=false -> 400 (validate_accept_terms).
    resp = client.post("/api/accounts/signup/", {**base, "accept_terms": False}, format="json")
    assert resp.status_code == 400, resp.data
    assert not User.objects.filter(email="carol@test.com").exists()

    # accept_terms=true -> 201 + consentement horodaté et versionné.
    resp = client.post("/api/accounts/signup/", {**base, "accept_terms": True}, format="json")
    assert resp.status_code == 201, resp.data
    created = User.objects.get(email="carol@test.com")
    profile = get_or_create_profile(created)
    assert profile.consent_accepted_at is not None
    assert profile.consent_version == CURRENT_CONSENT_VERSION


# ---------------------------------------------------------------------------
# Sprint A RGPD — Export / portabilité (M4)
# ---------------------------------------------------------------------------


def _auth(client, user):
    from rest_framework.authtoken.models import Token

    token = Token.objects.create(user=user)
    client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
    return client


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_export_request_sends_email(client, user):
    from django.core import mail

    mail.outbox = []
    _auth(client, user)
    resp = client.post("/api/accounts/export/request/")
    assert resp.status_code == 200, resp.data
    assert "lien" in resp.data["detail"].lower()
    # En backend locmem, l'email d'export est capturé dans outbox.
    assert len(mail.outbox) == 1
    assert user.email in mail.outbox[0].to
    # Le corps contient le lien de téléchargement backend.
    assert "/api/accounts/export/download/?token=" in mail.outbox[0].body


def test_export_download_valid_token(client, user):
    import json

    from accounts.tokens import make_export_token

    # Un quiz + une question pour vérifier la structure imbriquée.
    quiz = user.quizzes.create(title="Cours 1", source_text="Texte du cours", score=1)
    quiz.questions.create(
        index=1,
        prompt="Q ?",
        options=["a", "b", "c", "d"],
        correct_index=0,
        selected_index=0,
    )

    token = make_export_token(user)
    resp = client.get(f"/api/accounts/export/download/?token={token}")
    assert resp.status_code == 200
    assert resp["Content-Type"].startswith("application/json")
    assert resp["Content-Disposition"] == ('attachment; filename="mes-donnees-edututor.json"')

    data = json.loads(resp.content)
    assert set(data.keys()) == {"account", "profile", "quizzes"}
    assert data["account"]["email"] == user.email
    assert "consentement" in data["profile"]
    assert len(data["quizzes"]) == 1
    assert data["quizzes"][0]["title"] == "Cours 1"
    assert data["quizzes"][0]["questions"][0]["correct_index"] == 0


def test_export_download_rejects_invalid_token(client):
    # Token bidon -> 400 générique.
    resp = client.get("/api/accounts/export/download/?token=nimportequoi")
    assert resp.status_code == 400

    # Token absent -> 400 également.
    resp = client.get("/api/accounts/export/download/")
    assert resp.status_code == 400

    # Token d'un autre salt (validation email) -> rejeté par read_export_token.
    from accounts.tokens import make_email_verify_token

    other = User.objects.create_user(
        username="dave", email="dave@test.com", password="motdepasse123"
    )
    wrong = make_email_verify_token(other)
    resp = client.get(f"/api/accounts/export/download/?token={wrong}")
    assert resp.status_code == 400


def test_export_isolation(client, user):
    import json

    from accounts.tokens import make_export_token

    # `user` (alice) possède un quiz ; bob a le sien.
    user.quizzes.create(title="Quiz Alice", source_text="secret alice", score=None)
    bob = User.objects.create_user(username="bob", email="bob@test.com", password="motdepasse123")
    bob.quizzes.create(title="Quiz Bob", source_text="texte bob", score=None)

    # Le token de bob ne doit renvoyer QUE les données de bob.
    token = make_export_token(bob)
    resp = client.get(f"/api/accounts/export/download/?token={token}")
    assert resp.status_code == 200
    data = json.loads(resp.content)
    assert data["account"]["email"] == bob.email
    titles = [q["title"] for q in data["quizzes"]]
    assert titles == ["Quiz Bob"]
    assert "Quiz Alice" not in titles
