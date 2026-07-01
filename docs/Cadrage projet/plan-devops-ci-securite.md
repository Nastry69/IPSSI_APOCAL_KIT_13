# Plan DevOps — CI, sécurité & déploiement — EduTutor IA (équipe 13)

> **Rôle DevOps.** Feuille de route qualité/sécurité/livraison, adossée à
> l'[état des lieux](./etat-des-lieux-et-backlog.md). Aucun code applicatif
> modifié pour produire ce document.
>
> Date : 2026-07-01 · Périmètre : APOCAL'IPSSI 2026.

---

## 1. État actuel de la chaîne

| Élément | État | Détail |
|---|---|---|
| CI GitHub Actions | 🟢 | `.github/workflows/ci.yml` : job **backend** (ruff · black · `manage.py check` · migrate · pytest+cov) et job **frontend** (eslint · prettier · build TS · vitest), sur push/PR `main` |
| Pre-commit | 🟢 | black, ruff, prettier, `detect-private-key`, conventional-commits (`.pre-commit-config.yaml`) |
| Scan sécurité CI | 🔴 | **Aucun** : pas de scan de dépendances, pas de SAST, pas de scan de secrets, pas de `check --deploy` |
| Hardening prod | 🟢 | `settings.py:306-324` sous `SECURE_PROD` (SSL redirect, HSTS 1 an, cookies secure/httponly, nosniff, X-Frame DENY), câblé via `docker-compose.prod.yml` |
| Gestion des secrets | 🟡 | `.env` non suivi par git ✅ ; mais **clés API LLM stockées en clair** en base (`llm/models.py:13`) |
| Déploiement | 🟢 | VPS OVH + Caddy (HTTPS) documenté (`docs/11-deploiement-vps-ovh.md`), override prod Docker |

---

## 2. Volet sécurité CI (niveau « essentiel ») — [S1]

Nouveau workflow dédié **`.github/workflows/security.yml`** (push/PR `main` + **cron hebdomadaire**).
Détail d'implémentation complet dans la spec
[`docs/superpowers/specs/2026-07-01-ci-securite-design.md`](../superpowers/specs/2026-07-01-ci-securite-design.md).

| Outil | Cible | Rôle | Blocage initial |
|---|---|---|---|
| **pip-audit** | `backend/requirements*.txt` | CVE dépendances Python | non bloquant |
| **bandit** | `backend/` (hors tests) | SAST Python | non bloquant |
| **npm audit** | `frontend/` (`--audit-level=high`) | CVE dépendances front | non bloquant |
| **gitleaks** | tout le repo | scan de secrets | non bloquant |
| **`manage.py check --deploy`** | settings prod | valide le hardening `SECURE_PROD` (aujourd'hui non testé) | non bloquant |

**Config associée** : `pip-audit` + `bandit` ajoutés à `requirements-dev.txt` (reproductibilité locale) ; `.gitleaks.toml` avec allowlist pour `.env.example`/`.env.prod.example`.

---

## 3. Stratégie non-bloquant → bloquant

1. **Phase 1 (jour J)** — steps de scan en `continue-on-error: true`. La CI **rapporte** sans casser les PR de l'équipe. On triage la baseline (faux positifs, CVE réelles).
2. **Phase 2 (baseline traitée)** — retirer `continue-on-error` sur les scans stabilisés (gitleaks et `check --deploy` en premier, puis pip-audit/npm audit sur seuil `high`). La CI devient **bloquante**.
3. **Entretien** — le **cron hebdomadaire** capte les CVE publiées après coup ; **Dependabot** (`.github/dependabot.yml`) propose les montées de version.

---

## 4. Autres actions DevOps issues de l'audit

| # | Action | Backlog | Priorité |
|---|---|---|---|
| D1 | Throttling DRF (login, password-reset) — `DEFAULT_THROTTLE_CLASSES` + scopes dans `settings.py` | M5 | Must |
| D2 | Ajouter `python manage.py check --deploy` à la CI | S1 | Should |
| D3 | Dependabot (`.github/dependabot.yml`) pip + npm + actions | S1 | Should |
| D4 | Évaluer le **chiffrement au repos** des clés API LLM (aujourd'hui en clair) | R4 | Should |
| D5 | Restaurer/compléter la couverture de tests (backstop anti-régression) | S2–S4 | Should |
| D6 | Garde-fou taille d'upload PDF côté front (5 Mo) avant transfert | S2 | Should |

---

## 5. Exécution locale (avant push)

```bash
# Backend — qualité + sécurité
cd backend
ruff check . && black --check .
python manage.py check --deploy        # valide le hardening prod
pip-audit -r requirements.txt          # CVE dépendances
bandit -r . -x ./*/tests*,./*/migrations*   # SAST (hors tests/migrations)

# Frontend — qualité + sécurité
cd ../frontend
npm run lint && npm run format:check
npm audit --audit-level=high

# Secrets (tout le repo)
gitleaks detect --no-banner
```

---

## 6. Critères d'acceptation DevOps
- `security.yml` s'exécute sur push/PR `main` **et** en cron hebdo, visible dans l'onglet Actions.
- Les 5 scans produisent un rapport lisible ; aucun ne casse la CI en phase 1.
- `manage.py check --deploy` ne remonte aucune alerte critique en configuration prod.
- Throttling actif et vérifié sur login/reset.
- Passage documenté « non-bloquant → bloquant » une fois la baseline traitée.
