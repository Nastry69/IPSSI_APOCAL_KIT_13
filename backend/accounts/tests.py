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


# ===========================================================================
# FIABILISATION F1 (auth) — branches non couvertes
#
# Objectif : verrouiller le comportement ACTUEL du code (tests qui PASSENT),
# en couvrant les cas limites de la validation d'email, du resend, du reset
# de mot de passe, du profil et du change-password.
#
# Style repris des tests existants ci-dessus : APIClient, fixtures client/user,
# helper _auth (Token + credentials), @override_settings pour le backend email
# locmem, mail.outbox. On s'authentifie TOUJOURS par token (jamais par appels
# répétés à /login/) pour ne pas déclencher le throttle. Les endpoints sensibles
# répétés vident le cache au début (cache.clear()).
# ===========================================================================


# ---------------------------------------------------------------------------
# F1 — Validation d'email (verify-email)
# ---------------------------------------------------------------------------


def test_verify_email_valid_token_sets_email_verified(client, user):
    # Le profil part avec email_verified=False (défaut du modèle).
    from accounts.models import get_or_create_profile
    from accounts.tokens import make_email_verify_token

    assert get_or_create_profile(user).email_verified is False

    token = make_email_verify_token(user)
    resp = client.post("/api/accounts/verify-email/", {"token": token}, format="json")
    assert resp.status_code == 200, resp.data
    assert "confirmé" in resp.data["detail"].lower()

    # email_verified est bien passé à True en base.
    user.refresh_from_db()
    assert get_or_create_profile(user).email_verified is True


def test_verify_email_invalid_token_returns_400(client, user):
    # Token bidon (signature invalide) -> 400, email_verified reste False.
    from accounts.models import get_or_create_profile

    resp = client.post("/api/accounts/verify-email/", {"token": "nimportequoi"}, format="json")
    assert resp.status_code == 400, resp.data
    assert get_or_create_profile(user).email_verified is False


def test_verify_email_wrong_salt_token_returns_400(client, user):
    # Token signé avec un AUTRE salt (export) -> refusé par read_email_verify_token.
    from accounts.models import get_or_create_profile
    from accounts.tokens import make_export_token

    wrong = make_export_token(user)
    resp = client.post("/api/accounts/verify-email/", {"token": wrong}, format="json")
    assert resp.status_code == 400, resp.data
    assert get_or_create_profile(user).email_verified is False


def test_verify_email_requires_token_field(client):
    # Champ "token" manquant -> 400 (validation serializer).
    resp = client.post("/api/accounts/verify-email/", {}, format="json")
    assert resp.status_code == 400, resp.data


def test_verify_email_deleted_user_returns_400(client, user):
    # Token valide mais l'utilisateur a été supprimé entre-temps -> 400.
    from accounts.tokens import make_email_verify_token

    token = make_email_verify_token(user)
    user.delete()
    resp = client.post("/api/accounts/verify-email/", {"token": token}, format="json")
    assert resp.status_code == 400, resp.data


# ---------------------------------------------------------------------------
# F1 — Renvoi de l'email de validation (resend-verification)
# ---------------------------------------------------------------------------


def test_resend_verification_requires_auth(client):
    # Endpoint protégé : sans authentification -> 401/403.
    resp = client.post("/api/accounts/resend-verification/")
    assert resp.status_code in (401, 403)


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_resend_verification_sends_email_when_not_verified(client, user):
    from django.core import mail

    mail.outbox = []
    _auth(client, user)

    resp = client.post("/api/accounts/resend-verification/")
    assert resp.status_code == 200, resp.data
    assert "renvoyé" in resp.data["detail"].lower()
    # L'email de validation est bien parti et contient le lien front.
    assert len(mail.outbox) == 1
    assert user.email in mail.outbox[0].to
    assert "/verify-email?token=" in mail.outbox[0].body


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_resend_verification_idempotent_when_already_verified(client, user):
    # Profil déjà vérifié -> message idempotent, AUCUN email renvoyé.
    from django.core import mail

    from accounts.models import get_or_create_profile

    profile = get_or_create_profile(user)
    profile.email_verified = True
    profile.save(update_fields=["email_verified"])

    mail.outbox = []
    _auth(client, user)

    resp = client.post("/api/accounts/resend-verification/")
    assert resp.status_code == 200, resp.data
    assert "déjà confirmé" in resp.data["detail"].lower()
    # Pas d'email envoyé puisqu'il est déjà confirmé.
    assert len(mail.outbox) == 0


# ---------------------------------------------------------------------------
# F1 — Demande de reset de mot de passe (password-reset/) : anti-énumération
# ---------------------------------------------------------------------------


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_password_reset_request_same_response_whether_account_exists(client, user):
    # Anti-énumération : la RÉPONSE (status + detail) doit être IDENTIQUE que
    # le compte existe ou non, pour ne pas révéler quels emails sont enregistrés.
    from django.core import mail
    from django.core.cache import cache

    cache.clear()  # endpoint sensible (throttle password_reset) : compteur propre
    mail.outbox = []

    # Compte existant (user = alice@test.com).
    resp_existing = client.post(
        "/api/accounts/password-reset/", {"email": "alice@test.com"}, format="json"
    )
    # Compte inexistant.
    resp_missing = client.post(
        "/api/accounts/password-reset/", {"email": "inconnu@test.com"}, format="json"
    )

    assert resp_existing.status_code == 200, resp_existing.data
    assert resp_missing.status_code == 200, resp_missing.data
    # Réponse strictement identique (anti-énumération).
    assert resp_existing.data == resp_missing.data
    assert "si un compte existe" in resp_existing.data["detail"].lower()

    # Un seul email est réellement parti : celui de l'utilisateur existant.
    assert len(mail.outbox) == 1
    assert user.email in mail.outbox[0].to
    assert "/reset-password?uid=" in mail.outbox[0].body


def test_password_reset_request_invalid_email_returns_400(client):
    # Le serializer utilise EmailField : une valeur non-email -> 400.
    from django.core.cache import cache

    cache.clear()
    resp = client.post("/api/accounts/password-reset/", {"email": "pas-un-email"}, format="json")
    assert resp.status_code == 400, resp.data


# ---------------------------------------------------------------------------
# F1 — Confirmation du reset (password-reset/confirm/)
# ---------------------------------------------------------------------------


def test_password_reset_confirm_valid_tokens_changes_password(client, user):
    # uid + token valides -> le mot de passe est changé en base.
    from accounts.tokens import make_password_reset_tokens

    uidb64, token = make_password_reset_tokens(user)
    resp = client.post(
        "/api/accounts/password-reset/confirm/",
        {"uid": uidb64, "token": token, "new_password": "nouveaupass456"},
        format="json",
    )
    assert resp.status_code == 200, resp.data
    assert "réinitialisé" in resp.data["detail"].lower()

    # Le nouveau mot de passe est bien actif (et l'ancien ne l'est plus).
    user.refresh_from_db()
    assert user.check_password("nouveaupass456")
    assert not user.check_password("motdepasse123")


def test_password_reset_confirm_invalid_token_returns_400(client, user):
    # uid valide mais token invalide -> 400, mot de passe INCHANGÉ.
    from accounts.tokens import make_password_reset_tokens

    uidb64, _ = make_password_reset_tokens(user)
    resp = client.post(
        "/api/accounts/password-reset/confirm/",
        {"uid": uidb64, "token": "invalide-token", "new_password": "nouveaupass456"},
        format="json",
    )
    assert resp.status_code == 400, resp.data
    user.refresh_from_db()
    assert user.check_password("motdepasse123")


def test_password_reset_confirm_invalid_uid_returns_400(client, user):
    # uid qui ne correspond à aucun utilisateur -> 400 (read_password_reset_tokens -> None).
    from django.utils.encoding import force_bytes
    from django.utils.http import urlsafe_base64_encode

    from accounts.tokens import make_password_reset_tokens

    _, token = make_password_reset_tokens(user)
    bad_uid = urlsafe_base64_encode(force_bytes(999999))
    resp = client.post(
        "/api/accounts/password-reset/confirm/",
        {"uid": bad_uid, "token": token, "new_password": "nouveaupass456"},
        format="json",
    )
    assert resp.status_code == 400, resp.data


def test_password_reset_confirm_token_single_use(client, user):
    # Le token de reset (default_token_generator) devient invalide une fois le
    # mot de passe changé : un second usage -> 400 (verrouillage du comportement).
    from accounts.tokens import make_password_reset_tokens

    uidb64, token = make_password_reset_tokens(user)
    first = client.post(
        "/api/accounts/password-reset/confirm/",
        {"uid": uidb64, "token": token, "new_password": "nouveaupass456"},
        format="json",
    )
    assert first.status_code == 200, first.data

    second = client.post(
        "/api/accounts/password-reset/confirm/",
        {"uid": uidb64, "token": token, "new_password": "encoreautre789"},
        format="json",
    )
    assert second.status_code == 400, second.data
    # Le mot de passe n'a PAS changé une 2e fois.
    user.refresh_from_db()
    assert user.check_password("nouveaupass456")


def test_password_reset_confirm_weak_password_returns_400(client, user):
    # Nouveau mot de passe trop court -> 400 (validation serializer, min_length=8).
    from accounts.tokens import make_password_reset_tokens

    uidb64, token = make_password_reset_tokens(user)
    resp = client.post(
        "/api/accounts/password-reset/confirm/",
        {"uid": uidb64, "token": token, "new_password": "court"},
        format="json",
    )
    assert resp.status_code == 400, resp.data
    user.refresh_from_db()
    assert user.check_password("motdepasse123")


# ---------------------------------------------------------------------------
# F1 — Profil (GET / PATCH / DELETE)
# ---------------------------------------------------------------------------


def test_profile_get_requires_auth(client):
    resp = client.get("/api/accounts/profile/")
    assert resp.status_code in (401, 403)


def test_profile_get_returns_current_user(client, user):
    _auth(client, user)
    resp = client.get("/api/accounts/profile/")
    assert resp.status_code == 200, resp.data
    assert resp.data["email"] == user.email
    assert resp.data["username"] == "alice"
    # email_verified est exposé (SerializerMethodField), False par défaut.
    assert resp.data["email_verified"] is False


def test_profile_patch_first_and_last_name(client, user):
    _auth(client, user)
    resp = client.patch(
        "/api/accounts/profile/",
        {"first_name": "Alice", "last_name": "Martin"},
        format="json",
    )
    assert resp.status_code == 200, resp.data
    assert resp.data["first_name"] == "Alice"
    assert resp.data["last_name"] == "Martin"

    user.refresh_from_db()
    assert user.first_name == "Alice"
    assert user.last_name == "Martin"
    # L'email n'a pas changé -> username inchangé.
    assert user.username == "alice"


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_profile_patch_email_resets_verified_and_updates_username(client, user):
    # Changement d'email : email_verified repasse à False, username = email,
    # et un email de (re)validation est renvoyé (best-effort).
    from django.core import mail

    from accounts.models import get_or_create_profile

    # On part d'un profil déjà vérifié pour prouver la remise à False.
    profile = get_or_create_profile(user)
    profile.email_verified = True
    profile.save(update_fields=["email_verified"])

    mail.outbox = []
    _auth(client, user)

    resp = client.patch(
        "/api/accounts/profile/",
        {"email": "alice2@test.com"},
        format="json",
    )
    assert resp.status_code == 200, resp.data
    assert resp.data["email"] == "alice2@test.com"
    # email_verified est repassé à False dans la réponse ET en base.
    assert resp.data["email_verified"] is False

    user.refresh_from_db()
    assert user.email == "alice2@test.com"
    assert user.username == "alice2@test.com"  # username = email (identifiant)
    assert get_or_create_profile(user).email_verified is False

    # Un email de validation a été renvoyé à la nouvelle adresse.
    assert len(mail.outbox) == 1
    assert "alice2@test.com" in mail.outbox[0].to
    assert "/verify-email?token=" in mail.outbox[0].body


def test_profile_patch_duplicate_email_returns_400(client, user):
    # Un autre compte possède déjà l'email cible -> 400 (validate_email).
    other = User.objects.create_user(
        username="bob@test.com", email="bob@test.com", password="motdepasse123"
    )
    _auth(client, user)

    resp = client.patch(
        "/api/accounts/profile/",
        {"email": "bob@test.com"},
        format="json",
    )
    assert resp.status_code == 400, resp.data
    # L'email d'alice n'a pas été modifié.
    user.refresh_from_db()
    assert user.email == "alice@test.com"
    # bob est intact.
    assert User.objects.filter(pk=other.pk, email="bob@test.com").exists()


def test_profile_patch_same_email_is_allowed(client, user):
    # Remettre SON PROPRE email (avec une casse différente) ne doit pas être
    # considéré comme un doublon (exclude(pk=self.instance.pk)).
    _auth(client, user)
    resp = client.patch(
        "/api/accounts/profile/",
        {"email": "ALICE@test.com"},
        format="json",
    )
    assert resp.status_code == 200, resp.data
    user.refresh_from_db()
    # L'email est normalisé en minuscules par validate_email.
    assert user.email == "alice@test.com"


def test_profile_delete_requires_auth(client):
    resp = client.delete("/api/accounts/profile/")
    assert resp.status_code in (401, 403)


def test_profile_delete_wrong_password_returns_400(client, user):
    _auth(client, user)
    resp = client.delete(
        "/api/accounts/profile/",
        {"password": "mauvais"},
        format="json",
    )
    assert resp.status_code == 400, resp.data
    # Le compte existe toujours.
    assert User.objects.filter(pk=user.pk).exists()


def test_profile_delete_correct_password_deletes_account_and_cascade(client, user):
    # Bon mot de passe -> compte supprimé (et Profile en cascade via on_delete=CASCADE).
    from accounts.models import Profile, get_or_create_profile

    get_or_create_profile(user)  # s'assure qu'un Profile existe
    user_pk = user.pk
    _auth(client, user)

    resp = client.delete(
        "/api/accounts/profile/",
        {"password": "motdepasse123"},
        format="json",
    )
    assert resp.status_code == 204, getattr(resp, "data", resp)
    assert not User.objects.filter(pk=user_pk).exists()
    # Suppression en cascade du profil.
    assert not Profile.objects.filter(user_id=user_pk).exists()


# ---------------------------------------------------------------------------
# F1 — Changement de mot de passe (change-password/)
# ---------------------------------------------------------------------------


def test_change_password_requires_auth(client):
    resp = client.post(
        "/api/accounts/change-password/",
        {"old_password": "motdepasse123", "new_password": "nouveaupass456"},
        format="json",
    )
    assert resp.status_code in (401, 403)


def test_change_password_wrong_old_password_returns_400(client, user):
    # Ancien mot de passe faux -> 400, mot de passe INCHANGÉ.
    _auth(client, user)
    resp = client.post(
        "/api/accounts/change-password/",
        {"old_password": "mauvais", "new_password": "nouveaupass456"},
        format="json",
    )
    assert resp.status_code == 400, resp.data
    user.refresh_from_db()
    assert user.check_password("motdepasse123")


def test_change_password_success_changes_password_and_returns_new_token(client, user):
    # Succès : le mot de passe change et un NOUVEAU token est renvoyé (l'ancien
    # est invalidé et régénéré par la vue).
    from rest_framework.authtoken.models import Token

    old_token = Token.objects.create(user=user)
    client.credentials(HTTP_AUTHORIZATION=f"Token {old_token.key}")

    resp = client.post(
        "/api/accounts/change-password/",
        {"old_password": "motdepasse123", "new_password": "nouveaupass456"},
        format="json",
    )
    assert resp.status_code == 200, resp.data
    assert "token" in resp.data
    # Un nouveau token, différent de l'ancien.
    assert resp.data["token"] != old_token.key
    assert not Token.objects.filter(key=old_token.key).exists()
    assert Token.objects.filter(key=resp.data["token"], user=user).exists()

    # Le mot de passe a bien changé en base.
    user.refresh_from_db()
    assert user.check_password("nouveaupass456")
    assert not user.check_password("motdepasse123")


def test_change_password_weak_new_password_returns_400(client, user):
    # Nouveau mot de passe trop court -> 400 (validation), mot de passe inchangé.
    _auth(client, user)
    resp = client.post(
        "/api/accounts/change-password/",
        {"old_password": "motdepasse123", "new_password": "court"},
        format="json",
    )
    assert resp.status_code == 400, resp.data
    user.refresh_from_db()
    assert user.check_password("motdepasse123")
