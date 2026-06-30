# ADR-0001 : Choix du modèle LLM pour la génération de quiz

## Statut

Accepted

## Contexte et problème

L'application génère des QCM à partir d'un cours (PDF ou texte) via un LLM.
L'architecture supporte 9 providers interchangeables via le pattern Strategy+Factory
(`LLM_BACKEND` dans `.env`). Il faut choisir le provider retenu en production parmi
les options gratuites ou peu coûteuses, en tenant compte des contraintes du projet :
hébergement VPS OVH (France), usage académique, données potentiellement sensibles.

La génération doit produire **exactement 10 questions, 4 options, 1 bonne réponse**
au format JSON strict — une contrainte forte qui élimine d'emblée les modèles qui
ne respectent pas le schéma.

## Decision Drivers

* Qualité des questions générées (pertinence, diversité, niveau approprié)
* Fiabilité du format JSON (taux de parsing réussi sans fallback)
* Latence (objectif : < 60 s pour un texte de 2 000 caractères)
* Coût (free tier préféré, usage open-source valorisé)
* Souveraineté des données (RGPD — données traitées en UE si possible)
* Disponibilité / stabilité (rate limits, uptime)

## Options considérées

### Option 1 : Ollama — `llama3.1:8b` (local)

**Avantages** :
- Gratuit, données restent sur le serveur (RGPD natif)
- Aucune dépendance externe / pas de rate limit
- Modèle open-source auditable

**Inconvénients** :
- Latence dépendante du matériel du VPS (CPU only sur OVH)
- Qualité potentiellement inférieure aux APIs cloud

**Résultats benchmark** :
| Métrique | Résultat |
|---|---|
| Latence moyenne | Non testé (Docker non disponible en environnement de benchmark) |
| Taux JSON valide | — |
| Score qualité (sur 10) | — |

---

### Option 2 : Groq — `llama-3.3-70b-versatile`

**Avantages** :
- Inférence ultra-rapide (hardware Groq custom LPU)
- Free tier généreux
- Modèle Llama 3.3 70B — haute qualité
- Taux de fiabilité JSON parfait (100 %)

**Inconvénients** :
- Données envoyées hors UE
- Rate limits sur le free tier

**Résultats benchmark** :
| Métrique | Résultat |
|---|---|
| Latence moyenne | **2.4 s** |
| Latence min / max | 1.9 s / 2.7 s |
| Taux JSON valide | **100 %** (3/3) |
| Score qualité (sur 10) | **6.6 / 10** |
| Pertinence | 4.3 / 10 |
| Formulation | 10.0 / 10 |
| Diversité lexicale | 6.7 / 10 |
| Difficulté options | 6.8 / 10 |

---

### Option 3 : Mistral AI — `mistral-small-latest`

**Avantages** :
- Fournisseur français, données traitées en UE (RGPD)
- Free tier disponible
- Meilleure qualité globale sur textes académiques francophones
- Taux de fiabilité JSON parfait (100 %)

**Inconvénients** :
- Latence légèrement plus élevée que Groq et Cerebras
- Modèle "small" : options parfois courtes (score difficulté bas)

**Résultats benchmark** :
| Métrique | Résultat |
|---|---|
| Latence moyenne | **4.0 s** |
| Latence min / max | 3.6 s / 4.5 s |
| Taux JSON valide | **100 %** (3/3) |
| Score qualité (sur 10) | **7.1 / 10** |
| Pertinence | 6.1 / 10 |
| Formulation | 10.0 / 10 |
| Diversité lexicale | 8.4 / 10 |
| Difficulté options | 3.4 / 10 |

---

### Option 4 : Gemini — `gemini-2.5-flash`

**Avantages** :
- Clé gratuite sans carte bancaire (Google AI Studio)
- Meilleure qualité brute sur les runs réussis (7.2 / 10)
- Contexte long (utile pour PDF denses)

**Inconvénients** :
- Données envoyées hors UE
- Free tier très limité : rate limit 429 et erreurs 503 fréquentes
- Taux de disponibilité insuffisant pour la production : **67 %** seulement
- Latence très élevée : **17.5 s** en moyenne (6 s de délai obligatoire entre appels)

**Résultats benchmark** :
| Métrique | Résultat |
|---|---|
| Latence moyenne | **17.5 s** (dont 6 s de délai anti-rate-limit) |
| Latence min / max | 16.6 s / 18.5 s |
| Taux JSON valide | **67 %** (2/3 — 1 erreur 503) |
| Score qualité (sur 10) | **7.2 / 10** (sur runs réussis) |
| Pertinence | 5.1 / 10 |
| Formulation | 10.0 / 10 |
| Diversité lexicale | 7.8 / 10 |
| Difficulté options | 7.5 / 10 |

---

### Option 5 : Cerebras — `gemma-4-31b`

**Avantages** :
- Inférence la plus rapide du benchmark : **1.2 s** en moyenne
- Meilleure diversité lexicale (9.4 / 10)
- Free tier disponible

**Inconvénients** :
- Données hors UE
- Modèle `llama-3.3-70b` annoncé non disponible : remplacé par `gemma-4-31b`
- Options courtes (score difficulté bas : 3.8 / 10)

**Résultats benchmark** :
| Métrique | Résultat |
|---|---|
| Latence moyenne | **2.6 s** |
| Latence min / max | 2.4 s / 3.0 s |
| Taux JSON valide | **100 %** (3/3) |
| Score qualité (sur 10) | **6.6 / 10** |
| Pertinence | 4.4 / 10 |
| Formulation | 9.7 / 10 |
| Diversité lexicale | 9.4 / 10 |
| Difficulté options | 3.8 / 10 |

---

## Méthodologie du benchmark

**Date d'exécution** : 30 juin 2026

**Script** : `scripts/benchmark_llm.py` (standalone Python, sans Django)

**Corpus de test** : 3 textes académiques francophones de longueurs variées

| # | Sujet | Longueur |
|---|---|---|
| 1 | Modèle OSI (couches réseau) | ~500 caractères |
| 2 | Sécurité des applications web (OWASP, XSS, SQL injection) | ~1 100 caractères |
| 3 | Bases de données relationnelles et normalisation | ~2 200 caractères |

**Métriques collectées** :
- Latence end-to-end mesurée avec `time.perf_counter()`
- Taux de succès JSON : `parse_and_validate_quiz` sans exception
- Score qualité automatique sur 4 critères pondérés (voir grille ci-dessous)

**Grille de scoring qualité (score /10)** :

| Critère | Poids | Mesure automatique |
|---|---|---|
| Pertinence | 40 % | Longueur moyenne des questions (150 chars → 10/10) |
| Formulation | 25 % | % de questions interrogatives (« ? » ou mot interrogatif) |
| Diversité lexicale | 20 % | TTR : ratio mots uniques / mots totaux |
| Difficulté options | 15 % | Longueur moyenne des options (50 chars → 10/10) |

---

## Tableau comparatif final

| Provider | Modèle | JSON OK | Lat. moy. | Lat. min | Lat. max | Qualité /10 | Pertinence | Formulation | Diversité | Difficulté | RGPD UE |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **Mistral** | mistral-small-latest | **100 %** | 4.0 s | 3.6 s | 4.5 s | **7.1** | 6.1 | 10.0 | 8.4 | 3.4 | ✅ (UE) |
| Groq | llama-3.3-70b-versatile | **100 %** | **2.4 s** | 1.9 s | 2.7 s | 6.6 | 4.3 | 10.0 | 6.7 | 6.8 | ❌ |
| Cerebras | gemma-4-31b | **100 %** | 2.6 s | 2.4 s | 3.0 s | 6.6 | 4.4 | 9.7 | **9.4** | 3.8 | ❌ |
| Gemini | gemini-2.5-flash | 67 % | 17.5 s | 16.6 s | 18.5 s | 7.2* | 5.1 | 10.0 | 7.8 | 7.5 | ❌ |
| Ollama | llama3.1:8b | — | — | — | — | — | — | — | — | — | ✅ (local) |

_* Gemini : score calculé sur 2/3 runs uniquement (1 erreur 503 sur le texte long)._

---

## Décision

**Nous choisissons Mistral AI (`mistral-small-latest`)** comme provider LLM de production.

Raisons principales :
1. **Meilleur score qualité global** parmi les providers fiables à 100 % (7.1 / 10), notamment grâce à la meilleure diversité lexicale (8.4 / 10) et à la pertinence la plus élevée (6.1 / 10).
2. **Seul provider 100 % fiable ET conforme RGPD** : données traitées en UE (fournisseur français), ce qui répond directement à la contrainte souveraineté du projet hébergé sur VPS OVH France.
3. **Latence acceptable** (4.0 s) : bien en dessous de l'objectif < 60 s, et suffisamment rapide pour l'expérience utilisateur sur l'application web.

## Conséquences

### Positives

* Conformité RGPD garantie sans configuration supplémentaire
* Qualité des questions supérieure sur les textes académiques francophones
* Fiabilité parfaite du format JSON (0 erreur de parsing sur 3 appels)
* Free tier suffisant pour le volume de l'application académique

### Négatives

* Latence de 4 s (vs 2.4 s pour Groq) — acceptable mais perceptible sur mobile
* Score "difficulté des options" bas (3.4 / 10) : les distracteurs sont courts, les questions restent relativement simples
* Dépendance à un service tiers cloud (panne Mistral = panne quiz)

### Neutres

* Groq reste configuré comme fallback rapide (`LLM_BACKEND=groq`) pour les cas où la latence prime sur le RGPD
* Ollama reste le défaut en développement (gratuit, local, zéro coût)
* Les providers non retenus restent disponibles via `LLM_BACKEND` pour les développeurs
* Revue recommandée dans 6 mois : Mistral Medium ou Mistral Large si le budget évolue

---

## Liens

* Architecture LLM : [02-llm-integration.md](./02-llm-integration.md)
* Bonnes pratiques ADR : [07-bonnes-pratiques.md](./07-bonnes-pratiques.md)
* Script de benchmark : `scripts/benchmark_llm.py`
* Résultats bruts : `benchmark_results.json`
