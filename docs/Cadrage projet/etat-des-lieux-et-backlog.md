# État des lieux & backlog priorisé — EduTutor IA (équipe 13)

> **Rôle Scrum Master.** Document de planification produit à partir d'un audit
> automatisé du code réel (11 chantiers, preuves `fichier:ligne`). Aucune ligne
> de code applicatif n'a été modifiée pour produire ce document.
>
> Date : 2026-07-01 · Version projet : 1.2 · Périmètre : APOCAL'IPSSI 2026.

---

## 1. Tableau de bord (état des lieux)

Légende : 🟢 fait (complet et cohérent) · 🟡 partiel (présent mais incomplet/fragile) · 🔴 absent.

| Chantier | Statut | Synthèse | Preuves clés |
|---|---|---|---|
| **F1** — Auth email (validation lien, reset, profil) | 🟢 | Bout-en-bout OK, email=identifiant, anti-énumération sur reset, tokens signés/expirables | `backend/accounts/{models,serializers,views,tokens,emails,urls}.py` ; `frontend/src/pages/{Login,Signup,ForgotPassword,ResetPassword,VerifyEmail,Profile}Page.tsx` |
| **F2** — Saisie cours (PDF ≤5 Mo / texte ≥200 car.) | 🟡 | Limites réelles côté backend (+ rejet PDF chiffré/scanné) ; **0 test PDF**, pas de garde-fou taille au front | `llm/pdf_utils.py:12,32` (5 Mo) · `llm/serializers.py:26` (200 car.) · `UploadPage.tsx:85` |
| **F3** — Génération 10 QCM via LLM local | 🟢 | Ollama = défaut confirmé (settings/factory/providers/.env) ; « 10 » validé Python (rejet/tronquage) | `settings.py:226` · `llm/services/quiz_prompt.py:127` · `llm/services/ollama_client.py` |
| **F4** — Soumission + correction auto | 🟢 | Endpoint scopé propriétaire, correction correcte, bien testé (0/5/10, isolation) | `quizzes/views.py:48-104` · `quizzes/tests.py` |
| **F5** — Score /10 + détail bon/mauvais | 🟢 | Score calculé/persisté côté serveur, coloration front, revue des erreurs | `quizzes/views.py:76-104` · `QuizPage.tsx:104` · `ReviewMistakesPage.tsx` |
| **F6** — Historique par utilisateur | 🟢 | Persistance réelle, isolation stricte par user, 3 dimensions (date/cours/score) | `quizzes/models.py:13-38` · `quizzes/views.py:24-35` · `HistoryPage.tsx` |
| **Légal** — 4 pages (Confid./Mentions/CGU/Cookies) | 🟡 | Ossature complète (routes, footer, 31 rubriques) ; **contenu 100% vide** | `frontend/src/pages/legal/*` (scaffolds « À compléter ») |
| **Sécu prod (J3)** | 🟡 | Hardening solide et découplé de DEBUG ; **non testé**, clés API LLM en clair | `settings.py:306-324` · `docker-compose.prod.yml:41` · `llm/models.py:13` |
| **RGPD (J3-bis)** | 🔴 | Export & consentement inexistants (placeholders + TODO) | `accounts/views.py:271` · `ProfilePage.tsx:224-247` |
| **ADR LLM (J2)** | 🔴 | Seulement un template fictif ; choix acté en dur | `docs/07-bonnes-pratiques.md:8-63` · `llm/services/factory.py:61` |
| **Release 2** (dark/dashboard/révision) | 🟡 | Les 3 existent (à améliorer) ; dark mode = retrofit CSS fragile | `ThemeContext.tsx` · `DashboardPage.tsx` · `ReviewMistakesPage.tsx` |
| **Feedback / signalement (J4)** | 🔴 | Bouton désactivé uniquement ; aucun modèle/endpoint | `ProfilePage.tsx:238-245` |

**Lecture d'ensemble** : le MVP produit (F1–F6) est **présent et fonctionnel** ;
la valeur restante est concentrée sur les **chantiers de la semaine**
(conformité, sécurité, ADR, feedback) et sur la **fiabilisation par les tests**.

---

## 2. Backlog priorisé (MoSCoW)

Effort : **S** ≈ ½ journée · **M** ≈ 1 journée · **L** ≈ 2 journées+ (à 1 dev).

### 🔴 Must — bloquants conformité / sécurité
| # | Item | Effort | Dépend de |
|---|---|---|---|
| M1 | **ADR fournisseur LLM** — créer `docs/adr/ADR-0001-fournisseur-llm.md` (contexte, options Ollama/cloud/mock, décision Ollama par défaut, conséquences, statut Accepté, date/auteurs réels) | S | — |
| M2 | **Rédiger les 4 pages légales** (remplir les 31 rubriques + date de MàJ, sur l'ossature existante) | M | — |
| M3 | **Consentement CGU/confidentialité** — case obligatoire au signup + champ horodaté/versionné sur `Profile` + migration | M | M2 |
| M4 | **Export RGPD (portabilité)** — endpoint + branchement du bouton front + export avant suppression | M | — |
| M5 | **Throttling DRF** sur login & password-reset (`DEFAULT_THROTTLE_CLASSES` + scopes) | S | — |

### 🟠 Should — fiabilisation attendue
| # | Item | Effort |
|---|---|---|
| S1 | **CI sécurité** — `security.yml` (pip-audit, bandit, npm audit, gitleaks) + `manage.py check --deploy` + Dependabot | S |
| S2 | Fiabiliser **F2 (PDF)** — tests `pdf_utils` (5 Mo, chiffré, scanné, extension, extraction) + garde-fou taille au front | M |
| S3 | Fiabiliser **F1** — tests des branches non couvertes (verify-email, resend, reset/confirm, profil GET/PATCH/DELETE, change-password) | M |
| S4 | Fiabiliser **F3/F5/F6** — tests `parse_and_validate_quiz` (10 questions, tronquage, 4 options) + `StatsView`/`MistakesView` | M |

### 🟡 Could — améliorations non bloquantes
| # | Item | Effort |
|---|---|---|
| C1 | Durcir cas-limites **F4/F5** — 4xx (non 500) si quiz ≠ 10 questions, transaction atomique sur la persistance, bornes `correct_index < len(options)`, idempotence resoumission | S |
| C2 | **Anti-triche F5** — brancher `QuestionPublicSerializer` (déjà codé, non utilisé) pour ne pas exposer `correct_index` avant soumission | S |
| C3 | **Améliorer le dark mode** (Release 2) — variantes `dark:` Tailwind sur Dashboard/Review/header au lieu du retrofit CSS | M |
| C4 | **Tests frontend** (Vitest/RTL) sur les flux critiques (auth, score, dashboard, thème) | M |
| C5 | **J4 — Boucle de signalement/feedback** — modèle `Report` + migration + endpoint POST + bouton branché + onglet admin | L |

### ⚪ Won't (this time) — reporté MVP2
| # | Item | Effort |
|---|---|---|
| W1 | Historisation **multi-tentatives** (modèle `Attempt` au lieu d'écraser `Quiz.score`/`selected_index`) | L |

---

## 3. Proposition de découpage en sprints

> Priorité : **débloquer la conformité et la sécurité d'abord** (risque juridique
> réel), puis fiabiliser, puis améliorer. À ajuster avec le PO.

### Sprint A — « Conformité & sécurité » (Musts)
M1 (ADR) · M2 (pages légales) · M3 (consentement) · M4 (export RGPD) · M5 (throttling).
- **Objectif de sprint** : rendre l'application **légalement déployable** et fermer les portes ouvertes d'authentification.
- **En cours** : M2, M3, M4 sont couverts par les specs `2026-07-01-rgpd-conformite-design.md`. M5 + M1 sont les ajouts.

### Sprint B — « Fiabilisation » (Shoulds)
S1 (CI sécurité) · S2 (PDF) · S3 (F1) · S4 (F3/F5/F6).
- **Objectif** : prouver la fiabilité du code réputé « fait » par les tests et outiller la CI.
- **En cours** : S1 est couvert par la spec `2026-07-01-ci-securite-design.md`.

### Sprint C — « Améliorations & Release 2 » (Coulds)
C1 · C2 · C3 · C4 · **C5 (J4 feedback)**.
- **Objectif** : polish, anti-triche, dark mode, et la boucle de feedback J4.
- **Release 2** : améliorer dark mode/dashboard/révision — **ne pas recréer** (déjà fournis).

---

## 4. Definition of Done (rappel équipe)
- Code lint OK (ruff/black/eslint/prettier) et build vert.
- **Tests** ajoutés pour tout nouveau comportement + branches critiques.
- CI verte (dont, à terme, le volet sécurité).
- Docs à jour (README/CHANGELOG/ADR le cas échéant).
- Revue de PR (Conventional Commits, template PR respecté).

---

## 5. Risques (registre)
| # | Risque | Impact | Mitigation (item backlog) |
|---|---|---|---|
| R1 | RGPD/LCEN non satisfait (légal vide, pas de consentement/export) | Juridique, bloque la prod | M2, M3, M4 |
| R2 | Pas de throttling login/reset (brute-force, spam) | Sécurité | M5 |
| R3 | Fiabilité non prouvée (moitié F1, PDF F2, Ollama réel, Stats/Mistakes non testés) | Régressions silencieuses | S2, S3, S4 |
| R4 | Chaîne sécu CI absente ; clés API LLM en clair | Sécurité, dérive de config | S1 (+ chiffrement clés à évaluer) |
| R5 | LLM local : dérive de format / timeout, schéma ne verrouille pas « 10 » | Génération en échec 502 sans retry | S4 (+ retry à évaluer) |
| R6 | Dark mode = retrofit CSS fragile | Incohérences visuelles | C3 |
| R7 | Piège doc : cases `[x]` fictives dans `07-bonnes-pratiques.md` laissent croire J4 fait | Sous-estimation du reste-à-faire | C5 |
