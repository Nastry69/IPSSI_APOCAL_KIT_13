# Plan d'implémentation — Sprint A « Conformité & sécurité »

> Plan dérivé des specs vérifiées
> [RGPD](../specs/2026-07-01-rgpd-conformite-design.md) et
> [CI sécurité](../specs/2026-07-01-ci-securite-design.md), et du
> [backlog Scrum](../../Cadrage%20projet/etat-des-lieux-et-backlog.md).
>
> **Périmètre Sprint A** : les 5 Must — M1 (ADR LLM), M2 (pages légales),
> M3 (consentement), M4 (export RGPD), M5 (throttling). La CI sécurité (S1) est
> planifiée en Sprint B.
>
> Date : 2026-07-01 · Cible : `backend/` (Django/DRF) + `frontend/` (React/TS).

---

## 0. Ordre des phases & dépendances

```
P1 Throttling (M5) ─┐  indépendant, quick win
P2 ADR LLM (M1) ────┤  indépendant (doc)
P3 Pages légales (M2) ──► P4 Consentement (M3)   (le consentement lie une version des CGU)
P5 Export RGPD (M4) ─────► P6 Export-avant-suppression
P7 Tests + vérification finale
```

Chaque phase est **livrable indépendamment** (une PR par phase recommandée).
Après chaque phase : `make ci` (lint + tests) doit rester vert.

---

## P1 — Throttling anti-brute-force (M5) · effort S

**But** : fermer le brute-force sur le login et le spam d'emails sur le reset.

**Approche** : `ScopedRateThrottle` (n'affecte QUE les vues portant un
`throttle_scope`, donc pas d'impact sur le reste de l'API).

### Étapes
1. `backend/apocal/settings.py` — dans `REST_FRAMEWORK`, ajouter :
   ```python
   "DEFAULT_THROTTLE_CLASSES": ["rest_framework.throttling.ScopedRateThrottle"],
   "DEFAULT_THROTTLE_RATES": {
       "login": "10/min",
       "password_reset": "5/min",
       "export": "3/hour",   # utilisé en P5
   },
   ```
2. `backend/accounts/views.py` :
   - `LoginView` → `throttle_scope = "login"`
   - `PasswordResetRequestView` → `throttle_scope = "password_reset"`
3. **Piège tests** : DRF stocke l'historique de throttle dans le cache (LocMem en
   test). Pour éviter que les tests existants qui enchaînent des logins ne
   reçoivent des 429, le test dédié devra **vider le cache** en `setup`
   (`from django.core.cache import cache; cache.clear()`), et les rates ci-dessus
   sont assez larges pour ne pas gêner les tests nominaux.

### Test (`backend/accounts/tests.py`)
- `test_login_is_throttled` : 11 POST login en échec → le 11ᵉ renvoie **429**
  (vider le cache en amont).

### Vérification
- `pytest backend/accounts/ -k throttle` vert · les tests d'auth existants restent verts.

---

## P2 — ADR de choix du fournisseur LLM (M1) · effort S

**But** : documenter formellement le choix (déjà acté en dur `factory.py:61`).

### Étapes
1. Créer `docs/adr/ADR-0001-fournisseur-llm.md` (nouveau dossier `docs/adr/`) :
   - **Statut** : Accepté · **Date** : 2026-07-01 · **Auteurs** : `[à compléter : noms équipe 13]`.
   - **Contexte** : génération de 10 QCM par LLM ; contraintes latence (R1) et RGPD (R3, le `source_text` du cours part au fournisseur).
   - **Options évaluées** : (a) **Ollama local** (gratuit, sans clé, données **hors cloud**) ; (b) cloud free-tier (Groq/Gemini/Cerebras/Mistral) — rapide mais transfert de données, dont **hors UE** pour la plupart ; (c) cloud payant (OpenAI/Anthropic) ; (d) `mock` (tests).
   - **Décision** : **Ollama en local par défaut** (`LLM_BACKEND=ollama`) — meilleur compromis RGPD (le cours ne quitte pas l'infra) + coût nul. Les fournisseurs cloud restent **sélectionnables depuis l'admin** pour arbitrer latence/qualité au cas par cas.
   - **Conséquences** : latence CPU plus élevée (timeout 600 s), téléchargement du modèle (~4,7 Go) ; **si** un cloud est activé, la Politique de confidentialité (transferts hors UE) et l'ADR doivent être mis à jour. Tout changement de fournisseur = nouvel ADR.
2. Optionnel : lien vers l'ADR depuis `docs/02-llm-integration.md` (qui l'annonçait comme « attendu en J2 »).

### Vérification
- Le fichier existe, rempli (aucun placeholder `Alice/Bob`/`2026-XX-XX`), statut Accepté.

---

## P3 — Rédaction des 4 pages légales (M2) · effort M

**Réf. spec** : RGPD §7 (contenu intégral rédigé des 4 pages).

### Étapes
1. `frontend/src/pages/legal/LegalScaffold.tsx` — étendre le type et le rendu :
   ```ts
   export type LegalSection = {
     title: string;
     hint: string;
     content?: ReactNode; // si présent → rendu réel ; sinon fallback « À compléter — hint »
   };
   ```
   Dans le `.map`, rendre `section.content` s'il existe, sinon le paragraphe « À compléter » actuel. Masquer le bandeau ambre « page à compléter » quand **toutes** les rubriques ont un `content`. **Rétrocompatible** (les pages non remplies restent en mode scaffold).
2. Remplir le `content` des rubriques dans les 4 pages (reprendre le texte rédigé en spec §7) :
   - `ConfidentialitePage.tsx` (10 rubriques — inclut **transferts hors UE** avec OpenAI/Groq/Cerebras/Gemini/**Anthropic**/**OpenRouter**, et le « comment exercer ses droits » : bouton export + suppression compte).
   - `MentionsLegalesPage.tsx` (5 rubriques — hébergeur **OVH SAS**).
   - `CGUPage.tsx` (10 rubriques).
   - `CookiesPage.tsx` (cookies techniques uniquement → pas de bannière).
   - Renseigner la date « Dernière mise à jour ».
3. Balises `[à compléter : …]` uniquement pour : adresse postale, email DPO/contact, SIREN/statut de l'éditeur (cf. spec §11).

### Test (`frontend`)
- `frontend/src/pages/legal/LegalScaffold.test.tsx` : une rubrique avec `content` rend le contenu réel ; sans `content` rend « À compléter ». (`@testing-library/react` déjà installé.)

### Vérification
- Les 4 pages affichent du contenu réel (plus de « À compléter » sauf balises listées) · liens `/legal/...` OK · `npm run build` vert.

---

## P4 — Consentement à l'inscription (M3) · effort M · dépend de P3

**Réf. spec** : RGPD §3 (modèle), §4.5 (serializer), §6.4 (front).

### Étapes (backend)
1. `backend/accounts/models.py` — `Profile` : `consent_accepted_at = models.DateTimeField(null=True, blank=True)` + `consent_version = models.CharField(max_length=20, blank=True, default="")`.
2. `backend/accounts/migrations/0002_profile_consent.py` — migration d'ajout des 2 champs.
3. `backend/accounts/serializers.py` — `SignupSerializer` :
   - champ `accept_terms = serializers.BooleanField(write_only=True, required=True)` avec `validate_accept_terms` qui refuse `False`.
   - dans `create()`, après création du Profile : `consent_accepted_at = timezone.now()`, `consent_version = "2026-07-01"` (constante).
4. **Mettre à jour le test existant** `test_signup_creates_user` (`tests.py:~26`) : ajouter `"accept_terms": True` au payload (sinon 201 → 400).

### Étapes (frontend)
5. `frontend/src/pages/SignupPage.tsx` — case à cocher **obligatoire** avant le bouton, avec liens `target="_blank"` vers `/legal/cgu` et `/legal/confidentialite` ; bouton désactivé tant que non cochée ; envoyer `accept_terms` dans l'appel signup.
6. `frontend/src/api/auth.ts` — ajouter `accept_terms` au payload de `signup`.

### Tests
- Backend : `test_signup_requires_consent` (sans/`false` → 400 ; `true` → 201 + `consent_accepted_at` renseigné).
- Frontend : `SignupPage.test.tsx` — bouton désactivé si case décochée.

### Vérification
- `pytest backend/accounts/` vert (dont le test mis à jour) · signup impossible sans consentement.

---

## P5 — Export RGPD / portabilité (M4) · effort M

**Réf. spec** : RGPD §4 (API), §5 (sécurité token), §8 (email). Livraison **asynchrone par lien email** (token signé, expiration 1 h).

### Étapes (backend)
1. `backend/accounts/export.py` (nouveau) — `build_user_export(user) -> dict` : compte (id, email, first_name, last_name, date_joined), profil (email_verified, created_at, consentement), quizzes (title, source_text, score, created_at, updated_at) + questions (index, prompt, options, correct_index, selected_index).
2. `backend/accounts/tokens.py` — `make_export_token(user)` / `read_export_token(token)` via `signing.dumps`/`signing.loads` (salt dédié, `max_age=3600`).
3. `backend/accounts/emails.py` — `send_export_email(user, download_url)`.
4. `backend/accounts/views.py` :
   - `RequestExportView` — `POST /api/accounts/export/request/` (IsAuthenticated, `throttle_scope = "export"`) → génère le token, envoie l'email best-effort, réponse générique.
   - `DownloadExportView` — `GET /api/accounts/export/download/?token=…` (AllowAny) → vérifie le token, renvoie le JSON en pièce jointe (`Content-Disposition: attachment; filename="mes-donnees-edututor.json"`). Ne renvoie **que** les données de l'utilisateur du token.
5. `backend/accounts/urls.py` — router les 2 endpoints.

### Étapes (frontend)
6. `frontend/src/api/auth.ts` — `requestDataExport()` → `POST /accounts/export/request/`.
7. `frontend/src/pages/ProfilePage.tsx` — **activer** le bouton « Exporter mes données » (retirer `disabled`) → appelle `requestDataExport()` → message « Un lien d'export vient de vous être envoyé par email ».

### Tests (`backend/accounts/tests.py`)
- `test_export_request_sends_email` · `test_export_download_valid_token` (JSON complet, bon `Content-Type`) · `test_export_download_rejects_invalid_token` (400) · `test_export_isolation` (le token de A ne renvoie pas les données de B).

### Vérification
- `pytest backend/accounts/` vert · en mode console, l'email d'export s'affiche dans les logs · le lien télécharge un JSON complet.

---

## P6 — Export avant suppression · effort S · dépend de P5

### Étapes
1. `frontend/src/pages/ProfilePage.tsx` — dans la « Zone de danger », au-dessus du formulaire de suppression : rappel + bouton **« Exporter mes données d'abord »** déclenchant `requestDataExport()`. **Non bloquant** (pas de changement backend).

### Vérification
- Le parcours de suppression propose l'export au préalable.

---

## P7 — Vérification finale du sprint

1. `make lint` puis `make test` (pytest + vitest) → **tout vert**.
2. Revue manuelle : parcours complet inscription (avec consentement) → génération quiz → export (email → téléchargement JSON) → suppression (avec proposition d'export).
3. Mettre à jour `CHANGELOG.md` (section RGPD/sécurité) et le badge de version si pertinent.
4. Ouvrir les PR (une par phase de préférence), template PR + Conventional Commits.

---

## Récapitulatif des fichiers

**Créés** : `docs/adr/ADR-0001-fournisseur-llm.md` · `backend/accounts/export.py` · `backend/accounts/migrations/0002_profile_consent.py` · `frontend/src/pages/legal/LegalScaffold.test.tsx` · `frontend/src/pages/SignupPage.test.tsx`.

**Modifiés** : `backend/apocal/settings.py` · `backend/accounts/{models,serializers,views,tokens,emails,urls,tests}.py` · `frontend/src/api/auth.ts` · `frontend/src/pages/{ProfilePage,SignupPage}.tsx` · `frontend/src/pages/legal/{LegalScaffold,ConfidentialitePage,MentionsLegalesPage,CGUPage,CookiesPage}.tsx`.

## Critères d'acceptation du Sprint A
- [ ] Login & password-reset throttlés (429 au-delà du seuil).
- [ ] ADR-0001 rédigé, statut Accepté, sans placeholder fictif.
- [ ] 4 pages légales affichent du contenu réel (transferts hors UE complets).
- [ ] Inscription impossible sans consentement ; consentement horodaté + versionné.
- [ ] Export RGPD fonctionnel (lien email → JSON complet, isolé par utilisateur, token expirant).
- [ ] Export proposé avant la suppression de compte.
- [ ] `make ci` vert.
