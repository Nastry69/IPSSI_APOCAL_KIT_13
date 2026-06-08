# IPSSI_APOCAL_KIT 🚀

[![CI](https://github.com/melafrit/IPSSI_APOCAL_KIT/actions/workflows/ci.yml/badge.svg)](https://github.com/melafrit/IPSSI_APOCAL_KIT/actions/workflows/ci.yml)
[![Version](https://img.shields.io/badge/version-1.2.0-indigo)](./CHANGELOG.md)
[![License: CC BY-NC-SA 4.0](https://img.shields.io/badge/License-CC%20BY--NC--SA%204.0-amber.svg)](./LICENSE)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![React](https://img.shields.io/badge/react-18-cyan.svg)](https://react.dev/)

**Kit de démarrage officiel** pour la semaine immersive **APOCAL'IPSSI 2026** —
projet étudiant **EduTutor IA** : plateforme de révision personnalisée à base
de LLM open source.

> ⚡ **30 % du MVP déjà câblé.** Concentrez-vous sur la logique produit et
> votre réactivité agile, pas sur la plomberie.

> 🎓 **Nouveau sur le projet ? Commencez par le [Guide étudiant](./GUIDE-ETUDIANT.md)** —
> de l'installation à votre première fonctionnalité, pas à pas.

### ✨ Déjà inclus

- **Comptes** : inscription / connexion **par email**, validation d'email, mot de
  passe oublié, **page profil** (modifier / supprimer son compte)
- **Quiz** : upload PDF/texte → génération LLM de 10 QCM → correction + score → historique
- **MVP2 (démos)** : tableau de bord de progression, révision des erreurs, **mode sombre**
- **Admin** : interface d'admin (config LLM/app depuis l'UI, gestion des utilisateurs)
- **LLM** : 9 fournisseurs au choix · **Emails** : console (dev) / Brevo (réel)
- **Légal** : 4 pages légales vierges à compléter

---

## 🏗️ Stack

| Couche | Technologie | Version |
|---|---|---|
| Backend | Django + DRF | Python 3.11+ |
| Frontend | React + Vite + TypeScript | React 18 |
| Base de données | PostgreSQL | 16 (Docker) |
| LLM | Ollama (local) · Gemini · Groq · Cerebras · Mistral · OpenRouter · OpenAI · Claude · mock | Choix via `LLM_BACKEND` |
| Parsing PDF | `pypdf` | — |
| Conteneurisation | Docker + Compose | — |
| API docs | drf-spectacular | Swagger UI auto |

---

## 🚀 Démarrage en 4 commandes

```bash
# 1. Forker ce repo dans le compte de votre équipe, puis cloner
git clone https://github.com/VOTRE-EQUIPE/IPSSI_APOCAL_KIT.git
cd IPSSI_APOCAL_KIT

# 2. Copier la config et lancer les services
cp .env.example .env
docker compose up -d

# 3. Télécharger le modèle LLM (~5 min, à faire UNE fois)
make pull-model

# 4. Insérer les données de test et ouvrir l'app
make seed
open http://localhost:3000      # front React
open http://localhost:8000/api/docs  # Swagger UI
```

> 💡 Prérequis : Docker + Docker Compose, ≥ 8 Go RAM dispos pour Ollama,
> ≥ 5 Go d'espace disque pour le modèle.

---

## 📚 Documentation détaillée

👉 **Démarrage guidé pour les étudiants : [GUIDE-ETUDIANT.md](./GUIDE-ETUDIANT.md)**

Le dossier [`docs/`](./docs) contient 11 fiches thématiques :

| Fichier | Sujet |
|---|---|
| [00-getting-started.md](./docs/00-getting-started.md) | Setup détaillé + screenshots + troubleshooting 1ʳᵉ démarrage |
| [01-architecture.md](./docs/01-architecture.md) | Diagramme Django ↔ React ↔ Postgres ↔ Ollama + flux d'auth |
| [02-llm-integration.md](./docs/02-llm-integration.md) | Câblage Ollama, changement de modèle, structure du prompt |
| [03-auth.md](./docs/03-auth.md) | Auth par email, validation, reset, profil, où étendre |
| [04-testing.md](./docs/04-testing.md) | pytest, vitest + tutorial test adversarial (préparation J3) |
| [05-ci-cd.md](./docs/05-ci-cd.md) | GitHub Actions, Conventional Commits, hooks pre-commit |
| [06-troubleshooting.md](./docs/06-troubleshooting.md) | Docker, ports en conflit, Ollama, CORS |
| [07-bonnes-pratiques.md](./docs/07-bonnes-pratiques.md) | ADR, post-mortem, INVEST, MoSCoW + lien cours Agile |
| [08-mvp2-idees.md](./docs/08-mvp2-idees.md) | Catalogue d'idées MVP2 + méthode de priorisation |
| [09-admin.md](./docs/09-admin.md) | Interface d'admin : config LLM/app, utilisateurs, données |
| [10-gestion-projet-github.md](./docs/10-gestion-projet-github.md) | Workflow Git/PR, issues, board GitHub Projects, commits |

---

## 🛠️ Commandes utiles (Makefile)

```bash
make help          # Liste toutes les cibles
make dev           # Lance tous les services
make down          # Arrête tous les services
make logs          # Logs en temps réel
make pull-model    # Télécharge Llama 3.1 8B (1 fois)
make test          # Lance pytest + vitest
make lint          # black, ruff, eslint, prettier
make ci            # lint + test (cible CI)
make seed          # Insère données de test
make reset-db      # ⚠️ Supprime + recrée la DB
```

---

## 🔄 Redéployer après une modification

Après avoir modifié du code ou le `.env`, régénérez les conteneurs avec le
script adapté à votre système. Il reconstruit les images, **recrée les
conteneurs** (prise en compte du code *et* du `.env`) et relance Docker.
Le script se replace tout seul à la racine du projet — lançable de n'importe où.

| Système | Commande |
|---|---|
| **Linux / macOS** | `bash scripts/redeploy.sh` |
| **Windows (PowerShell)** | `powershell -ExecutionPolicy Bypass -File scripts\redeploy.ps1` |

Option **rapide** (`--fast` / `-Fast`) — recrée sans reconstruire les images :

| Système | Commande |
|---|---|
| Linux / macOS | `bash scripts/redeploy.sh --fast` |
| Windows | `powershell -ExecutionPolicy Bypass -File scripts\redeploy.ps1 -Fast` |

> 💡 **Quand utiliser quoi ?**
> - **Modif de code** (Python/JS) → `--fast` suffit (code monté en volume, rechargé à chaud).
> - **Modif du `.env`** (ex. `LLM_BACKEND`, clés API) → `--fast` suffit (recrée les conteneurs).
> - **Modif des dépendances** (`requirements.txt`, `package.json`) ou d'un `Dockerfile` → version **complète** (avec rebuild).
>
> Sous Windows, si PowerShell bloque l'exécution, le préfixe
> `-ExecutionPolicy Bypass` (déjà dans la commande) lève la restriction
> pour cette seule exécution.

---

## 📧 Email (Brevo)

L'application envoie des emails (**validation de compte** à l'inscription,
**réinitialisation de mot de passe**). Le backend bascule **automatiquement** :

- **Sans clé Brevo (défaut dev)** → backend « console » : les emails s'affichent
  dans les **logs du backend**. Idéal pour tester sans compte Brevo ni adresse réelle.
- **Avec une clé SMTP Brevo** → envoi de **vrais emails**.

### Configurer Brevo (envoi réel)

1. Créez un compte sur [brevo.com](https://www.brevo.com)
2. Récupérez votre **clé SMTP** (≠ clé API v3) : <https://app.brevo.com/settings/keys/smtp>
3. Dans `.env` :
   ```bash
   BREVO_SMTP_KEY=xsmtpsib-...
   # ⚠ Le LOGIN est l'identifiant SMTP affiché par Brevo (xxxxx@smtp-brevo.com),
   #   PAS l'email de votre compte — sinon erreur "535 Authentication failed".
   BREVO_SMTP_LOGIN=xxxxx@smtp-brevo.com
   DEFAULT_FROM_EMAIL=EduTutor IA <no-reply@votre-domaine.fr>
   ```
4. Redéployez : `bash scripts/redeploy.sh --fast` (ou `.ps1 -Fast` sous Windows)

### Tester l'envoi

```bash
docker exec apocalipssi-2026-backend python manage.py send_test_email vous@example.com
```
En mode console, l'email s'affiche dans la sortie ; avec Brevo, il part réellement.

---

## 📐 Périmètre attendu (rappel APOCAL'IPSSI)

### MVP must-have — Release 1 (mercredi soir)

| # | Feature |
|---|---|
| F1 | Inscription / connexion **par email** (Django Auth) |
| F2 | Saisie cours (PDF ≤ 5 Mo OU texte ≥ 200 caractères) |
| F3 | Génération auto de 10 QCM via Llama 3.1 8B |
| F4 | Soumission + correction auto |
| F5 | Affichage score /10 + détail |
| F6 | Historique persisté par utilisateur |

### Release 2 — Catalogue de pistes (jeudi soir)

Aucune obligatoire — votre Product Owner et votre Story Map décident.
**Catalogue complet d'idées (valeur / complexité / pistes techniques) :
[docs/08-mvp2-idees.md](./docs/08-mvp2-idees.md).** Trois sont déjà codées comme
exemples : tableau de bord, révision des erreurs, mode sombre.

---

## 🎓 Cours de référence

Cours Agile/Scrum complet utilisé tout au long de la semaine :
**[mohamedelafrit.com/teaching/Master_Classe_Agile](https://mohamedelafrit.com/teaching/Master_Classe_Agile/cours.html)**

---

## 🌐 Site pédagogique APOCAL'IPSSI

Toutes les informations sur la semaine (déroulement, perturbations, modèles,
FAQ) : **[apocal.mohamedelafrit.com](https://apocal.mohamedelafrit.com)**

---

## 👤 Auteur

**Mohamed Amine EL AFRIT** — [mohamedelafrit.com](https://www.mohamedelafrit.com)
GitHub : [@melafrit](https://github.com/melafrit)

## 📄 Licence

**Creative Commons BY-NC-SA 4.0** — voir [LICENSE](./LICENSE)
