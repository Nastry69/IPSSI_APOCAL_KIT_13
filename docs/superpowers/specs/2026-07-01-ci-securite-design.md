# Spec — Volet Sécurité de la CI (EduTutor IA)

- **Fichier** : `docs/superpowers/specs/2026-07-01-ci-securite-design.md`
- **Date** : 2026-07-01
- **Auteur** : Équipe DevOps
- **Statut** : Prêt à implémenter
- **Niveau retenu** : ESSENTIEL (non bloquant au démarrage)
- **Portée** : Ajout d'un workflow GitHub Actions dédié à la sécurité, sans modifier le workflow CI existant.

---

## 1. Contexte & objectif

Le projet **EduTutor IA** (dépôt `IPSSI_APOCAL_KIT_13`) dispose déjà d'une CI fonctionnelle (`.github/workflows/ci.yml`) qui garantit la qualité (lint, format, tests) du backend Django et du frontend React/Vite. En revanche, **aucun contrôle de sécurité automatisé** n'existe : ni analyse des vulnérabilités connues (CVE) des dépendances, ni analyse statique du code (SAST), ni détection de secrets accidentellement committés.

**Objectif** : introduire un volet sécurité **automatisé, reproductible et progressif** dans la CI, au niveau **ESSENTIEL**. Ce niveau couvre les quatre risques les plus courants d'un projet web conteneurisé :

1. **Dépendances vulnérables** côté Python et côté Node (chaîne d'approvisionnement / supply chain).
2. **Failles de code** détectables statiquement côté Python (injection, secrets en dur, usages dangereux).
3. **Fuite de secrets** (clés d'API, mots de passe, tokens) dans l'historique et les fichiers du dépôt.

**Décisions structurantes** :

- Un **workflow dédié** `.github/workflows/security.yml`, distinct de `ci.yml`, pour ne pas alourdir la CI existante et pour pouvoir faire évoluer la sécurité indépendamment.
- **Le scan des images Docker est explicitement hors périmètre** à ce niveau (niveau essentiel choisi). Les images ne sont pas scannées (pas de Trivy/Grype). Ce point est identifié comme évolution possible vers un niveau supérieur.
- **Démarrage NON BLOQUANT** : chaque étape de scan porte `continue-on-error: true`. Le but est de rendre les rapports visibles sans casser les Pull Requests le jour de la mise en place. Le passage en mode **BLOQUANT** est documenté et trivial (voir §6).
- **Reproductibilité locale** : les outils Python (`pip-audit`, `bandit`) sont ajoutés à `backend/requirements-dev.txt` avec versions épinglées, afin qu'un développeur puisse lancer exactement les mêmes contrôles en local.

**Non-objectifs** :

- Ne remplace pas une revue de sécurité humaine ni un pentest.
- Ne scanne pas les images Docker (niveau essentiel).
- Ne modifie pas `ci.yml`.

---

## 2. État actuel de la CI

Fichier : `.github/workflows/ci.yml`.

- **Déclencheurs** : `push` sur `main` et `pull_request` vers `main`.
- **Permissions** : `contents: read` (minimales).
- **Job `backend`** (« Backend (Python / Django) ») :
  - `runs-on: ubuntu-latest`.
  - Service `postgres:16-alpine` (base `apocal`, healthcheck `pg_isready`).
  - `defaults.run.working-directory: ./backend`.
  - Variables d'environnement CI (`DJANGO_DEBUG=False`, `DJANGO_SECRET_KEY=ci-only-not-secret`, `LLM_BACKEND=mock`, connexion Postgres…).
  - Étapes : `actions/checkout@v5` → `actions/setup-python@v6` (Python 3.11, `cache: pip`, `cache-dependency-path: backend/requirements-dev.txt`) → `pip install -r requirements-dev.txt` → `ruff check .` → `black --check .` → `python manage.py check` → `python manage.py migrate --noinput` → `pytest --cov --cov-report=term-missing`.
- **Job `frontend`** (« Frontend (React / Vite) ») :
  - `runs-on: ubuntu-latest`.
  - `defaults.run.working-directory: ./frontend`.
  - Étapes : `actions/checkout@v5` → `actions/setup-node@v5` (Node 20, `cache: npm`, `cache-dependency-path: frontend/package-lock.json`) → `npm ci || npm install --no-audit --no-fund` (install avec fallback : `npm ci` strict d'abord, repli sur `npm install` si le lockfile est désynchronisé) → `npm run lint` → `npm run format:check` → `npm run build` → `npm test -- --run`.

> **Divergence assumée dans `security.yml`** : le job `deps-frontend` du nouveau workflow utilise un `npm ci` **strict** (sans fallback), car un audit de dépendances n'a de sens que sur une installation parfaitement déterministe issue du lockfile. Ce n'est donc **pas** une reprise à l'identique de l'étape d'install de `ci.yml` (qui, elle, tolère un repli sur `npm install`), mais un choix délibéré propre au contexte sécurité.

**Conventions à respecter dans le nouveau workflow** (pour cohérence) :

- Versions d'actions identiques : `actions/checkout@v5`, `actions/setup-python@v6`, `actions/setup-node@v5`.
- Python `3.11`, Node `20`.
- Caches pip/npm avec les mêmes `cache-dependency-path`.
- `permissions` minimales déclarées explicitement.
- Commentaires d'en-tête en français, mêmes conventions de nommage de jobs.

**Éléments du dépôt à connaître** :

- `backend/requirements.txt` : dépendances runtime.
- `backend/requirements-dev.txt` : `-r requirements.txt` + outils (pytest, black, ruff, factory-boy, faker).
- `backend/pyproject.toml` : configuration centralisée (`[tool.black]`, `[tool.ruff]`, `[tool.pytest.ini_options]`, `[tool.coverage]`). C'est le fichier naturel pour ajouter la config `bandit`.
- Applications Django : `accounts/`, `administration/`, `apocal/` (projet), `llm/`, `quizzes/`.
- Fichiers de tests : `accounts/tests.py`, `administration/tests.py`, `llm/tests.py`, `quizzes/tests.py`, plus `llm/tests_fixtures/`.
- `frontend/package-lock.json` présent (permet `npm audit` déterministe).
- `.env` **non suivi** par git ; `.env.example` et `.env.prod.example` **suivis**.
  - `.env.prod.example` ne contient que des **placeholders** (`<COLLER_...>`) : c'est un faux positif attendu, légitimement couvert par l'allowlist gitleaks par chemin.
  - `.env.example` contient en revanche une **VRAIE clé SMTP Brevo en clair** (`BREVO_SMTP_KEY=...`) et son login, documentée par le dépôt lui-même comme **compromise / déjà fuitée**, à révoquer et purger (`docs/11-deploiement-vps-ovh.md:497`). Ce n'est **pas** une valeur factice. Le mettre en allowlist masquerait le seul vrai secret fuité du repo — ce qui va à l'encontre du livrable central. Il **ne doit donc pas** figurer dans l'allowlist par chemin tant qu'une remédiation préalable (révocation + remplacement par un placeholder) n'a pas été effectuée (voir §5.1, « Remédiation préalable obligatoire »).

---

## 3. Outils retenus

| Outil | Cible | Rôle | Déclencheurs | Bloquant (démarrage) |
|-------|-------|------|--------------|----------------------|
| **pip-audit** | `backend/requirements.txt` et `backend/requirements-dev.txt` | Détection des CVE des dépendances Python (base PyPI Advisory / OSV) | push, PR, cron hebdo | Non (`continue-on-error: true`) |
| **bandit** | Code Python sous `backend/` (exclusion des tests et migrations) | SAST : usages dangereux, secrets en dur, injections potentielles | push, PR, cron hebdo | Non (`continue-on-error: true`) |
| **npm audit** | `frontend/` (via `package-lock.json`) | Détection des CVE des dépendances Node, seuil `--audit-level=high` | push, PR, cron hebdo | Non (`continue-on-error: true`) |
| **gitleaks** | Tout le dépôt (fichiers + historique) | Détection de secrets (clés, tokens, mots de passe) | push, PR, cron hebdo | Non (`continue-on-error: true`) |

**Justification des choix (niveau essentiel)** :

- **pip-audit** : léger, sans daemon, s'appuie sur la base OSV/PyPI ; on scanne **les deux** fichiers de requirements car les outils de dev sont aussi exécutés en CI (surface d'attaque réelle).
- **bandit** : SAST Python standard, rapide, faible bruit **une fois les fichiers de tests réellement exclus**. Attention : les tests ne génèrent pas que du B101 (`assert_used`) ; sur le code réel du projet, bandit remonte aussi des **B105/B106** (`hardcoded_password_string` / `hardcoded_password_funcarg`, ex. `password='motdepasse123'` dans `accounts/tests.py`) que le seul skip de B101 **ne supprime pas**. Il faut donc soit exclure les fichiers de tests via `--exclude`, soit skipper B105 et B106 en plus de B101 (voir §5.3).
- **npm audit** : natif à npm, aucun outil tiers à installer ; seuil `high` pour se concentrer sur les vulnérabilités sérieuses et limiter le bruit des `low/moderate`.
- **gitleaks** : détecteur de secrets de référence, configurable via `.gitleaks.toml` (allowlist des fichiers d'exemple).

**Hors périmètre volontaire** : scan d'images Docker (Trivy/Grype), analyse SAST JavaScript avancée (au-delà d'ESLint déjà présent), DAST. À réévaluer pour un niveau « renforcé ».

---

## 4. Le workflow `security.yml`

Le workflow comporte **quatre jobs indépendants** exécutés en parallèle, tous `runs-on: ubuntu-latest` :

1. **`deps-python`** — pip-audit sur les deux fichiers de requirements.
2. **`sast-python`** — bandit sur le code backend.
3. **`deps-frontend`** — npm audit sur le frontend.
4. **`secrets`** — gitleaks sur l'ensemble du dépôt.

### 4.1 Déclencheurs

- `push` sur `main` et `pull_request` vers `main` (cohérent avec `ci.yml`).
- `schedule` : cron hebdomadaire **le lundi à 06:00 UTC** (`0 6 * * 1`) pour capter les CVE nouvellement publiées sur du code inchangé.
- `workflow_dispatch` : déclenchement manuel depuis l'onglet Actions (utile pour tester ou relancer un scan à la demande).

### 4.2 Permissions

Permissions minimales au niveau workflow : `contents: read`.

> Note gitleaks/PR : `contents: read` suffit pour cloner et scanner. Le job `secrets` a besoin de l'historique complet (`fetch-depth: 0`) pour scanner les commits, pas de permissions d'écriture. Aucune écriture de commentaire de PR n'est configurée à ce niveau (évite d'avoir à élever `pull-requests: write`).

### 4.3 Détail par job / step

**Job `deps-python`** :

- `actions/checkout@v5`.
- `actions/setup-python@v6` (Python 3.11, cache pip, `cache-dependency-path: backend/requirements-dev.txt`) — identique à `ci.yml`.
- Installation de pip-audit via `requirements-dev.txt` (où il est épinglé) : `pip install -r requirements-dev.txt`. Cela garantit **la même version en local et en CI**.
- Deux étapes pip-audit (chacune `continue-on-error: true`) :
  - `pip-audit -r requirements.txt --desc` (dépendances runtime).
  - `pip-audit -r requirements-dev.txt --desc` (dépendances de dev/CI).
- `working-directory: ./backend`.

**Job `sast-python`** :

- `actions/checkout@v5`.
- `actions/setup-python@v6` (mêmes paramètres).
- `pip install -r requirements-dev.txt` (bandit y est épinglé).
- Étape bandit (`continue-on-error: true`) : `bandit -c pyproject.toml -r . -q --exclude ./accounts/tests.py,./administration/tests.py,./llm/tests.py,./quizzes/tests.py`. La configuration (`[tool.bandit]` dans `backend/pyproject.toml`) exclut migrations, `venv/`, `.venv/`, `tests_fixtures/` ; l'option `--exclude` écarte en plus les fichiers de tests `tests.py` par application (que `exclude_dirs` ne peut pas cibler car ce sont des fichiers, pas des répertoires), afin de neutraliser à la fois B101 (assert) et B105/B106 (mots de passe de test en dur). `-r .` avec `working-directory: ./backend`.

**Job `deps-frontend`** :

- `actions/checkout@v5`.
- `actions/setup-node@v5` (Node 20, cache npm, `cache-dependency-path: frontend/package-lock.json`) — identique à `ci.yml`.
- `npm ci` **strict**, sans fallback (déterministe grâce au lockfile). **Divergence assumée** vis-à-vis de `ci.yml`, dont l'étape d'install est `npm ci || npm install --no-audit --no-fund` : ici on veut une install strictement reproductible depuis le lockfile, condition d'un audit fiable — on ne reprend donc pas le fallback.
- Étape `npm audit --audit-level=high` (`continue-on-error: true`).
- `working-directory: ./frontend`.

**Job `secrets`** :

- `actions/checkout@v5` avec `fetch-depth: 0` (historique complet requis par gitleaks).
- Action officielle **`gitleaks/gitleaks-action@v2`** (`continue-on-error: true`), configurée pour utiliser `.gitleaks.toml` à la racine.
- Variable `GITLEAKS_CONFIG: ${{ github.workspace }}/.gitleaks.toml` pour forcer la prise en compte de l'allowlist.

### 4.4 YAML complet

Chemin cible : `.github/workflows/security.yml`

```yaml
# ============================================================================
# EduTutor IA (IPSSI_APOCAL_KIT_13) — Pipeline SÉCURITÉ GitHub Actions
# ----------------------------------------------------------------------------
# Niveau : ESSENTIEL. Complète ci.yml sans le remplacer.
#
# Déclenchement :
#   - push sur main
#   - pull request vers main
#   - cron hebdomadaire (lundi 06:00 UTC) : capte les nouvelles CVE
#   - déclenchement manuel (workflow_dispatch)
#
# 4 jobs en parallèle :
#   - deps-python   : pip-audit (CVE des dépendances Python)
#   - sast-python   : bandit (analyse statique du code Python)
#   - deps-frontend : npm audit (CVE des dépendances Node)
#   - secrets       : gitleaks (détection de secrets sur tout le dépôt)
#
# DÉMARRAGE NON BLOQUANT : chaque step de scan porte `continue-on-error: true`.
# Pour rendre un contrôle BLOQUANT : retirer la ligne `continue-on-error: true`
# du step concerné (voir la spec, section « Stratégie non-bloquant vers bloquant »).
# ============================================================================

name: Security

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
  schedule:
    # Tous les lundis à 06:00 UTC (minutes heure jour-du-mois mois jour-semaine)
    - cron: '0 6 * * 1'
  workflow_dispatch:

permissions:
  contents: read

jobs:

  # --------------------------------------------------------------------------
  # DÉPENDANCES PYTHON — pip-audit sur requirements.txt et requirements-dev.txt
  # --------------------------------------------------------------------------
  deps-python:
    name: Deps Python (pip-audit)
    runs-on: ubuntu-latest

    defaults:
      run:
        working-directory: ./backend

    steps:
      - uses: actions/checkout@v5

      - name: Setup Python 3.11
        uses: actions/setup-python@v6
        with:
          python-version: '3.11'
          cache: 'pip'
          cache-dependency-path: backend/requirements-dev.txt

      - name: Install dependencies (dont pip-audit)
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements-dev.txt

      - name: Audit CVE (requirements.txt)
        continue-on-error: true
        run: pip-audit -r requirements.txt --desc

      - name: Audit CVE (requirements-dev.txt)
        continue-on-error: true
        run: pip-audit -r requirements-dev.txt --desc

  # --------------------------------------------------------------------------
  # SAST PYTHON — bandit sur le code backend (tests et migrations exclus)
  # --------------------------------------------------------------------------
  sast-python:
    name: SAST Python (bandit)
    runs-on: ubuntu-latest

    defaults:
      run:
        working-directory: ./backend

    steps:
      - uses: actions/checkout@v5

      - name: Setup Python 3.11
        uses: actions/setup-python@v6
        with:
          python-version: '3.11'
          cache: 'pip'
          cache-dependency-path: backend/requirements-dev.txt

      - name: Install dependencies (dont bandit)
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements-dev.txt

      - name: Analyse statique (bandit)
        continue-on-error: true
        # -c pyproject.toml : lit [tool.bandit] (exclusions migrations/venv/fixtures)
        # -r . : parcours récursif ; -q : sortie concise
        # --exclude : écarte les fichiers de tests tests.py (que exclude_dirs ne
        #   peut pas cibler). Neutralise B101 (assert) ET B105/B106 (mots de
        #   passe de test en dur) sans affaiblir la détection sur le code applicatif.
        run: >
          bandit -c pyproject.toml -r . -q
          --exclude ./accounts/tests.py,./administration/tests.py,./llm/tests.py,./quizzes/tests.py

  # --------------------------------------------------------------------------
  # DÉPENDANCES FRONTEND — npm audit (seuil high)
  # --------------------------------------------------------------------------
  deps-frontend:
    name: Deps Frontend (npm audit)
    runs-on: ubuntu-latest

    defaults:
      run:
        working-directory: ./frontend

    steps:
      - uses: actions/checkout@v5

      - name: Setup Node 20
        uses: actions/setup-node@v5
        with:
          node-version: '20'
          cache: 'npm'
          cache-dependency-path: frontend/package-lock.json

      - name: Install dependencies
        # npm ci STRICT (sans fallback) : divergence assumée vs ci.yml, qui
        # tolère `npm ci || npm install`. Un audit n'a de sens que sur une
        # install parfaitement déterministe issue du lockfile.
        run: npm ci

      - name: Audit CVE (npm audit)
        continue-on-error: true
        run: npm audit --audit-level=high

  # --------------------------------------------------------------------------
  # SECRETS — gitleaks sur l'ensemble du dépôt (fichiers + historique)
  # --------------------------------------------------------------------------
  secrets:
    name: Secrets (gitleaks)
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v5
        with:
          # Historique complet nécessaire pour scanner tous les commits
          fetch-depth: 0

      - name: Scan de secrets (gitleaks)
        continue-on-error: true
        uses: gitleaks/gitleaks-action@v2
        env:
          # Utilise l'allowlist du dépôt (.env.prod.example uniquement ;
          # .env.example n'est PAS allowlisté tant que la vraie clé Brevo
          # fuitée n'est pas révoquée/remplacée — cf. spec §5.1)
          GITLEAKS_CONFIG: ${{ github.workspace }}/.gitleaks.toml
```

> **Note sur gitleaks-action** : l'action `gitleaks/gitleaks-action@v2` peut, selon l'organisation, demander une variable `GITLEAKS_LICENSE` (gratuite pour les comptes personnels et l'open source). Si l'organisation l'exige, l'ajouter en secret de dépôt et l'exposer via `env: GITLEAKS_LICENSE: ${{ secrets.GITLEAKS_LICENSE }}`. Pour un dépôt public / personnel, aucune licence n'est requise. Alternative sans action : installer le binaire gitleaks et lancer `gitleaks detect --config .gitleaks.toml --redact` (voir §8).

---

## 5. Fichiers de configuration

### 5.1 `.gitleaks.toml` (racine du dépôt)

Objectif : partir de la configuration par défaut de gitleaks (`useDefault = true`, qui embarque toutes les règles standard) et ajouter une **allowlist minimale** pour éviter les faux positifs sur le fichier d'exemple qui ne contient que des **placeholders** : `.env.prod.example` (valeurs `<COLLER_...>`).

> **IMPORTANT — `.env.example` n'est PAS mis en allowlist.** Contrairement à `.env.prod.example`, le fichier `.env.example` (suivi par git, dépôt public) contient une **vraie clé SMTP Brevo en clair** ainsi que son login, documentée par le dépôt comme **compromise / déjà fuitée** (`docs/11-deploiement-vps-ovh.md:497`). L'ajouter à l'allowlist par chemin neutraliserait la détection du **seul vrai secret fuité du repo**, alors que la détection de secrets est le livrable central de cette CI. Il ne pourra être ajouté à l'allowlist **qu'après** la remédiation décrite ci-dessous (une fois la vraie clé remplacée par un placeholder factice).

#### Remédiation préalable obligatoire (avant activation du scan)

Le job `secrets` ne devient réellement pertinent qu'une fois cette remédiation effectuée sur `.env.example` :

1. **Révoquer** la clé SMTP Brevo côté Brevo (elle est publiquement fuitée : la considérer comme définitivement compromise).
2. **Remplacer** dans `.env.example` la valeur réelle (`BREVO_SMTP_KEY=...`, `BREVO_SMTP_LOGIN=...`) par un **placeholder factice** (ex. `BREVO_SMTP_KEY=<COLLER_CLE_BREVO>`).
3. **Purger l'historique git** (idéalement) : retirer la clé du fichier courant **ne suffit pas**, car elle reste accessible dans l'historique public du dépôt (via `git filter-repo` ou l'outil équivalent). Sans purge, gitleaks continuera légitimement de la remonter lors du scan de l'historique (`fetch-depth: 0`).

Tant que cette remédiation n'est pas faite, il est **normal et souhaité** que gitleaks remonte ce secret : c'est le comportement attendu de l'outil. Une fois la clé remplacée par un placeholder, `.env.example` pourra être ajouté à l'allowlist par chemin au même titre que `.env.prod.example`.

Chemin cible : `.gitleaks.toml`

```toml
# ============================================================================
# EduTutor IA — Configuration gitleaks
# ----------------------------------------------------------------------------
# Part des règles par défaut de gitleaks (useDefault = true) et ajoute une
# allowlist MINIMALE pour le seul fichier d'exemple ne contenant que des
# placeholders : .env.prod.example.
#
# .env.example n'est PAS en allowlist : il contient une vraie clé SMTP Brevo
# fuitée/compromise (voir spec §5.1). Il ne pourra y être ajouté qu'APRÈS
# remédiation (révocation + remplacement par un placeholder).
# ============================================================================

title = "EduTutor IA - gitleaks config"

[extend]
# Charge le jeu de règles par défaut de gitleaks (recommandé)
useDefault = true

[allowlist]
description = "Fichier d'exemple ne contenant que des placeholders"
# Ignore intégralement ces chemins (regex sur le chemin relatif).
# .env.example est VOLONTAIREMENT absent : vrai secret Brevo fuité à remédier.
paths = [
  '''(^|/)\.env\.prod\.example$''',
]
# Filet de sécurité restreint : seulement des placeholders explicites et non
# ambigus (chaînes qui ne peuvent pas apparaître dans un vrai secret).
# Pas de sous-chaînes larges comme "example"/"dummy" qui masqueraient un vrai
# secret dont la valeur contiendrait ces fragments.
regexes = [
  '''(?i)(changeme|your[_-]?key[_-]?here)''',
]
```

> Le tableau `paths` ne neutralise que `.env.prod.example` (placeholders uniquement). `.env.example` est délibérément exclu de l'allowlist tant que la vraie clé Brevo n'est pas révoquée et remplacée par un placeholder (voir « Remédiation préalable obligatoire »). Le tableau `regexes` est volontairement restreint à des placeholders explicites (`changeme`, `your_key_here`) : les motifs larges de type `example`/`dummy` ont été **retirés** car, appliqués à tout le dépôt, ils risqueraient de masquer un vrai secret dont la valeur contiendrait ces sous-chaînes. Si un vrai secret apparaît un jour dans un fichier d'exemple, il faut le retirer et le révoquer — l'allowlist ne doit couvrir que de vrais placeholders.

### 5.2 Ajouts à `backend/requirements-dev.txt`

Ajouter, à la fin du fichier, une section outils sécurité avec versions épinglées (reproductibilité locale + CI) :

```text
# Sécurité (audit dépendances + SAST)
pip-audit==2.7.3
bandit==1.8.0
```

Le fichier complet devient alors :

```text
# ============================================================================
# Dépendances dev (linting, tests, formatting)
# ============================================================================

-r requirements.txt

# Tests
pytest==8.3.4
pytest-django==4.9.0
pytest-cov==6.0.0

# Linting et formatting
black==24.10.0
ruff==0.8.4

# Tests utilitaires
factory-boy==3.3.1
faker==33.1.0

# Sécurité (audit dépendances + SAST)
pip-audit==2.7.3
bandit==1.8.0
```

> Ces deux outils sont installés par le job backend de `ci.yml` (qui fait `pip install -r requirements-dev.txt`) mais **n'y sont pas exécutés** — `ci.yml` n'est pas modifié. Ils ne sont exécutés que par `security.yml` et en local. Le léger surcoût d'installation dans `ci.yml` est négligeable (déjà couvert par le cache pip).

### 5.3 Configuration bandit dans `backend/pyproject.toml`

Ajouter une section `[tool.bandit]` au `pyproject.toml` existant du backend. Elle exclut les migrations et environnements virtuels. Point crucial : les **fichiers de tests** ne génèrent pas que des `assert` (B101) ; ils contiennent aussi des **mots de passe en dur** de test (ex. `password='motdepasse123'` dans `accounts/tests.py`) qui déclenchent **B105/B106** (`hardcoded_password_string` / `hardcoded_password_funcarg`). Ces findings **ne sont pas** supprimés par le seul skip de B101 : il faut donc réellement exclure les fichiers de tests, ou skipper B105/B106 en plus.

```toml
[tool.bandit]
# Répertoires exclus du parcours récursif
exclude_dirs = [
    "migrations",
    "venv",
    ".venv",
    "tests_fixtures",
]
# Fichiers de tests : les assert (B101) ET les mots de passe factices (B105/B106)
# ne sont pas des failles exploitables. Les tests suivent les patterns pytest :
# tests.py, test_*.py, *_tests.py — mais bandit n'exclut pas par nom de fichier
# via [tool.bandit], d'où le recours à --exclude en CLI (voir ci-dessous).
tests = []
skips = []
```

> Remarque : bandit exclut par nom de **répertoire** via `exclude_dirs`, pas par nom de fichier. Or les fichiers de tests du projet sont des `tests.py` situés directement dans chaque application (`accounts/tests.py`, `administration/tests.py`, `llm/tests.py`, `quizzes/tests.py`) — ils ne peuvent donc pas être écartés par `exclude_dirs`. Un simple `skips = ["B101"]` **ne suffit pas** : les tests remontent aussi B105/B106 (mots de passe de test en dur). Deux options réellement efficaces :
>
> - **Option retenue (ciblée)** : exclure explicitement les fichiers de tests via l'argument CLI `--exclude` (chemins séparés par des virgules) — c'est le seul moyen d'écarter des `tests.py` par fichier. L'invocation bandit devient :
>   `bandit -c pyproject.toml -r . -q --exclude ./accounts/tests.py,./administration/tests.py,./llm/tests.py,./quizzes/tests.py`.
>   Cela supprime **tous** les findings de test (B101, B105, B106…) sans toucher au code applicatif.
> - **Option alternative (par skips)** : conserver `-r .` sans `--exclude` mais neutraliser globalement les règles bruyantes des tests en ajoutant B105 et B106 à B101 : `skips = ["B101", "B105", "B106"]`, **en documentant** que ce sont des mots de passe de test. Inconvénient : ces règles sont alors désactivées partout, y compris sur le code de production — moins précis que l'exclusion ciblée.
>
> Pour le niveau essentiel, l'**option ciblée (`--exclude` sur les fichiers de tests)** est recommandée : elle neutralise réellement le bruit des tests sans affaiblir la détection sur le code applicatif. La section ci-dessous en donne la variante conseillée (invocation CLI + config).

Variante recommandée — l'invocation bandit exclut les fichiers de tests par `--exclude`, et `[tool.bandit]` ne porte que les exclusions de répertoires :

```toml
[tool.bandit]
exclude_dirs = [
    "migrations",
    "venv",
    ".venv",
    "tests_fixtures",
]
# Pas de skip global de B105/B106 : ces règles restent actives sur le code
# applicatif. Le bruit des fichiers de tests (B101 assert + B105/B106 mots de
# passe factices) est neutralisé en amont par --exclude dans l'invocation CLI.
skips = []
```

Invocation CLI correspondante (à utiliser dans `security.yml` et en local) :

```bash
bandit -c pyproject.toml -r . -q \
  --exclude ./accounts/tests.py,./administration/tests.py,./llm/tests.py,./quizzes/tests.py
```

---

## 6. Stratégie non-bloquant vers bloquant

**Phase 1 — Observation (démarrage, non bloquant)** :

- Tous les steps de scan portent `continue-on-error: true`.
- Le workflow **s'exécute toujours en succès vert**, mais chaque scan affiche ses résultats dans les logs et via le statut de l'étape (croix orange sur l'étape si l'outil renvoie un code non nul).
- Objectif : laisser l'équipe corriger le stock initial de findings (mettre à jour les dépendances vulnérables, corriger les alertes bandit, retirer d'éventuels secrets) sans bloquer les PR le jour de la mise en place.
- Durée conseillée : 1 à 2 sprints, jusqu'à obtenir un état « propre ».

**Phase 2 — Application (bloquant)** :

Pour rendre un contrôle bloquant, **retirer la ligne `continue-on-error: true`** du step concerné. Le job échouera alors si l'outil renvoie un code de sortie non nul, ce qui fait échouer le workflow et (si la protection de branche est activée) bloque le merge.

Ordre de bascule recommandé (du moins bruyant au plus impactant) :

1. **`secrets` (gitleaks)** en premier : une fuite de secret est critique et rare ; à rendre bloquant **une fois la remédiation faite** (clé Brevo de `.env.example` révoquée + remplacée par un placeholder, cf. §5.1) et qu'il n'y a plus de faux positif (l'allowlist par chemin couvre `.env.prod.example`, et `.env.example` seulement après remédiation).
2. **`sast-python` (bandit)** ensuite : une fois les alertes traitées ou explicitement acquittées (via `# nosec` ciblés).
3. **`deps-frontend` (npm audit)** : après avoir résorbé les CVE `high`.
4. **`deps-python` (pip-audit)** : après mise à jour des dépendances vulnérables.

**Protection de branche** (recommandé en phase 2) : dans `Settings → Branches → Branch protection rules` pour `main`, ajouter les jobs `Deps Python (pip-audit)`, `SAST Python (bandit)`, `Deps Frontend (npm audit)` et `Secrets (gitleaks)` comme *required status checks*. Tant qu'ils sont non bloquants (phase 1), **ne pas** les marquer comme requis.

**Gestion des exceptions** (une fois bloquant) :

- **pip-audit** : ignorer une CVE précise et documentée via `--ignore-vuln GHSA-xxxx` (dans le step), en commentant la raison. À réserver aux vulnérabilités sans correctif disponible et non exploitables dans le contexte.
- **bandit** : acquitter une ligne précise avec `# nosec Bxxx` accompagné d'un commentaire justificatif.
- **npm audit** : si une CVE `high` est sans correctif, documenter et éventuellement relever le seuil temporairement, ou utiliser `overrides` dans `package.json`. Éviter d'abaisser durablement `--audit-level`.
- **gitleaks** : n'ajouter à l'allowlist que des faux positifs avérés (jamais un vrai secret — le retirer et le révoquer).

---

## 7. Cron & maintenance

- **Cron** : `0 6 * * 1` (lundi 06:00 UTC). Une exécution planifiée hebdomadaire rescanne le code **inchangé** afin de détecter les CVE **nouvellement publiées** entre deux commits (les bases pip-audit/OSV et npm advisory évoluent en continu). Sans cron, une dépendance vulnérable introduite proprement il y a un mois passerait inaperçue jusqu'au prochain push.
- **Fuseau horaire** : GitHub Actions utilise UTC pour les crons. 06:00 UTC = créneau creux, résultats disponibles en début de semaine.
- **workflow_dispatch** : permet un relancement manuel à tout moment (par ex. après annonce d'une CVE majeure).
- **Maintenance des versions** :
  - Épingler et faire évoluer les versions d'outils (`pip-audit`, `bandit`) dans `backend/requirements-dev.txt` ; monter de version en même temps que les autres outils dev.
  - Garder les versions d'actions alignées sur `ci.yml` (`checkout@v5`, `setup-python@v6`, `setup-node@v5`). Toute montée de version doit être faite **simultanément** dans les deux workflows.
  - Réviser `.gitleaks.toml` si de nouveaux fichiers d'exemple apparaissent.
  - Revue trimestrielle : vérifier le taux de faux positifs, ajuster `--audit-level`, et décider des bascules non-bloquant → bloquant restantes.
- **Note cron sur dépôt peu actif** : GitHub désactive les workflows planifiés après 60 jours d'inactivité du dépôt. Le `workflow_dispatch` sert alors de secours pour réactiver.

---

## 8. Exécution locale

Prérequis : installer les dépendances dev (elles incluent désormais `pip-audit` et `bandit`).

```bash
cd backend
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
```

**Équivalents locaux des jobs CI** :

```bash
# --- deps-python (pip-audit) ---
cd backend
pip-audit -r requirements.txt --desc
pip-audit -r requirements-dev.txt --desc

# --- sast-python (bandit) ---
cd backend
bandit -c pyproject.toml -r . -q \
  --exclude ./accounts/tests.py,./administration/tests.py,./llm/tests.py,./quizzes/tests.py

# --- deps-frontend (npm audit) ---
cd frontend
npm ci
npm audit --audit-level=high

# --- secrets (gitleaks) ---
# Installer le binaire gitleaks (https://github.com/gitleaks/gitleaks/releases)
# puis, depuis la racine du dépôt :
gitleaks detect --config .gitleaks.toml --redact --verbose
```

**Astuce hook local (optionnel)** : pour bloquer une fuite de secret avant même le commit, activer le hook de pré-commit gitleaks :

```bash
gitleaks protect --staged --config .gitleaks.toml --redact
```

> Sur Windows (environnement de dev du projet), lancer ces commandes dans un shell POSIX (Git Bash) ou adapter la navigation de répertoire ; les commandes des outils sont identiques.

---

## 9. Fichiers touchés / créés

| Fichier | Action | Description |
|---------|--------|-------------|
| `.github/workflows/security.yml` | **Créé** | Nouveau workflow sécurité : 4 jobs (pip-audit, bandit, npm audit, gitleaks), déclencheurs push/PR/cron/manuel, non bloquant. |
| `.gitleaks.toml` | **Créé** | Configuration gitleaks : règles par défaut + allowlist par chemin restreinte à `.env.prod.example` (placeholders). `.env.example` **non** allowlisté tant que la vraie clé Brevo fuitée n'est pas révoquée/remplacée (§5.1). |
| `.env.example` | **À remédier** | Contient une vraie clé SMTP Brevo fuitée : révoquer côté Brevo, remplacer par un placeholder, purger l'historique git (préalable à l'activation utile du job `secrets`). |
| `backend/requirements-dev.txt` | **Modifié** | Ajout de `pip-audit==2.7.3` et `bandit==1.8.0` (versions épinglées, reproductibilité locale). |
| `backend/pyproject.toml` | **Modifié** | Ajout de la section `[tool.bandit]` (exclusions migrations/venv/fixtures). Les fichiers de tests sont écartés via `--exclude` à l'invocation (neutralise B101 + B105/B106), pas via un skip global. |
| `.github/workflows/ci.yml` | **Inchangé** | Aucune modification (les outils y sont installés via requirements-dev mais non exécutés). |
| `docs/superpowers/specs/2026-07-01-ci-securite-design.md` | **Créé** | Ce document de conception. |

---

## 10. Critères d'acceptation

1. **Le workflow existe et est valide** : `.github/workflows/security.yml` est présent, YAML valide, et apparaît dans l'onglet Actions de GitHub.
2. **Déclencheurs corrects** : le workflow se lance sur `push` vers `main`, sur `pull_request` vers `main`, via le cron `0 6 * * 1`, et manuellement via `workflow_dispatch`.
3. **Quatre jobs présents** : `deps-python`, `sast-python`, `deps-frontend`, `secrets`, exécutés en parallèle sur `ubuntu-latest`.
4. **Cohérence des versions** : `actions/checkout@v5`, `actions/setup-python@v6` (Python 3.11), `actions/setup-node@v5` (Node 20), avec caches pip/npm et les mêmes `cache-dependency-path` que `ci.yml`.
5. **Non bloquant au démarrage** : chaque step de scan porte `continue-on-error: true` ; une PR contenant des findings **n'est pas bloquée** (le workflow reste vert) mais les findings sont visibles dans les logs.
6. **pip-audit** scanne bien **les deux** fichiers `requirements.txt` et `requirements-dev.txt`.
7. **bandit** s'exécute sur `backend/` avec la config `pyproject.toml` et **exclut réellement les fichiers de tests** (via `--exclude ./accounts/tests.py,./administration/tests.py,./llm/tests.py,./quizzes/tests.py`, ou à défaut via `skips = ["B101", "B105", "B106"]`), de sorte que ni les `assert` (B101) ni les mots de passe factices de test (B105/B106) ne soient remontés comme findings.
8. **npm audit** s'exécute avec `--audit-level=high` sur `frontend/` après `npm ci` déterministe.
9. **gitleaks** scanne fichiers **et** historique (`fetch-depth: 0`). L'allowlist par chemin ne couvre que `.env.prod.example` (placeholders). `.env.example` n'est **pas** allowlisté tant qu'il contient la vraie clé Brevo fuitée : gitleaks **doit** la remonter (comportement attendu, cf. « Remédiation préalable obligatoire »). Une fois la clé révoquée et remplacée par un placeholder, `.env.example` peut être ajouté à l'allowlist par chemin ; le scan ne remonte alors plus aucun faux positif sur les deux fichiers d'exemple.
10. **Permissions minimales** : `permissions: contents: read` au niveau workflow ; aucune permission d'écriture superflue.
11. **Reproductibilité locale** : les commandes de la §8 produisent les mêmes contrôles qu'en CI, avec les versions épinglées de `pip-audit` et `bandit`.
12. **Documentation du passage bloquant** : la procédure de retrait de `continue-on-error` (§6) est présente et l'ordre de bascule est défini.
13. **`ci.yml` inchangé** : le workflow CI d'origine n'est pas modifié et continue de passer.
14. **Cron opérationnel** : une exécution planifiée hebdomadaire est configurée et permet de détecter les CVE nouvellement publiées.
