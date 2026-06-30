# ADR-0001 : Choix du modèle LLM pour la génération de quiz

## Statut

Proposed

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
| Latence moyenne | _TBD_ |
| Taux JSON valide | _TBD_ |
| Score qualité (sur 10) | _TBD_ |

---

### Option 2 : Groq — `llama-3.3-70b-versatile`

**Avantages** :
- Inférence ultra-rapide (hardware Groq custom)
- Free tier généreux
- Modèle Llama 3.3 70B — haute qualité

**Inconvénients** :
- Données envoyées hors UE
- Rate limits sur le free tier

**Résultats benchmark** :
| Métrique | Résultat |
|---|---|
| Latence moyenne | _TBD_ |
| Taux JSON valide | _TBD_ |
| Score qualité (sur 10) | _TBD_ |

---

### Option 3 : Mistral AI — `mistral-small-latest`

**Avantages** :
- Fournisseur français, données traitées en UE (RGPD)
- Free tier disponible
- Bonne qualité sur textes académiques francophones

**Inconvénients** :
- Latence plus élevée que Groq
- Modèle "small" potentiellement moins capable sur tâches complexes

**Résultats benchmark** :
| Métrique | Résultat |
|---|---|
| Latence moyenne | _TBD_ |
| Taux JSON valide | _TBD_ |
| Score qualité (sur 10) | _TBD_ |

---

### Option 4 : Gemini — `gemini-1.5-flash`

**Avantages** :
- Clé gratuite sans carte bancaire (Google AI Studio)
- Bon support du structured output JSON
- Contexte long (utile pour PDF denses)

**Inconvénients** :
- Données envoyées hors UE
- Free tier limité en quota

**Résultats benchmark** :
| Métrique | Résultat |
|---|---|
| Latence moyenne | _TBD_ |
| Taux JSON valide | _TBD_ |
| Score qualité (sur 10) | _TBD_ |

---

### Option 5 : Cerebras — `llama3.1-8b`

**Avantages** :
- Inférence très rapide (hardware Cerebras)
- Free tier disponible

**Inconvénients** :
- Modèle 8B moins puissant que 70B
- Données hors UE

**Résultats benchmark** :
| Métrique | Résultat |
|---|---|
| Latence moyenne | _TBD_ |
| Taux JSON valide | _TBD_ |
| Score qualité (sur 10) | _TBD_ |

---

## Méthodologie du benchmark

**Corpus de test** : _TBD_ textes académiques (thèmes variés, longueurs variées — 200, 1 000, 3 000 caractères).

**Métriques collectées par provider** :
- Latence end-to-end (moyenne sur N appels)
- Taux de succès JSON (`parse_and_validate_quiz` sans exception)
- Score qualité questions : pertinence + difficulté + diversité (grille ci-dessous)
- Nombre de tokens consommés (si l'API expose `usage`)

**Grille de scoring qualité (sur 10)** :

| Critère | Poids | Description |
|---|---|---|
| Pertinence au cours | 40 % | Les questions portent sur le contenu fourni |
| Formulation claire | 25 % | Questions et options non ambiguës |
| Diversité | 20 % | Pas de répétition de la même idée |
| Difficulté adaptée | 15 % | Ni triviales ni impossibles |

**Textes de test utilisés** :
1. _TBD_ — (sujet, longueur)
2. _TBD_ — (sujet, longueur)
3. _TBD_ — (sujet, longueur)

**Script de benchmark** : `scripts/benchmark_llm.py` _(à créer)_

---

## Tableau comparatif final

| Provider | Latence moy. | Taux JSON | Qualité /10 | Coût | RGPD UE | Score global |
|---|---|---|---|---|---|---|
| Ollama llama3.1:8b | _TBD_ | _TBD_ | _TBD_ | Gratuit | ✅ | _TBD_ |
| Groq llama-3.3-70b | _TBD_ | _TBD_ | _TBD_ | Free tier | ❌ | _TBD_ |
| Mistral small | _TBD_ | _TBD_ | _TBD_ | Free tier | ✅ | _TBD_ |
| Gemini 1.5-flash | _TBD_ | _TBD_ | _TBD_ | Free tier | ❌ | _TBD_ |
| Cerebras llama3.1:8b | _TBD_ | _TBD_ | _TBD_ | Free tier | ❌ | _TBD_ |

---

## Décision

**Nous choisissons _[PROVIDER À COMPLÉTER]_** comme provider LLM de production.

Raisons principales :
1. _TBD_
2. _TBD_
3. _TBD_

## Conséquences

### Positives

* _TBD_

### Négatives

* _TBD_

### Neutres

* Les providers non retenus restent configurables via `LLM_BACKEND` pour les développeurs
* Revue dans 6 mois si de nouveaux modèles libres émergent (Llama 4, Mistral Next…)

---

## Liens

* Architecture LLM : [02-llm-integration.md](./02-llm-integration.md)
* Bonnes pratiques ADR : [07-bonnes-pratiques.md](./07-bonnes-pratiques.md)
* Script de benchmark : `scripts/benchmark_llm.py` _(à créer)_
