# Spécification — Mise en conformité RGPD d'EduTutor IA

- **Date** : 2026-07-01
- **Statut** : Validé par le PO — prêt à implémenter
- **Projet** : EduTutor IA (Équipe 13, IPSSI, semaine APOCAL'IPSSI 2026)
- **Stack** : Backend Django + Django REST Framework ; Frontend React + Vite + TypeScript + Tailwind
- **Auteur** : Équipe 13
- **Version du consentement introduite** : `2026-07-01`

Ce document retranscrit fidèlement les décisions validées. Il est organisé par les 12 sections attendues, avec les chemins de fichiers et noms de fonctions exacts, prêt à implémenter sans deviner.

---

## 1. Contexte & objectif

EduTutor IA collecte des données personnelles (email, nom, prénom, texte des cours téléversés, historique de quiz) et peut envoyer le texte des cours (`Quiz.source_text`) à des fournisseurs LLM, dont certains hébergés hors Union européenne. Le code actuel contient déjà des marqueurs `TODO J3-bis RGPD` (dans `backend/accounts/views.py`, `frontend/src/pages/ProfilePage.tsx`) signalant que la conformité RGPD reste à finaliser.

Trois manques bloquent la conformité :

1. **Droit à la portabilité (RGPD art. 20)** : l'utilisateur ne peut pas récupérer une copie de ses données. Le bouton « Exporter mes données » de `ProfilePage.tsx` est désactivé (`disabled`, libellé « bientôt »).
2. **Consentement à l'inscription** : aucune trace du consentement de l'utilisateur aux CGU et à la politique de confidentialité n'est enregistrée (ni à quelle version).
3. **Information légale** : les 4 pages légales (`Confidentialité`, `Mentions légales`, `CGU`, `Cookies`) sont des gabarits vierges qui affichent « À compléter — {hint} » au lieu d'un contenu réel.

**Objectif** : livrer une base conforme au RGPD en comblant ces trois manques, en réutilisant les patterns existants du codebase (notamment le pattern `django.core.signing` — fonctions `signing.dumps`/`signing.loads` — déjà employé dans `accounts/tokens.py`) pour ne pas introduire de dette technique ni de stockage de token superflu en base.

---

## 2. Objectifs / hors-périmètre

### 2.1. Objectifs (dans le périmètre)

1. **Export des données utilisateur (portabilité)** — flux **asynchrone par lien email** : l'utilisateur authentifié demande son export ; il reçoit un email contenant un lien signé, temporaire (1 h), qui déclenche le téléchargement d'un fichier JSON contenant toutes ses données.
2. **Rappel « exporter avant suppression »** — dans la Zone de danger de `ProfilePage.tsx`, un bouton non bloquant « Exporter mes données d'abord » réutilisant le même flux d'export.
3. **Consentement à l'inscription** — enregistrement de la date et de la version du consentement dans `Profile` ; case à cocher obligatoire sur le formulaire d'inscription.
4. **Rédaction des 4 pages légales** — contenu réel adapté à EduTutor IA (Confidentialité, Mentions légales, CGU, Cookies), via une extension rétrocompatible du gabarit `LegalScaffold`.

### 2.2. Hors-périmètre (explicitement exclu de ce lot)

- **Pas de suppression logique (soft delete)** : la suppression de compte reste un **hard delete** (comportement actuel de `ProfileView.delete`). On ne change pas ce comportement ; on retire simplement le commentaire `TODO J3-bis RGPD` obsolète une fois l'export livré (voir §4.6).
- **Pas de génération asynchrone via worker/Celery** : « asynchrone » désigne ici le **découplage demande / téléchargement via lien email**, pas une file de tâches. L'export JSON est calculé à la volée à la requête de téléchargement.
- **Pas de stockage de fichiers d'export** : aucun fichier n'est écrit sur disque ni en base ; le JSON est sérialisé en mémoire et renvoyé en pièce jointe.
- **Pas de bannière cookies** : le site n'utilise que des cookies/stockages techniques (session Django, token DRF en `localStorage`). Aucun traceur ⇒ pas de consentement cookies requis (documenté, pas implémenté).
- **Pas de mise en place d'un registre des traitements formel** ni de DPO nommé : les informations que seule l'équipe connaît sont balisées `[à compléter : ...]` (voir §11).
- **Pas de modification du flux LLM** : on documente les destinataires et transferts hors UE, on ne change pas `LLM_BACKEND` ni le code d'appel LLM.

---

## 3. Modèle de données (changements Profile + migration)

### 3.1. Fichier `backend/accounts/models.py` — modèle `Profile`

Ajouter **deux champs** au modèle `Profile` existant (qui contient déjà `user` OneToOne, `email_verified: BooleanField`, `created_at: DateTimeField(auto_now_add=True)`) :

```python
# backend/accounts/models.py — dans class Profile, après created_at

    # --- Consentement RGPD (traçabilité du consentement à l'inscription) ---
    # Date/heure à laquelle l'utilisateur a accepté les CGU et la politique de
    # confidentialité. NULL pour les comptes créés AVANT l'introduction du
    # consentement (rétrocompatibilité).
    consent_accepted_at = models.DateTimeField(null=True, blank=True)
    # Version des CGU/politique acceptée (permet de re-solliciter le consentement
    # si les documents changent). Vide pour les comptes historiques.
    consent_version = models.CharField(max_length=20, blank=True, default="")
```

Ajouter en tête de `models.py` une constante de version du consentement, importable ailleurs :

```python
# backend/accounts/models.py — au niveau module, après les imports

# Version courante des CGU / politique de confidentialité. À incrémenter
# (nouvelle date) quand ces documents changent de façon substantielle.
CURRENT_CONSENT_VERSION = "2026-07-01"
```

Contraintes de conception :
- `consent_accepted_at` est **nullable** (comptes historiques sans consentement enregistré).
- `consent_version` est un `CharField(max_length=20, blank=True, default="")` (jamais `null` pour un champ texte, convention Django).
- La fonction existante `get_or_create_profile(user)` **n'est pas modifiée** : elle continue de créer un `Profile` avec `consent_accepted_at=None` / `consent_version=""` par défaut. Le renseignement du consentement est fait explicitement par `SignupSerializer.create` (voir §4.5).

### 3.2. Migration Django

Créer la migration **`backend/accounts/migrations/0002_profile_consent.py`** (numéro `0002`, la seule migration existante étant `0001_initial.py`).

Génération :

```bash
cd backend
python manage.py makemigrations accounts
```

Contenu attendu (équivalent) :

```python
# backend/accounts/migrations/0002_profile_consent.py
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="profile",
            name="consent_accepted_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="profile",
            name="consent_version",
            field=models.CharField(blank=True, default="", max_length=20),
        ),
    ]
```

Migration **additive et non destructive** : ajout de deux colonnes nullable/à défaut vide, sans data migration. Les profils existants gardent `consent_accepted_at=NULL` et `consent_version=""`.

Application :

```bash
python manage.py migrate accounts
```

---

## 4. API backend (endpoints, méthodes, permissions, payloads, structure du JSON d'export)

### 4.1. Vue d'ensemble des endpoints ajoutés

| Méthode | Chemin | Vue | Permission | Auth de requête |
|---|---|---|---|---|
| POST | `/api/accounts/export/request/` | `RequestExportView` | `IsAuthenticated` | Token/Session DRF (utilisateur connecté) |
| GET | `/api/accounts/export/download/?token=...` | `DownloadExportView` | `AllowAny` | **Le token signé** (dans la query string) |

Le préfixe `/api/accounts/` est celui déjà en place (`backend/accounts/urls.py`).

### 4.2. Nouveau module `backend/accounts/export.py`

Fonction unique de construction du dictionnaire d'export.

```python
# backend/accounts/export.py
"""
Construction de l'export RGPD (droit à la portabilité, art. 20).

On assemble un dictionnaire JSON-sérialisable regroupant TOUTES les données
personnelles d'un utilisateur : son compte, son profil (dont le consentement),
ses quiz et les questions associées. Aucune donnée d'un autre utilisateur n'est
incluse (isolation stricte par `user`).
"""

from .models import get_or_create_profile


def build_user_export(user) -> dict:
    """Renvoie un dict JSON-sérialisable de toutes les données de `user`.

    Structure documentée en §4.4 de la spec RGPD. Ne fait AUCUN accès aux
    données d'autres utilisateurs : on part de `user` et on suit ses relations
    (`user.quizzes` -> `quiz.questions`).
    """
    profile = get_or_create_profile(user)

    quizzes = []
    # `related_name="quizzes"` sur Quiz.user ; `related_name="questions"` sur Question.quiz
    for quiz in user.quizzes.all().order_by("created_at"):
        questions = [
            {
                "index": q.index,
                "prompt": q.prompt,
                "options": q.options,
                "correct_index": q.correct_index,
                "selected_index": q.selected_index,
            }
            for q in quiz.questions.all().order_by("index")
        ]
        quizzes.append(
            {
                "title": quiz.title,
                "source_text": quiz.source_text,
                "score": quiz.score,
                "created_at": quiz.created_at.isoformat(),
                "updated_at": quiz.updated_at.isoformat(),
                "questions": questions,
            }
        )

    return {
        "compte": {
            "id": user.id,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "date_joined": user.date_joined.isoformat(),
        },
        "profil": {
            "email_verified": profile.email_verified,
            "created_at": profile.created_at.isoformat(),
            "consentement": {
                "consent_accepted_at": (
                    profile.consent_accepted_at.isoformat()
                    if profile.consent_accepted_at
                    else None
                ),
                "consent_version": profile.consent_version or None,
            },
        },
        "quizzes": quizzes,
    }
```

Notes :
- Les dates sont sérialisées en **ISO 8601** (`.isoformat()`) pour rester JSON-natif.
- `options` est déjà un `JSONField` (liste) : inséré tel quel.
- Aucune donnée sensible interne (mot de passe hashé, tokens) n'est exportée.

### 4.3. Tokens d'export — `backend/accounts/tokens.py`

Réutiliser le pattern `django.core.signing` (comme `make_email_verify_token` / `read_email_verify_token`) avec un **salt dédié** et une **expiration courte (1 h)**.

Ajouter en tête du fichier, à côté des constantes existantes :

```python
# backend/accounts/tokens.py — après EMAIL_VERIFY_MAX_AGE

EXPORT_SALT = "accounts.data-export"
EXPORT_MAX_AGE = 60 * 60  # 1 heure en secondes
```

Ajouter les deux fonctions (mêmes conventions que `make_email_verify_token` / `read_email_verify_token`) :

```python
# backend/accounts/tokens.py — nouvelle section

# --- Export RGPD (token signé temporel, sans stockage en base) ---


def make_export_token(user) -> str:
    """Crée un token signé (valable 1 h) autorisant le téléchargement de l'export de `user`."""
    return signing.dumps({"uid": user.pk}, salt=EXPORT_SALT)


def read_export_token(token: str) -> int | None:
    """Renvoie l'id utilisateur si le token d'export est valide et non expiré, sinon None."""
    try:
        data = signing.loads(token, salt=EXPORT_SALT, max_age=EXPORT_MAX_AGE)
        return data.get("uid")
    except signing.BadSignature:
        return None
```

Le module importe déjà `from django.core import signing` — aucun import supplémentaire.

### 4.4. Structure exacte du JSON d'export

Le fichier téléchargé est un JSON UTF-8 de la forme suivante (exemple illustratif) :

```json
{
  "compte": {
    "id": 42,
    "email": "alice@example.com",
    "first_name": "Alice",
    "last_name": "Durand",
    "date_joined": "2026-06-01T10:12:33.456789+00:00"
  },
  "profil": {
    "email_verified": true,
    "created_at": "2026-06-01T10:12:33.500000+00:00",
    "consentement": {
      "consent_accepted_at": "2026-06-01T10:12:33.400000+00:00",
      "consent_version": "2026-07-01"
    }
  },
  "quizzes": [
    {
      "title": "Chapitre 3 — La Révolution française",
      "source_text": "Texte du cours téléversé...",
      "score": 8,
      "created_at": "2026-06-02T09:00:00+00:00",
      "updated_at": "2026-06-02T09:30:00+00:00",
      "questions": [
        {
          "index": 1,
          "prompt": "En quelle année débute la Révolution française ?",
          "options": ["1789", "1799", "1804", "1815"],
          "correct_index": 0,
          "selected_index": 0
        }
      ]
    }
  ]
}
```

Champs, par clé racine :

- **`compte`** : `id` (int), `email` (str), `first_name` (str), `last_name` (str), `date_joined` (str ISO 8601).
- **`profil`** : `email_verified` (bool), `created_at` (str ISO 8601), `consentement` : `{ consent_accepted_at: str ISO 8601 | null, consent_version: str | null }`.
- **`quizzes`** : liste ; chaque quiz : `title` (str), `source_text` (str), `score` (int | null), `created_at` (str ISO 8601), `updated_at` (str ISO 8601), `questions` : liste ; chaque question : `index` (int), `prompt` (str), `options` (liste de str), `correct_index` (int), `selected_index` (int | null).

### 4.5. Vues et sérialiseur

#### 4.5.1. `RequestExportView` — `backend/accounts/views.py`

```python
# backend/accounts/views.py

from .export import build_user_export  # (import en tête de fichier)
from .emails import (
    EmailError,
    send_export_email,          # <-- nouvel import
    send_password_reset_email,
    send_verification_email,
)
from .tokens import (
    make_export_token,          # <-- nouvel import
    read_email_verify_token,
    read_export_token,          # <-- nouvel import
    read_password_reset_tokens,
)


class RequestExportView(APIView):
    """Demande d'export RGPD : envoie par email un lien de téléchargement temporaire."""

    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: OpenApiResponse(description="Lien d'export envoyé par email")})
    def post(self, request):
        user = request.user
        token = make_export_token(user)
        download_url = request.build_absolute_uri(
            f"/api/accounts/export/download/?token={token}"
        )
        # Best-effort : on ne bloque pas si l'email n'part pas (mode console en dev,
        # clé Brevo expirée en prod). Réponse GÉNÉRIQUE dans tous les cas.
        try:
            send_export_email(user, download_url)
        except EmailError as exc:
            logger.warning("Email d'export non envoyé pour %s : %s", user.email, exc)
        return Response(
            {
                "detail": "Un lien de téléchargement de vos données vient de vous "
                "être envoyé par email. Il est valable 1 heure."
            }
        )
```

Décisions :
- **Permission `IsAuthenticated`** : seul l'utilisateur connecté peut demander SON export ; le token est émis pour `request.user`, jamais pour un autre.
- Le lien pointe **directement sur l'endpoint backend** de téléchargement (pas le frontend), construit avec `request.build_absolute_uri` pour être absolu et respecter le schéma/host courant (HTTPS en prod derrière Caddy).
- Réponse **générique** (« lien envoyé »), quel que soit le résultat de l'envoi — cohérent avec l'anti-énumération déjà pratiqué dans `PasswordResetRequestView`.

#### 4.5.2. `DownloadExportView` — `backend/accounts/views.py`

```python
# backend/accounts/views.py
import json

from django.http import HttpResponse


class DownloadExportView(APIView):
    """Téléchargement de l'export : authentifié PAR LE TOKEN signé (pas par session)."""

    permission_classes = [AllowAny]
    authentication_classes = []  # endpoint public : l'autorisation vient du token signé

    @extend_schema(responses={200: OpenApiResponse(description="Fichier JSON en pièce jointe")})
    def get(self, request):
        token = request.query_params.get("token", "")
        uid = read_export_token(token)
        if uid is None:
            return Response(
                {"detail": "Lien d'export invalide ou expiré."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            user = User.objects.get(pk=uid)
        except User.DoesNotExist:
            return Response(
                {"detail": "Utilisateur introuvable."}, status=status.HTTP_400_BAD_REQUEST
            )

        data = build_user_export(user)
        payload = json.dumps(data, ensure_ascii=False, indent=2)
        response = HttpResponse(payload, content_type="application/json; charset=utf-8")
        response["Content-Disposition"] = (
            f'attachment; filename="edututor-export-{user.id}.json"'
        )
        return response
```

Décisions :
- **`permission_classes = [AllowAny]` + `authentication_classes = []`** : l'endpoint est ouvert car il est atteint depuis un client email (pas de header d'auth). L'**autorisation réelle vient du token signé**, qui encode l'`uid` et est vérifié par `read_export_token` (signature + expiration 1 h). Même schéma de sécurité que `VerifyEmailView`.
- Réponse en **pièce jointe** : `Content-Disposition: attachment; filename="edututor-export-{id}.json"`, `Content-Type: application/json; charset=utf-8`.
- `ensure_ascii=False` pour préserver les accents ; `indent=2` pour un fichier lisible.
- On renvoie un `HttpResponse` brut (pas un `Response` DRF) car le corps est un fichier, pas une ressource négociée.

#### 4.5.3. `SignupSerializer` — champ `accept_terms` — `backend/accounts/serializers.py`

Ajouter un champ `accept_terms` **write-only, requis, booléen**, refusé s'il n'est pas `True`, et renseigner le consentement à la création.

```python
# backend/accounts/serializers.py
from django.utils import timezone

from .models import CURRENT_CONSENT_VERSION, get_or_create_profile  # ajout de CURRENT_CONSENT_VERSION


class SignupSerializer(serializers.ModelSerializer):
    """Inscription par EMAIL (identifiant). Le username interne = email."""

    password = serializers.CharField(
        write_only=True,
        min_length=8,
        style={"input_type": "password"},
        help_text="Au moins 8 caractères.",
    )
    accept_terms = serializers.BooleanField(
        write_only=True,
        help_text="L'utilisateur doit accepter les CGU et la politique de confidentialité.",
    )

    class Meta:
        model = User
        fields = ["email", "password", "first_name", "last_name", "accept_terms"]
        extra_kwargs = {
            "email": {"required": True, "allow_blank": False},
            "first_name": {"required": False},
            "last_name": {"required": False},
        }

    # validate_email / validate_password : INCHANGÉS (voir code existant)

    def validate_accept_terms(self, value: bool) -> bool:
        if value is not True:
            raise serializers.ValidationError(
                "Vous devez accepter les CGU et la politique de confidentialité "
                "pour créer un compte."
            )
        return value

    def create(self, validated_data: dict) -> User:
        password = validated_data.pop("password")
        validated_data.pop("accept_terms")  # non stocké sur User : on le trace sur le Profile
        email = validated_data["email"]
        user = User(username=email, **validated_data)  # username = email (identifiant)
        user.set_password(password)
        user.save()
        profile = get_or_create_profile(user)  # profil avec email_verified=False
        profile.consent_accepted_at = timezone.now()
        profile.consent_version = CURRENT_CONSENT_VERSION
        profile.save(update_fields=["consent_accepted_at", "consent_version"])
        return user
```

Décisions :
- `accept_terms` est **requis** : `BooleanField` sans `default` ⇒ un payload sans ce champ échoue en 400. Un `false` explicite échoue via `validate_accept_terms`.
- `accept_terms` est **retiré de `validated_data`** avant `User(...)` (ce n'est pas un champ du modèle User).
- Le consentement est horodaté avec `timezone.now()` et versionné avec `CURRENT_CONSENT_VERSION` (constante `2026-07-01`).

### 4.6. Nettoyage des `TODO J3-bis RGPD`

Une fois l'export livré, **retirer** le commentaire obsolète dans `ProfileView.delete` (`backend/accounts/views.py`, lignes ~271-273) :

```python
# AVANT (à supprimer) :
        # [TODO J3-bis RGPD] Avant de supprimer, proposer un export des données
        #   personnelles (droit à la portabilité). Voir Lot futur "export RGPD".
# APRÈS (remplacement) :
        # Suppression DURE (hard delete) confirmée par mot de passe. L'export RGPD
        # (droit à la portabilité) est disponible via /api/accounts/export/request/
        # et rappelé côté front dans la Zone de danger avant suppression.
```

La suppression reste un hard delete (hors-périmètre §2.2). Aucune autre modification de `ProfileView.delete`.

### 4.7. Routes — `backend/accounts/urls.py`

Ajouter les imports et les deux routes :

```python
# backend/accounts/urls.py
from .views import (
    ChangePasswordView,
    DownloadExportView,   # <-- ajout
    LoginView,
    LogoutView,
    MeView,
    PasswordResetConfirmView,
    PasswordResetRequestView,
    ProfileView,
    RequestExportView,    # <-- ajout
    ResendVerificationView,
    SignupView,
    VerifyEmailView,
)

urlpatterns = [
    # ... routes existantes ...
    # Export RGPD (droit à la portabilité, art. 20)
    path("export/request/", RequestExportView.as_view(), name="export-request"),
    path("export/download/", DownloadExportView.as_view(), name="export-download"),
]
```

Placer ce bloc après les routes `profile/` et `change-password/` existantes.

---

## 5. Sécurité du token d'export

Le token d'export réutilise `django.core.signing` (HMAC-signé avec `SECRET_KEY`), au même titre que le token de validation d'email existant. Propriétés de sécurité, décision par décision :

1. **Token signé temporel** : `signing.dumps({"uid": user.pk}, salt=EXPORT_SALT)` produit un jeton **inviolable** (toute altération casse la signature ⇒ `BadSignature` ⇒ `None`). Le contenu (`uid`) n'est pas chiffré mais il est signé : un attaquant ne peut ni forger ni modifier un token pour cibler un autre utilisateur.
2. **Expiration courte (1 h)** : `EXPORT_MAX_AGE = 60 * 60`. Passé ce délai, `signing.loads(..., max_age=EXPORT_MAX_AGE)` lève `SignatureExpired` (sous-classe de `BadSignature`) ⇒ `read_export_token` renvoie `None` ⇒ HTTP 400. Un lien qui traîne dans une boîte mail périmée est inexploitable.
3. **Salt dédié** : `EXPORT_SALT = "accounts.data-export"`, distinct de `EMAIL_VERIFY_SALT`. Un token de validation d'email ne peut **pas** être rejoué comme token d'export (et réciproquement) : le salt fait partie du calcul de signature.
4. **Isolation par utilisateur** : `build_user_export(user)` ne lit que `user`, `user.profile`, `user.quizzes` et leurs `questions`. Aucune requête transverse ; impossible d'exfiltrer les données d'un tiers même avec un `uid` valide, car le JSON est toujours construit à partir de l'utilisateur encodé dans le token.
5. **Pas d'énumération** :
   - `RequestExportView` exige `IsAuthenticated` : on ne peut demander un export que pour soi-même ; le endpoint ne prend aucun paramètre d'identité en entrée.
   - `DownloadExportView` renvoie un message **générique** (« Lien d'export invalide ou expiré. ») pour token invalide, expiré, ou `uid` introuvable — sans distinguer les cas, donc sans révéler l'existence d'un compte.
6. **Pas de stockage** : aucun token ni fichier d'export n'est persistté (ni en base, ni sur disque). Rien à voler côté serveur ; la révocation implicite est assurée par l'expiration.
7. **Transport** : en production, le backend est servi derrière Caddy en HTTPS (`DJANGO_SECURE_PROD`), donc le token en query string circule chiffré. Le lien étant à usage court et lié à l'email du titulaire, le risque de fuite via l'historique/referer est limité par l'expiration 1 h.
8. **Auth par token uniquement sur le download** : `DownloadExportView` a `authentication_classes = []` (aucune session/CSRF requise), l'autorisation venant exclusivement du token signé — cohérent avec `VerifyEmailView`. `RequestExportView`, lui, s'appuie sur l'authentification standard de l'utilisateur connecté.

---

## 6. Changements frontend (fichier par fichier)

### 6.1. `frontend/src/api/auth.ts` — nouvelle fonction `requestDataExport()`

Ajouter, dans la section « Profil » (après `deleteAccount`) :

```ts
// frontend/src/api/auth.ts

/**
 * Demande un export RGPD des données personnelles (droit à la portabilité).
 * Le backend envoie par email un lien de téléchargement valable 1 h.
 * Renvoie le message de confirmation (`detail`).
 */
export async function requestDataExport(): Promise<string> {
  const { data } = await api.post<{ detail: string }>('/accounts/export/request/');
  return data.detail;
}
```

Aucune fonction de téléchargement direct côté front : le lien est dans l'email et pointe sur le backend.

### 6.2. `frontend/src/pages/ProfilePage.tsx` — activer l'export + rappel avant suppression

**6.2.1. En-tête** — retirer/mettre à jour le `TODO J3-bis RGPD` du docblock (lignes ~13-14) :

```
- * [TODO J3-bis RGPD] Ajouter ici un bouton « Exporter mes données » (droit à la
- *   portabilité) — placeholder présent plus bas, à implémenter pendant la semaine.
+ * L'export RGPD (droit à la portabilité) est disponible dans la zone « Mes
+ *   données » (bouton actif) et rappelé dans la Zone de danger avant suppression.
```

**6.2.2. Import** — ajouter `requestDataExport` :

```ts
import { changePassword, deleteAccount, requestProfileExport as _unused, updateProfile } from '@/api/auth';
```
> Correction : l'import exact est :
```ts
import { changePassword, deleteAccount, requestDataExport, updateProfile } from '@/api/auth';
```

**6.2.3. État** — ajouter, à côté des autres `useState`, l'état du flux d'export :

```ts
  // --- Export RGPD (portabilité) ---
  const [exportMsg, setExportMsg] = useState<string | null>(null);
  const [exportErr, setExportErr] = useState<string | null>(null);
  const [exportLoading, setExportLoading] = useState(false);

  const handleExport = async () => {
    setExportMsg(null);
    setExportErr(null);
    setExportLoading(true);
    try {
      const detail = await requestDataExport();
      setExportMsg(detail);
    } catch (err) {
      setExportErr(getApiErrorMessage(err, 'Demande d’export impossible.'));
    } finally {
      setExportLoading(false);
    }
  };
```

**6.2.4. Zone « Mes données »** — remplacer le bouton désactivé « Exporter mes données (bientôt) » (lignes ~224-247) par un bouton actif branché sur `handleExport`, et conserver le bouton « Signaler un contenu (bientôt) » désactivé (hors-périmètre) :

```tsx
      {/* Mes données (RGPD) */}
      <section className="card bg-slate-50">
        <h2 className="text-lg font-semibold text-slate-900 mb-2">Mes données</h2>
        <p className="text-sm text-slate-500 mb-4">
          Vous pouvez récupérer une copie de toutes vos données (compte, profil,
          quiz). Un lien de téléchargement sécurisé, valable 1 heure, vous sera
          envoyé par email.
        </p>
        {exportMsg && (
          <div className="mb-4 p-3 bg-emerald-50 border-l-4 border-emerald-500 text-sm text-emerald-900 rounded">
            {exportMsg}
          </div>
        )}
        {exportErr && (
          <div className="mb-4 p-3 bg-rose-50 border-l-4 border-rose-500 text-sm text-rose-900 rounded">
            {exportErr}
          </div>
        )}
        <div className="flex flex-wrap gap-3">
          <button
            type="button"
            onClick={handleExport}
            disabled={exportLoading}
            className="btn-secondary"
          >
            {exportLoading ? 'Envoi du lien…' : 'Exporter mes données'}
          </button>
          <button
            type="button"
            disabled
            title="À implémenter (J4) — signalement de contenu"
            className="btn-secondary opacity-60 cursor-not-allowed"
          >
            Signaler un contenu (bientôt)
          </button>
        </div>
      </section>
```

**6.2.5. Zone de danger** — ajouter le rappel + bouton **non bloquant** « Exporter mes données d'abord » (même flux `handleExport`), au-dessus du formulaire de suppression, sans modifier `handleDelete` :

```tsx
        <p className="text-sm text-slate-600 mb-4">
          Avant de supprimer, vous pouvez récupérer une copie de vos données.
        </p>
        <button
          type="button"
          onClick={handleExport}
          disabled={exportLoading}
          className="btn-secondary mb-4"
        >
          {exportLoading ? 'Envoi du lien…' : 'Exporter mes données d’abord'}
        </button>
```

Ce bouton est **non bloquant** : la suppression reste possible sans exporter ; il ne conditionne pas `delConfirm`/`delLoading`.

### 6.3. `frontend/src/api/auth.ts` — signature `signup` (champ `accept_terms`)

Étendre le type d'entrée de `signup` pour transmettre `accept_terms` au backend :

```ts
export async function signup(input: {
  email: string;
  password: string;
  first_name?: string;
  last_name?: string;
  accept_terms: boolean;   // <-- requis par le backend
}): Promise<User> {
  const { data } = await api.post<User>('/accounts/signup/', input);
  await login(input.email, input.password);
  return data;
}
```

### 6.4. `frontend/src/pages/SignupPage.tsx` — case à cocher obligatoire

**6.4.1. État** — ajouter :

```ts
  const [acceptTerms, setAcceptTerms] = useState(false);
```

**6.4.2. Soumission** — transmettre `accept_terms` :

```ts
      await signup({
        email,
        password,
        first_name: firstName || undefined,
        last_name: lastName || undefined,
        accept_terms: acceptTerms,
      });
```

**6.4.3. Champ** — ajouter, dans le `<form>` juste avant le bouton de soumission, la case à cocher avec liens vers `/legal/cgu` et `/legal/confidentialite` :

```tsx
          <label className="flex items-start gap-2 text-sm text-slate-700">
            <input
              type="checkbox"
              required
              checked={acceptTerms}
              onChange={(e) => setAcceptTerms(e.target.checked)}
              className="mt-1"
            />
            <span>
              J’accepte les{' '}
              <Link to="/legal/cgu" className="text-indigo-600 hover:underline" target="_blank">
                CGU
              </Link>{' '}
              et la{' '}
              <Link to="/legal/confidentialite" className="text-indigo-600 hover:underline" target="_blank">
                politique de confidentialité
              </Link>
              .
            </span>
          </label>
```

**6.4.4. Bouton** — bloquer la soumission tant que la case n'est pas cochée :

```tsx
          <button type="submit" disabled={loading || !acceptTerms} className="btn-primary w-full">
            {loading ? 'Création du compte…' : 'Créer mon compte'}
          </button>
```

Double protection : `required` sur l'input (validation HTML native) **et** `disabled={... || !acceptTerms}` sur le bouton. `Link` est déjà importé de `react-router-dom` dans ce fichier.

### 6.5. `frontend/src/pages/legal/LegalScaffold.tsx` — extension rétrocompatible

Étendre le type `LegalSection` avec un champ `content?: ReactNode` optionnel. Si `content` est fourni, rendre le **contenu réel** ; sinon, conserver le comportement actuel (« À compléter — {hint} »). Le bandeau amber « Page à compléter » ne doit s'afficher **que** s'il reste au moins une section sans `content`.

```tsx
// frontend/src/pages/legal/LegalScaffold.tsx
import type { ReactNode } from 'react';

export const REGLEMENTATION_URL = 'https://mohamedelafrit.com/teaching/Reglementation_des_Donnees';

export type LegalSection = {
  /** Titre de la rubrique (ce que la loi attend de voir). */
  title: string;
  /** Indication pour l'équipe : quoi écrire (affichée seulement si `content` absent). */
  hint: string;
  /** Contenu réel de la rubrique. Si présent, remplace le placeholder "À compléter". */
  content?: ReactNode;
};

type Props = {
  title: string;
  intro: string;
  sections: LegalSection[];
  /** Date de dernière mise à jour affichée en pied de page. */
  updatedAt?: string;
  children?: ReactNode;
};

export default function LegalScaffold({ title, intro, sections, updatedAt, children }: Props) {
  const hasDrafts = sections.some((s) => s.content == null);

  return (
    <article className="max-w-3xl mx-auto">
      <h1 className="text-3xl font-bold text-slate-900 mb-2">{title}</h1>
      <p className="text-slate-600 mb-6">{intro}</p>

      {hasDrafts && (
        <div className="mb-8 p-4 bg-amber-50 border-l-4 border-amber-400 rounded text-sm text-amber-900">
          <p className="font-semibold mb-1">📝 Page à compléter par votre équipe</p>
          <p>
            Certaines rubriques restent à rédiger. Besoin d'aide ?{' '}
            <a
              href={REGLEMENTATION_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="text-indigo-700 underline hover:no-underline font-medium"
            >
              Consultez le cours « Réglementation des données »
            </a>
            .
          </p>
        </div>
      )}

      <div className="space-y-6">
        {sections.map((section, i) => (
          <section key={section.title}>
            <h2 className="text-lg font-semibold text-slate-900 mb-1">
              {i + 1}. {section.title}
            </h2>
            {section.content != null ? (
              <div className="text-sm text-slate-700 space-y-2">{section.content}</div>
            ) : (
              <p className="text-sm text-slate-500 italic">À compléter — {section.hint}</p>
            )}
          </section>
        ))}
      </div>

      {children}

      <p className="text-xs text-slate-400 mt-10 pt-4 border-t border-slate-200">
        Dernière mise à jour : <em>{updatedAt ?? 'à compléter'}</em>. Document rédigé dans le
        cadre pédagogique APOCAL'IPSSI 2026.
      </p>
    </article>
  );
}
```

Rétrocompatibilité assurée :
- `content` est **optionnel** ; toute page existante passant des sections sans `content` conserve exactement l'affichage actuel.
- `updatedAt` est optionnel ; par défaut « à compléter » comme aujourd'hui.
- Aucune signature de props existante n'est retirée.

Les 4 pages légales (§7) fournissent désormais `content` sur toutes leurs sections et un `updatedAt="1er juillet 2026"`, ce qui masque automatiquement le bandeau amber.

---

## 7. Contenu des 4 pages légales (rédigé)

Chaque page (`frontend/src/pages/legal/*.tsx`) passe un tableau `SECTIONS: LegalSection[]` où chaque entrée porte un `content` (JSX). Le texte ci-dessous est le **contenu réel** à insérer. Les seules zones laissées à l'équipe sont balisées `[à compléter : ...]` (récapitulées en §11).

Constantes communes à réutiliser dans le contenu :
- **Éditeur** : Équipe 13 — IPSSI (projet pédagogique APOCAL'IPSSI 2026).
- **Produit** : EduTutor IA.
- **URL de production** : `https://apocalipssi26.elafrit.com`.
- **Hébergeur** : OVH SAS, 2 rue Kellermann, 59100 Roubaix, France — téléphone 1007 (VPS OVHcloud, Ubuntu 24.04 LTS).
- **Version du consentement / date de mise à jour** : 1er juillet 2026 (`2026-07-01`).

### 7.1. `ConfidentialitePage.tsx` — Politique de confidentialité

Conserver l'ordre des 10 rubriques existantes, en fournissant un `content` pour chacune.

1. **Responsable du traitement** — « Le responsable du traitement est l'Équipe 13 du projet EduTutor IA, réalisé dans le cadre pédagogique APOCAL'IPSSI 2026 à l'IPSSI. Contact : [à compléter : email du référent données de l'équipe]. Adresse postale : [à compléter : adresse postale de l'éditeur]. »

2. **Données personnelles collectées** — liste :
   - Données de compte : **adresse email** (identifiant de connexion), **nom**, **prénom** (facultatifs).
   - Données de contenu : **texte des cours** que vous téléversez ou collez (`source_text`), utilisé pour générer les quiz.
   - Données d'usage pédagogique : **quiz générés** (titre, questions, options, bonne réponse) et **historique de réponses** (réponse sélectionnée, score obtenu).
   - Données techniques : indicateur de **vérification de l'email**, dates de création du compte et des quiz, **date et version du consentement**.
   - Nous ne collectons **pas** de données sensibles au sens de l'art. 9 du RGPD, et vous demandons de ne pas insérer de telles données dans le texte des cours.

3. **Finalités du traitement** — « Vos données sont traitées pour : (a) créer et gérer votre compte et vous authentifier ; (b) générer des quiz à partir du texte de vos cours ; (c) conserver votre historique de quiz et vos scores pour votre suivi pédagogique ; (d) vous envoyer les emails de service (confirmation d'adresse, réinitialisation de mot de passe, export de vos données) ; (e) assurer la sécurité et le bon fonctionnement du service. »

4. **Base légale (RGPD art. 6)** —
   - Gestion du compte et fourniture du service (génération de quiz, historique) : **exécution du contrat** (art. 6-1-b) — l'acceptation des CGU à l'inscription.
   - Envoi du texte des cours à un fournisseur LLM pour générer les quiz : **exécution du contrat** (fonctionnalité coeur demandée par l'utilisateur).
   - Emails de sécurité et fonctionnement du service : **intérêt légitime** (art. 6-1-f).
   - Conservation de la preuve de consentement aux CGU/politique : **obligation de responsabilité** (accountability) et **consentement** recueilli à l'inscription (art. 6-1-a pour l'acceptation documentaire).

5. **Durée de conservation** —
   - Données de compte et de profil : **conservées tant que le compte existe**, puis **supprimées immédiatement et définitivement** lors de la suppression du compte (suppression en cascade des quiz et questions).
   - Quiz, questions, historique et scores : **même durée que le compte**, supprimés avec lui.
   - Preuve de consentement (date + version) : conservée pendant la durée de vie du compte.
   - Aucun export de données n'est stocké : les fichiers d'export sont générés à la demande et ne sont pas conservés côté serveur.
   - Le service n'a pas de politique d'inactivité automatique à ce stade : [à compléter : durée d'inactivité éventuelle avant suppression, si l'équipe en définit une].

6. **Destinataires des données** —
   - L'**équipe pédagogique** en charge d'EduTutor IA (administration technique).
   - L'**hébergeur** OVHcloud (sous-traitant technique, hébergement du serveur et de la base).
   - Le **fournisseur d'emails** Brevo (Sendinblue SAS) en production, pour l'acheminement des emails de service.
   - Le **fournisseur LLM** configuré pour générer les quiz : selon la configuration du serveur, il peut s'agir de Mistral AI (UE), ou de fournisseurs hors UE (voir rubrique 7). Le **texte de vos cours** (`source_text`) est transmis à ce fournisseur pour la seule finalité de génération des quiz.
   - Vos données ne sont **ni vendues, ni louées, ni cédées** à des fins publicitaires.

7. **Transferts hors UE** —
   - Selon le fournisseur LLM activé, le texte de vos cours peut être transmis à des prestataires situés **hors de l'Union européenne** : **OpenAI**, **Groq**, **Cerebras** (États-Unis), **Google Gemini** (Google, États-Unis), **Anthropic** (Claude, États-Unis) et **OpenRouter** (passerelle multi-modèles, routage possible hors UE).
   - Lorsqu'un fournisseur **européen** est utilisé (**Mistral AI**, hébergé dans l'UE) ou un modèle **local** (Ollama, exécuté sur notre propre serveur), **aucun transfert hors UE** n'a lieu.
   - Lorsqu'un transfert hors UE a lieu, il est encadré par les **clauses contractuelles types** de la Commission européenne et/ou les mécanismes de conformité propres à chaque fournisseur. [à compléter : préciser le fournisseur LLM effectivement retenu en production et le mécanisme de transfert applicable].
   - Vous pouvez nous demander quelle configuration LLM est active en nous contactant (voir rubrique 10).

8. **Vos droits** — « Conformément aux articles 15 à 21 du RGPD, vous disposez des droits suivants, exerçables ainsi :
   - **Droit d'accès et de rectification** : consultez et modifiez votre nom, prénom et email depuis la page « Mon profil ».
   - **Droit à la portabilité** (art. 20) : utilisez le bouton **« Exporter mes données »** de la page « Mon profil » ; vous recevez par email un lien de téléchargement (valable 1 heure) d'un fichier JSON contenant l'ensemble de vos données.
   - **Droit à l'effacement** (art. 17) : supprimez définitivement votre compte et toutes vos données depuis la **Zone de danger** de la page « Mon profil » (action irréversible).
   - **Droit d'opposition et de limitation** : contactez-nous (rubrique 10).
   Pour tout droit non exerçable directement dans l'application, contactez le référent données. »

9. **Cookies** — « Le service n'utilise que des cookies et stockages strictement techniques (session applicative, token d'authentification). Aucun traceur publicitaire ou de mesure d'audience n'est déposé. Pour le détail, consultez notre Politique de gestion des cookies. » (lien vers `/legal/cookies`).

10. **Contact & réclamation** — « Pour exercer vos droits ou pour toute question relative à vos données : [à compléter : email du référent données]. Si vous estimez, après nous avoir contactés, que vos droits ne sont pas respectés, vous pouvez introduire une réclamation auprès de la **CNIL** (Commission nationale de l'informatique et des libertés), 3 place de Fontenoy, TSA 80715, 75334 Paris Cedex 07, France — www.cnil.fr. »

La page passe `updatedAt="1er juillet 2026"`.

### 7.2. `MentionsLegalesPage.tsx` — Mentions légales

Conserver l'ordre des 5 rubriques existantes.

1. **Éditeur du site** — « Le site EduTutor IA (`https://apocalipssi26.elafrit.com`) est édité par l'Équipe 13 dans le cadre du projet pédagogique APOCAL'IPSSI 2026 à l'IPSSI. Statut : projet étudiant à but non lucratif et pédagogique. Adresse : [à compléter : adresse postale de l'éditeur]. Email : [à compléter : email de contact]. »

2. **Directeur de la publication** — « Le directeur de la publication est [à compléter : nom du responsable de la publication, ex. référent de l'Équipe 13]. »

3. **Hébergeur** — « Le site est hébergé sur un serveur privé virtuel (VPS) OVHcloud. Hébergeur : **OVH SAS**, 2 rue Kellermann, 59100 Roubaix, France. Téléphone : 1007. Site : www.ovhcloud.com. »

4. **Propriété intellectuelle** — « Le code source, la charte graphique, les textes et l'ensemble des éléments du site (hors contenus déposés par les utilisateurs) sont la propriété de l'Équipe 13 / du projet EduTutor IA, ou sont utilisés sous licence (voir le fichier LICENSE du dépôt). Les contenus que vous déposez (texte de vos cours) restent votre propriété ; vous nous accordez le droit de les traiter pour la seule fourniture du service. Toute reproduction non autorisée est interdite. »

5. **Contact** — « Pour toute question juridique ou relative au site : [à compléter : email de contact juridique]. »

La page passe `updatedAt="1er juillet 2026"`.

### 7.3. `CGUPage.tsx` — Conditions Générales d'Utilisation

Conserver l'ordre des 10 rubriques existantes.

1. **Objet** — « Les présentes CGU régissent l'utilisation du service EduTutor IA, une application pédagogique qui génère des quiz à choix multiples à partir du texte de cours fourni par l'utilisateur. »

2. **Acceptation des conditions** — « La création d'un compte vaut acceptation pleine et entière des présentes CGU et de la politique de confidentialité. L'utilisateur atteste avoir coché la case d'acceptation lors de son inscription ; la date et la version acceptées sont enregistrées. »

3. **Accès au service** — « Le service est accessible en ligne via un navigateur récent. Il est fourni « en l'état », dans un cadre pédagogique, sans garantie de disponibilité continue. Des interruptions peuvent survenir pour maintenance ou pour des raisons techniques. »

4. **Compte utilisateur** — « L'utilisateur s'engage à fournir une adresse email valide, à conserver son mot de passe confidentiel et à ne pas partager son compte. Il est responsable des actions réalisées depuis son compte. Toute perte de mot de passe peut être réinitialisée via la fonction « mot de passe oublié ». »

5. **Comportements interdits** — « Sont notamment interdits : le téléversement de contenus illicites, diffamatoires ou portant atteinte aux droits de tiers ; toute tentative d'atteinte à la sécurité ou à l'intégrité du service ; l'usage automatisé abusif ; le dépôt de données personnelles de tiers ou de données sensibles dans le texte des cours. »

6. **Contenu généré par IA** — « Les quiz sont générés automatiquement par un modèle d'intelligence artificielle. Ils **peuvent contenir des erreurs ou des imprécisions**. L'utilisateur reste responsable de la vérification des contenus générés avant tout usage pédagogique ou évaluatif. EduTutor IA ne garantit pas l'exactitude des quiz produits. »

7. **Responsabilité** — « L'éditeur ne saurait être tenu responsable des dommages indirects liés à l'utilisation du service, ni des conséquences d'une utilisation de contenus générés par l'IA sans vérification. Le service étant pédagogique, il est fourni sans garantie de résultat. »

8. **Propriété intellectuelle** — « Le service et ses composants appartiennent à l'Équipe 13 / EduTutor IA (voir Mentions légales). Les contenus déposés par l'utilisateur (texte des cours) restent sa propriété ; l'utilisateur garantit détenir les droits nécessaires sur les textes qu'il téléverse. »

9. **Modification des CGU** — « Les présentes CGU peuvent évoluer. En cas de modification substantielle, une nouvelle version (identifiée par sa date) sera publiée et pourra faire l'objet d'une nouvelle acceptation. La version en vigueur est celle affichée sur cette page. » (Note : la rubrique existante « Droit applicable et litiges » est fusionnée ici ou traitée ci-dessous selon l'ordre du tableau — voir remarque.)

> Remarque d'implémentation : le tableau `SECTIONS` existant de `CGUPage.tsx` comporte les rubriques dans l'ordre : Objet, Acceptation des conditions, Accès au service, Compte utilisateur, Comportements interdits, Contenu généré par IA, Responsabilité, Propriété intellectuelle, Modification des CGU, **Droit applicable et litiges**. Fournir un `content` pour **chacune** de ces rubriques (ne pas en retirer). Pour « Droit applicable et litiges » : « Les présentes CGU sont soumises au **droit français**. À défaut de résolution amiable, tout litige relève de la compétence des **tribunaux français**. »

La page passe `updatedAt="1er juillet 2026"`.

### 7.4. `CookiesPage.tsx` — Politique de gestion des cookies

Conserver l'ordre des 6 rubriques existantes et le bloc `children` existant (l'indice sur le `localStorage`).

1. **Qu'est-ce qu'un cookie ?** — « Un cookie est un petit fichier déposé par un site sur votre appareil. Plus largement, un site peut aussi utiliser d'autres formes de stockage local du navigateur (comme le localStorage) pour mémoriser des informations techniques nécessaires à son fonctionnement. »

2. **Cookies et stockage utilisés** — « EduTutor IA utilise uniquement des dispositifs **techniques** :
   - un **cookie de session** applicatif (`sessionid`), posé par le serveur lors de la connexion, utile notamment à l'interface d'administration/documentation ;
   - un **token d'authentification** stocké dans le **localStorage** de votre navigateur, qui vous maintient connecté entre deux visites.
   Aucun cookie tiers, publicitaire ou de mesure d'audience n'est déposé. »

3. **Finalité de chaque cookie** — « Le cookie de session et le token d'authentification servent exclusivement à vous **identifier et vous maintenir connecté** en toute sécurité. Ils sont **strictement nécessaires** au fonctionnement du service. »

4. **Consentement** — « Les cookies et stockages strictement nécessaires au fonctionnement d'un service sont **exemptés de consentement** (art. 82 loi Informatique et Libertés / lignes directrices CNIL). EduTutor IA n'utilisant **que** de tels dispositifs techniques, **aucune bannière de consentement n'est requise** et aucun traceur n'est activé sans votre action. »

5. **Durée de conservation** — « Le cookie de session expire à la fermeture de la session ou selon la configuration du serveur. Le token d'authentification reste dans le localStorage **jusqu'à votre déconnexion** (bouton « Se déconnecter »), un changement de mot de passe, ou la suppression manuelle du stockage de votre navigateur. »

6. **Gérer ou refuser les cookies** — « Vous pouvez à tout moment supprimer ces données via les réglages de votre navigateur (effacement des cookies et du stockage local) ou en vous déconnectant. Le refus ou la suppression du token d'authentification vous **déconnectera** simplement du service ; aucune autre fonctionnalité n'est affectée puisque aucun traceur non essentiel n'est utilisé. »

Le bloc `children` existant (indice pédagogique sur le `localStorage`) est **conservé** tel quel. La page passe `updatedAt="1er juillet 2026"`.

---

## 8. Emails (nouveau template export)

### 8.1. `backend/accounts/emails.py` — `send_export_email(user, download_url)`

Ajouter, dans la section « Emails métier », une fonction sur le modèle exact de `send_verification_email` / `send_password_reset_email` (même style, même gestion via `send_email` qui peut lever `EmailError`) :

```python
# backend/accounts/emails.py — section "Emails métier", après send_password_reset_email

def send_export_email(user, download_url: str) -> None:
    """Email contenant le lien de téléchargement de l'export RGPD (valable 1 h)."""
    body = (
        "Bonjour,\n\n"
        "Vous avez demandé une copie de vos données personnelles EduTutor IA "
        "(droit à la portabilité). Cliquez sur le lien ci-dessous pour "
        "télécharger votre fichier :\n\n"
        f"{download_url}\n\n"
        "Ce lien est valable 1 heure et n'est utilisable que par vous. "
        "Le fichier est au format JSON et contient votre compte, votre profil, "
        "vos quiz et l'historique de vos réponses.\n\n"
        "Si vous n'êtes pas à l'origine de cette demande, ignorez simplement cet "
        "email.\n\n"
        "— L'équipe EduTutor IA"
    )
    send_email(user.email, "Vos données EduTutor IA (export RGPD)", body)
```

Décisions :
- Le lien est **passé en argument** (`download_url`) et non reconstruit ici : c'est `RequestExportView` qui le construit via `request.build_absolute_uri` (backend, HTTPS-aware). On **ne** réutilise **pas** le helper `_frontend(...)` : le lien doit pointer sur le backend, pas le frontend.
- Email texte simple, cohérent avec les deux emails métier existants.
- En dev (backend email console), le lien s'affiche dans les logs — testable sans compte Brevo.

---

## 9. Tests (backend pytest + front vitest)

Conventions existantes : backend `pytest` avec `pytestmark = pytest.mark.django_db`, `APIClient`, fixtures `client` et `user` (voir `backend/accounts/tests.py`). Front `vitest` (`describe/it/expect`), setup dans `frontend/src/test/setup.ts`.

### 9.1. Backend — `backend/accounts/tests.py` (compléter le fichier existant)

**Export — cas nominaux**
- `test_request_export_authenticated_returns_generic_message` : POST `/api/accounts/export/request/` avec un utilisateur authentifié ⇒ 200, `detail` contient « lien » ; vérifier qu'un email a été « envoyé » (`django.core.mail.outbox` en backend `locmem`, ou capture du log).
- `test_request_export_requires_auth` : POST sans authentification ⇒ 401/403.
- `test_download_export_valid_token_returns_json_attachment` : générer un token via `make_export_token(user)`, GET `/api/accounts/export/download/?token=...` ⇒ 200, `Content-Type` = `application/json...`, header `Content-Disposition` commence par `attachment; filename="edututor-export-`.
- `test_export_payload_structure` : créer un `Quiz` + une `Question` pour l'utilisateur, télécharger, parser le JSON ⇒ vérifier les clés racines `compte`, `profil`, `quizzes` ; `compte.email` correct ; `profil.consentement.consent_version` présent ; `quizzes[0].questions[0].correct_index` correct.

**Export — cas limites**
- `test_download_export_missing_token` : GET sans `token` ⇒ 400.
- `test_download_export_invalid_token` : GET avec `token=nimportequoi` ⇒ 400, message générique.
- `test_download_export_expired_token` : monkeypatch/override de `EXPORT_MAX_AGE` à `-1` (ou usage de `signing.loads` mocké) pour simuler l'expiration ⇒ 400.
- `test_export_empty_user` : utilisateur sans quiz ⇒ `quizzes == []`, structure valide.

**Export — sécurité (isolation)**
- `test_download_export_isolation_between_users` : créer `alice` (avec un quiz) et `bob` ; générer le token de `bob` ; télécharger avec le token de `bob` ⇒ le JSON ne contient **que** les données de `bob` (aucun quiz d'`alice`), `compte.email == bob.email`.
- `test_export_token_salt_isolation` : un token de validation d'email (`make_email_verify_token(user)`) passé à `/export/download/` ⇒ 400 (salt distinct, rejeté par `read_export_token`).

**Consentement**
- `test_signup_requires_accept_terms_true` : POST signup **sans** `accept_terms` ⇒ 400 ; POST avec `accept_terms=false` ⇒ 400 avec message d'acceptation ; POST avec `accept_terms=true` ⇒ 201.
- `test_signup_records_consent` : après un signup avec `accept_terms=true`, le `Profile` de l'utilisateur a `consent_accepted_at` non nul et `consent_version == "2026-07-01"` (comparer à `CURRENT_CONSENT_VERSION`).

**Mise à jour d'un test existant (obligatoire, pas optionnelle)**
- `test_signup_creates_user` (existant, `backend/accounts/tests.py`, ~ligne 26) poste actuellement `{email, password}` **sans** `accept_terms` et attend `201`. Rendre `accept_terms` requis (BooleanField sans `default`) casse ce test : il renverra désormais `400`. Il faut donc **mettre à jour son payload** en y ajoutant `"accept_terms": True` pour qu'il reste vert. Cette modification est **requise** et fait partie du lot (elle n'est pas facultative).

### 9.2. Frontend — `vitest`

- `frontend/src/api/auth.test.ts` (nouveau) :
  - `requestDataExport` appelle `POST /accounts/export/request/` (api mocké) et renvoie `detail`.
  - `signup` inclut bien `accept_terms` dans le corps envoyé au backend.
- `frontend/src/pages/legal/LegalScaffold.test.tsx` (nouveau, avec `@testing-library/react`, déjà installé) :
  - une section avec `content` rend le contenu réel et **pas** « À compléter — ».
  - une section sans `content` rend « À compléter — {hint} ».
  - le bandeau amber « Page à compléter » n'apparaît **pas** quand toutes les sections ont un `content` (`hasDrafts === false`), et apparaît sinon.
- `frontend/src/pages/SignupPage.test.tsx` (nouveau) :
  - le bouton « Créer mon compte » est **désactivé** tant que la case n'est pas cochée, et **activé** une fois cochée.

> Note : `@testing-library/react` est déjà installé (voir `frontend/package.json` devDependencies et `frontend/src/test/setup.ts` qui importe `@testing-library/jest-dom/vitest`). Les tests de composants (LegalScaffold, SignupPage) sont donc **obligatoires** au même titre que les tests d'API (`auth.test.ts`) et les tests backend.

---

## 10. Liste des fichiers touchés/créés

| # | Fichier | Type | Nature du changement |
|---|---|---|---|
| B1 | `backend/accounts/models.py` | Modifié | Ajout `consent_accepted_at`, `consent_version`, constante `CURRENT_CONSENT_VERSION` |
| B2 | `backend/accounts/migrations/0002_profile_consent.py` | **Créé** | Migration additive (2 champs) |
| B3 | `backend/accounts/export.py` | **Créé** | `build_user_export(user) -> dict` |
| B4 | `backend/accounts/tokens.py` | Modifié | `EXPORT_SALT`, `EXPORT_MAX_AGE`, `make_export_token`, `read_export_token` |
| B5 | `backend/accounts/serializers.py` | Modifié | `SignupSerializer` : champ `accept_terms`, `validate_accept_terms`, `create` renseigne le consentement |
| B6 | `backend/accounts/views.py` | Modifié | `RequestExportView`, `DownloadExportView`, imports, nettoyage du `TODO J3-bis` |
| B7 | `backend/accounts/emails.py` | Modifié | `send_export_email(user, download_url)` |
| B8 | `backend/accounts/urls.py` | Modifié | Routes `export/request/` et `export/download/` |
| B9 | `backend/accounts/tests.py` | Modifié | Tests export (nominaux/limites/sécurité) + consentement ; **mise à jour requise** de `test_signup_creates_user` (ajout de `"accept_terms": True` à son payload, sinon il passe de 201 à 400) |
| F1 | `frontend/src/api/auth.ts` | Modifié | `requestDataExport()` ; `signup` accepte `accept_terms` |
| F2 | `frontend/src/pages/ProfilePage.tsx` | Modifié | Bouton export actif ; rappel + bouton export dans la Zone de danger ; nettoyage `TODO J3-bis` |
| F3 | `frontend/src/pages/SignupPage.tsx` | Modifié | Case à cocher obligatoire + blocage submit |
| F4 | `frontend/src/pages/legal/LegalScaffold.tsx` | Modifié | `LegalSection.content?`, prop `updatedAt?`, bandeau conditionnel |
| F5 | `frontend/src/pages/legal/ConfidentialitePage.tsx` | Modifié | Contenu réel des 10 rubriques |
| F6 | `frontend/src/pages/legal/MentionsLegalesPage.tsx` | Modifié | Contenu réel des 5 rubriques |
| F7 | `frontend/src/pages/legal/CGUPage.tsx` | Modifié | Contenu réel des rubriques |
| F8 | `frontend/src/pages/legal/CookiesPage.tsx` | Modifié | Contenu réel des 6 rubriques (bloc `children` conservé) |
| F9 | `frontend/src/api/auth.test.ts` | **Créé** | Tests `requestDataExport` + `signup` |
| F10 | `frontend/src/pages/legal/LegalScaffold.test.tsx` | **Créé** | Rendu content vs placeholder, bandeau |
| F11 | `frontend/src/pages/SignupPage.test.tsx` | **Créé** | Blocage submit tant que case décochée |

**Backend impactés : 9 fichiers** (dont 2 créés : `0002_profile_consent.py`, `export.py`).
**Frontend impactés : 11 fichiers** (dont 3 créés : `auth.test.ts`, `LegalScaffold.test.tsx`, `SignupPage.test.tsx`).

---

## 11. Points à compléter par l'équipe

Zones balisées `[à compléter : ...]` — informations que seule l'équipe détient. **Tout le reste est rédigé et implémentable en l'état.**

1. **Email du référent données** (Confidentialité §1 et §10, Mentions légales §5) — adresse de contact RGPD de l'équipe.
2. **Adresse postale de l'éditeur** (Confidentialité §1, Mentions légales §1) — adresse à publier.
3. **Nom du directeur de la publication** (Mentions légales §2).
4. **Fournisseur LLM effectivement retenu en production** et **mécanisme de transfert hors UE applicable** (Confidentialité §7) — à préciser selon la valeur de `LLM_BACKEND` en prod.
5. **Durée d'inactivité éventuelle avant suppression automatique** (Confidentialité §5), si l'équipe décide d'en instaurer une (sinon, indiquer « pas de suppression automatique pour inactivité »).

Aucun autre placeholder `TBD`/`TODO` ne subsiste dans cette spec.

---

## 12. Critères d'acceptation

**Modèle & migration**
- [ ] `Profile` possède `consent_accepted_at` (nullable) et `consent_version` (`CharField`, défaut vide) ; `CURRENT_CONSENT_VERSION == "2026-07-01"`.
- [ ] `python manage.py makemigrations --check` ne détecte aucune migration manquante après `0002_profile_consent`.
- [ ] `python manage.py migrate` s'applique sans erreur ; les comptes existants ont `consent_accepted_at = NULL`.

**Export RGPD**
- [ ] POST `/api/accounts/export/request/` authentifié ⇒ 200 + message générique ; non authentifié ⇒ 401/403.
- [ ] Un email d'export est déclenché (visible dans les logs en dev / `outbox` en test) et contient un lien absolu vers `/api/accounts/export/download/?token=...`.
- [ ] GET `/api/accounts/export/download/` avec token valide ⇒ 200, `Content-Type: application/json`, `Content-Disposition: attachment; filename="edututor-export-<id>.json"`.
- [ ] Le JSON respecte exactement la structure §4.4 (`compte`, `profil` avec `consentement`, `quizzes` avec `questions`).
- [ ] Token absent/invalide/expiré ⇒ 400 avec message générique ; token d'un autre salt (validation email) ⇒ 400.
- [ ] Le JSON ne contient que les données de l'utilisateur encodé dans le token (isolation vérifiée par test).

**Consentement**
- [ ] Signup sans `accept_terms` ou avec `accept_terms=false` ⇒ 400 ; avec `accept_terms=true` ⇒ 201 et `Profile.consent_accepted_at` renseigné + `consent_version == "2026-07-01"`.
- [ ] Le test existant `test_signup_creates_user` a été mis à jour (ajout de `"accept_terms": True` à son payload) et repasse au vert (201).
- [ ] Sur `SignupPage`, le bouton de soumission est désactivé tant que la case n'est pas cochée ; les liens `/legal/cgu` et `/legal/confidentialite` sont présents.

**Frontend export**
- [ ] Sur `ProfilePage`, le bouton « Exporter mes données » est actif et appelle `requestDataExport()` ; un message de confirmation s'affiche.
- [ ] La Zone de danger contient un rappel + un bouton « Exporter mes données d'abord » **non bloquant** (la suppression reste possible sans exporter).
- [ ] Plus aucun `TODO J3-bis RGPD` dans `ProfilePage.tsx` ni `views.py`.

**Pages légales**
- [ ] Les 4 pages affichent le **contenu réel** rédigé (plus de « À compléter — {hint} » sur les rubriques pourvues d'un `content`), avec `updatedAt="1er juillet 2026"`.
- [ ] Le bandeau amber « Page à compléter » ne s'affiche plus sur les pages dont toutes les sections ont un `content`.
- [ ] `LegalScaffold` reste rétrocompatible : une section sans `content` affiche toujours « À compléter — {hint} ».
- [ ] Confidentialité couvre : responsable, données collectées, finalités, base légale art.6, durées de conservation, destinataires (dont LLM), transferts hors UE (OpenAI/Groq/Cerebras/Gemini/Anthropic/OpenRouter), droits avec le « comment » (export, suppression), cookies (renvoi), contact + CNIL.

**Qualité / tests**
- [ ] `pytest backend/accounts/` passe (tests export nominaux, limites, sécurité, consentement).
- [ ] Les tests front `auth.test.ts` passent.
- [ ] `ruff` / `black` OK côté backend ; lint front OK.
- [ ] Seuls les `[à compléter : ...]` de §11 subsistent comme éléments non finalisés.
