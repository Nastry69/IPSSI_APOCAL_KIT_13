# ADR-0002 : Stratégie de sécurité de l'application

## Statut

Proposed

## Contexte et problème

L'application EduTutor IA est une plateforme web (Django + React) qui génère des QCM
via des LLMs à partir de cours uploadés par les utilisateurs. Elle gère des comptes
utilisateurs, des tokens d'authentification, des clés API vers des services tiers, et
des fichiers PDF potentiellement sensibles.

Un audit complet du code source a été réalisé le 01/07/2026. Il a identifié **4 problèmes
sérieux**, **14 points à améliorer** et **14 points conformes** aux bonnes pratiques.

Ce document recense l'état actuel, les risques associés, et les actions correctives
recommandées classées par priorité.

---

## Ce qui est déjà sécurisé ✅

| Point | Détail | Fichier |
|---|---|---|
| Authentification par token DRF | Mécanisme clair, logout supprime le token | `settings.py` l.164 |
| `IsAuthenticated` par défaut | Tous les endpoints sont protégés sauf exceptions explicites | `settings.py` l.169 |
| Endpoints admin protégés par `IsAdminUser` | Aucun accès admin sans droit staff | `administration/views.py` l.70+ |
| Isolation des données par utilisateur | Les quiz sont filtrés par `user=request.user` | `quizzes/views.py` l.31 |
| Pas d'injection SQL | ORM Django utilisé partout, pas de SQL brut | Toutes les vues |
| XSS front-end neutralisé | React échappe automatiquement les valeurs, aucun `dangerouslySetInnerHTML` | Composants React |
| Validation complète des serializers | `is_valid(raise_exception=True)` systématique | `accounts/serializers.py` |
| Taille PDF limitée à 5 Mo | Vérification effective avant extraction | `pdf_utils.py` l.12 |
| PDF non stocké sur disque | Traitement en mémoire uniquement | `pdf_utils.py` |
| PDF protégé par mot de passe rejeté | `reader.is_encrypted` vérifié | `pdf_utils.py` l.43 |
| Prompt LLM : system séparé du contenu user | Rôles `system` / `user` distincts dans l'API | `quiz_prompt.py` l.26 |
| Validation stricte de la sortie LLM | JSON rejeté si structure invalide | `quiz_prompt.py` l.91 |
| CORS restreint à localhost | Pas de wildcard, origines explicites | `settings.py` l.199 |
| Anti-énumération sur password-reset | Réponse identique compte existant ou non | `accounts/views.py` l.192 |
| `.env` dans `.gitignore` | Les secrets locaux ne sont pas versionnés | `.gitignore` l.18 |
| `set_password` utilisé correctement | Hashage Django appliqué partout | `accounts/views.py` l.297 |
| Vérification email implémentée | Token signé, validité 3 jours | `tokens.py` l.21 |
| Rotation du token au changement de mot de passe | Ancien token invalidé | `accounts/views.py` l.303 |

---

## Problèmes sérieux ❌

### P1 — Clé SMTP réelle dans `.env.example`

**Fichier :** `.env.example` ligne 90
**Risque :** La clé SMTP Brevo est une vraie clé active versionnée dans Git. Même
"jetable", toute clé dans un fichier versionné peut être indexée par GitHub, des bots
de scan ou des membres de l'équipe qui la réutilisent hors contexte.

```
BREVO_SMTP_KEY=xsmtpsib-1c81465a9155a2d7b3276d90aa043e7f988753a8bbbcdf8d9fabe7d89456c57d-...
```

**Solution :**
```bash
# Dans .env.example : remplacer par un placeholder
BREVO_SMTP_KEY=your-brevo-smtp-key-here
```
Révoquer immédiatement la clé exposée dans la console Brevo.

---

### P2 — Aucun rate limiting (brute force illimité)

**Fichier :** Absent dans tout le backend
**Risque :** N'importe qui peut tenter un nombre illimité de mots de passe sur
`/api/accounts/login/`, créer des milliers de comptes via `/api/accounts/signup/`,
ou spammer des emails de reset via `/api/accounts/password-reset/`. La génération LLM
(`/api/llm/generate-quiz/`) peut aussi être appelée en boucle pour consommer les quotas.

**Solution — ajouter les throttles DRF (sans dépendance externe) :**
```python
# settings.py
REST_FRAMEWORK = {
    ...
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "20/hour",
        "user": "100/hour",
    },
}
```
```python
# accounts/views.py — sur LoginView
from rest_framework.throttling import AnonRateThrottle

class LoginView(APIView):
    throttle_classes = [AnonRateThrottle]
    throttle_scope = "login"  # "5/min" dans DEFAULT_THROTTLE_RATES
```

---

### P3 — Clés API LLM stockées en clair en base de données

**Fichier :** `llm/models.py` ligne 39
**Risque :** La colonne `api_keys` (JSONField) contient les clés Groq, Mistral,
Gemini, etc. en texte clair. Un accès à la base de données (dump SQL, backup non
chiffré, vulnérabilité future) expose immédiatement toutes les clés.

```python
# llm/models.py — commentaire dans le code lui-même :
# ⚠️ Sécurité : les clés API sont stockées EN CLAIR dans `api_keys`.
```

**Solution simple (court terme) :**
```bash
pip install django-fernet-fields
```
```python
# llm/models.py
from fernet_fields import EncryptedJSONField
api_keys = EncryptedJSONField(default=dict, blank=True)
```
La clé de chiffrement est lue depuis `settings.FERNET_KEYS` (variable d'environnement).

---

### P4 — Aucune Content Security Policy (CSP)

**Fichier :** Absent dans `settings.py` et dans la config Vite/Caddy
**Risque :** Sans CSP, le navigateur n'a aucune restriction sur les sources de scripts.
Si une XSS est découverte (même mineure), un attaquant peut charger du code depuis
n'importe quelle URL externe. La CSP est la dernière ligne de défense anti-XSS.

**Solution :**
```bash
pip install django-csp
```
```python
# settings.py
INSTALLED_APPS += ["csp"]
MIDDLEWARE += ["csp.middleware.CSPMiddleware"]

CONTENT_SECURITY_POLICY = {
    "DIRECTIVES": {
        "default-src": ["'self'"],
        "script-src": ["'self'"],
        "style-src": ["'self'", "'unsafe-inline'"],  # ajuster selon les besoins UI
        "img-src": ["'self'", "data:"],
        "connect-src": ["'self'"],
        "frame-ancestors": ["'none'"],
    }
}
```

---

## Points à améliorer ⚠️

### A1 — Token d'authentification sans expiration, stocké en localStorage

**Fichier :** `frontend/src/api/client.ts` l.15 / `settings.py` l.164
**Risque :** Le token DRF est permanent (pas de TTL) et stocké en `localStorage`,
accessible par tout script JavaScript. Un token volé via XSS reste valide indéfiniment.

**Solution recommandée — migrer vers `django-knox` :**
```bash
pip install django-knox
```
Knox génère des tokens avec expiration configurable, stockés hashés en base,
et supporte plusieurs tokens par utilisateur (multi-device).
```python
# settings.py
REST_KNOX = {
    "TOKEN_TTL": timedelta(hours=10),
    "AUTO_REFRESH": True,
}
```
Côté front : stocker le token dans un cookie `HttpOnly; Secure; SameSite=Strict`
plutôt que `localStorage` (nécessite un endpoint backend qui pose le cookie).

---

### A2 — Validation MIME des PDF par extension uniquement

**Fichier :** `llm/serializers.py` ligne 33
**Risque :** Un fichier malveillant renommé `.pdf` passe la validation.

```python
# Actuel — insuffisant
if pdf and not pdf.name.lower().endswith(".pdf"):
    raise serializers.ValidationError(...)
```

**Solution — vérifier le magic number :**
```python
# llm/serializers.py
def validate(self, data):
    pdf = data.get("pdf")
    if pdf:
        pdf.seek(0)
        header = pdf.read(4)
        pdf.seek(0)
        if header != b"%PDF":
            raise serializers.ValidationError({"pdf": "Fichier PDF invalide."})
    ...
```

---

### A3 — Swagger / OpenAPI public en production

**Fichier :** `backend/apocal/urls.py` lignes 33-35
**Risque :** L'API est entièrement documentée et accessible sans authentification.
C'est un plan détaillé offert à un attaquant.

**Solution :**
```python
# urls.py — restreindre en production
from django.conf import settings
from rest_framework.permissions import IsAdminUser

if not settings.SECURE_PROD:
    urlpatterns += [path("api/docs/", SpectacularSwaggerView...)]
else:
    # Swagger accessible uniquement aux admins connectés
    urlpatterns += [path("api/docs/", permission_classes=[IsAdminUser](...)]
```

---

### A4 — SECRET_KEY Django avec valeur par défaut faible

**Fichier :** `settings.py` ligne 20
**Risque :** Si le `.env` n'est pas créé, Django démarre avec une clé connue de tous.
Les tokens de vérification email et sessions seraient forgables.

**Solution :**
```python
# settings.py
SECRET_KEY = config("DJANGO_SECRET_KEY")  # Supprimer le default=
# Django refusera de démarrer sans la variable — comportement voulu.
```
Ou lever une exception explicite si la valeur par défaut est détectée en prod.

---

### A5 — Hashage PBKDF2 (Argon2 recommandé)

**Fichier :** `settings.py` (défaut Django)
**Risque :** PBKDF2 est acceptable mais Argon2 est le standard actuel (vainqueur
Password Hashing Competition 2015), résistant aux attaques GPU et aux ASICs.

**Solution :**
```bash
pip install django[argon2]
```
```python
# settings.py
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",  # nouveau défaut
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",  # fallback existants
]
```
Les mots de passe existants sont automatiquement re-hashés à la prochaine connexion.

---

### A6 — Vérification email non obligatoire par défaut

**Fichier :** `administration/models.py` ligne 28
**Risque :** Un utilisateur peut créer un compte avec n'importe quelle adresse email
et accéder immédiatement à toutes les fonctionnalités.

**Solution :** Activer `require_email_verification = True` dans `SiteConfig` en
production via l'interface admin. Le mécanisme est déjà codé dans `llm/views.py` l.115.

---

### A7 — Interface admin Django sur URL standard `/admin/`

**Fichier :** `apocal/urls.py` ligne 24
**Risque :** L'URL `/admin/` est la première URL testée par les scanners automatiques.

**Solution :**
```python
# urls.py
path("gestion-interne-2026/", admin.site.urls),  # URL non prévisible
```

---

### A8 — `/api/llm/ping/` public et informatif

**Fichier :** `llm/views.py` ligne 27
**Risque :** Expose le backend LLM actif, le modèle et l'état d'Ollama sans
authentification.

**Solution :** Passer à `IsAuthenticated` ou `IsAdminUser` selon l'usage.

---

### A9 — Headers de sécurité désactivés hors production

**Fichier :** `settings.py` lignes 311-324
**Risque :** `X-Frame-Options`, `SECURE_CONTENT_TYPE_NOSNIFF`, cookies sécurisés
ne sont actifs qu'avec `DJANGO_SECURE_PROD=True`.

**Solution :** Activer `SECURE_CONTENT_TYPE_NOSNIFF = True` et
`X_FRAME_OPTIONS = "DENY"` inconditionnellement (ils ne cassent rien en dev).

---

### A10 — Pas de sanitisation du titre avant injection dans le prompt LLM

**Fichier :** `llm/services/quiz_prompt.py` ligne 77
**Risque :** Un titre comme `"; IGNORE LES INSTRUCTIONS PRÉCÉDENTES..."` est envoyé
tel quel au LLM (prompt injection).

**Solution :**
```python
def build_user_prompt(source_text: str, title: str) -> str:
    safe_title = title[:100].replace("\n", " ").replace("\r", " ")
    truncated = source_text[:MAX_SOURCE_CHARS]
    return f"TITRE DU COURS : {safe_title}\n\nCOURS :\n{truncated}\n\nGÉNÈRE LE JSON MAINTENANT :"
```

---

## Tableau de synthèse

| # | Point | Statut | Effort | Impact |
|---|---|---|---|---|
| P1 | Clé SMTP réelle dans `.env.example` | ❌ | 5 min | Critique |
| P2 | Aucun rate limiting (brute force) | ❌ | 1h | Critique |
| P3 | Clés API LLM en clair en base | ❌ | 2h | Élevé |
| P4 | Aucune Content Security Policy | ❌ | 1h | Élevé |
| A1 | Token sans expiration + localStorage | ⚠️ | 4h | Élevé |
| A2 | MIME PDF validé par extension seulement | ⚠️ | 30 min | Moyen |
| A3 | Swagger public en production | ⚠️ | 30 min | Moyen |
| A4 | SECRET_KEY avec valeur par défaut | ⚠️ | 10 min | Élevé |
| A5 | Hashage PBKDF2 au lieu d'Argon2 | ⚠️ | 30 min | Faible |
| A6 | Vérification email non obligatoire | ⚠️ | 5 min (config) | Moyen |
| A7 | Admin Django sur URL standard `/admin/` | ⚠️ | 5 min | Faible |
| A8 | `/api/llm/ping/` public | ⚠️ | 5 min | Faible |
| A9 | Headers sécurité désactivés hors prod | ⚠️ | 15 min | Moyen |
| A10 | Pas de sanitisation titre prompt LLM | ⚠️ | 15 min | Moyen |

---

## Décision

Les correctifs sont classés en deux lots :

**Lot 1 — Urgences (à faire avant toute mise en production) :**
Traiter P1, P2, P3, P4, A4 dans cet ordre. Ces cinq points représentent ~5h de travail
et couvrent les risques les plus sérieux (secrets exposés, brute force, chiffrement,
injection de scripts).

**Lot 2 — Améliorations (sprint dédié sécurité) :**
Traiter A1 à A10. Priorité à A1 (token) et A2 (MIME) car ils complètent la défense
en profondeur.

## Conséquences

### Positives

* Résistance aux attaques les plus communes (brute force, vol de token, XSS, secret leaks)
* Conformité RGPD renforcée (chiffrement des clés API en base)
* Réduction de la surface d'attaque (admin obscurci, Swagger restreint, ping protégé)

### Négatives

* Lot 1 nécessite des migrations Django (chiffrement `api_keys`, Argon2)
* La migration vers `knox` (A1) implique une déconnexion forcée de tous les utilisateurs
* L'activation de la CSP (P4) peut casser des styles inline si présents

### Neutres

* L'architecture actuelle (ORM, serializers, séparation prompt/contenu) est saine
  et ne nécessite pas de refonte — ce sont des ajouts de couches de protection
* Revue de sécurité recommandée à chaque ajout de provider LLM ou d'endpoint public

---

## Liens

* [OWASP Top 10](https://owasp.org/www-project-top-ten/)
* [Django Security docs](https://docs.djangoproject.com/en/5.0/topics/security/)
* Architecture app : [01-architecture.md](./01-architecture.md)
* Intégration LLM : [02-llm-integration.md](./02-llm-integration.md)
* Tests : [04-testing.md](./04-testing.md)
