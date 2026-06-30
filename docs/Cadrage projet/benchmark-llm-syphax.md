# Benchmark LLM — EduTutor IA

**Date :** 30 juin 2026
**Script :** `scripts/benchmark_llm.py`
**Exécuté via :** `docker exec apocalipssi-2026-backend`

---

## Contexte

Benchmark des providers LLM intégrés dans EduTutor IA pour la tâche de
**génération de quiz pédagogiques** (10 questions, 4 options, 1 bonne réponse,
sortie JSON strict).

---

## Corpus de test

| # | Titre | Longueur approx. |
|---|---|---|
| 1 | Modèle OSI | ~620 caractères |
| 2 | Sécurité des applications web (OWASP, XSS, SQLi, MFA) | ~1 700 caractères |
| 3 | Bases de données relationnelles et normalisation | ~2 500 caractères |

---

## Résultats mesurés

### Tableau comparatif — données réelles

| Provider | Modèle | Runs OK | JSON OK | Lat. moy. | Lat. min | Lat. max | Qualité /10 |
|---|---|---|---|---|---|---|---|
| **Ollama** | llama3.1:8b | 3/3 | **100 %** | 281.4 s | 264.6 s | 306.9 s | **6.7** |
| **Groq** | llama-3.3-70b-versatile | 6/6 | **100 %** | **2.0 s** | 1.5 s | 2.6 s | **6.7** |
| **Mistral** | mistral-small-latest | 6/6 | **100 %** | 4.4 s | 3.3 s | 5.4 s | **7.4** |
| Cerebras | gpt-oss-120b | 3/18 ⚠️ | — | ~0.8 s | 0.6 s | 1.0 s | ~6.2 ⚠️ |
| Gemini | gemini-2.0-flash | 0/9 ❌ | — | — | — | — | — |

> **Cerebras** : rate limit persistant sur le free tier — seules 3 requêtes ont abouti
> (corpus OSI uniquement). Latence et qualité sont donc indicatives, pas représentatives.
>
> **Gemini** : rate limit 429 dès le premier appel et tout au long des tests. La clé et
> le modèle sont valides (confirmé par un test manuel). Le free tier de `gemini-2.0-flash`
> impose des quotas très bas (15 RPM) qui s'épuisent en quelques minutes de benchmark.
> À retester dans 24h depuis une session fraîche.

---

### Détail qualité par critère

| Provider | Pertinence ×0.40 | Formulation ×0.25 | Diversité ×0.20 | Difficulté ×0.15 | **Total /10** |
|---|---|---|---|---|---|
| **Mistral** | 5.9 | **10.0** | **8.5** | 5.6 | **7.4** |
| **Ollama** | 5.2 | 9.3 | 7.5 | 5.2 | **6.7** |
| **Groq** | 4.3 | **10.0** | 7.5 | **6.4** | **6.7** |
| Cerebras | 4.6 ⚠️ | — | — | — | ~6.2 ⚠️ |
| Gemini | — | — | — | — | — ❌ |

**Grille de scoring (rappel)** :

| Critère | Poids | Mesure automatique |
|---|---|---|
| Pertinence | 40 % | Longueur moyenne des questions (proxy de spécificité) |
| Formulation | 25 % | % de questions interrogatives (« ? » ou mot interrogatif) |
| Diversité | 20 % | Ratio mots uniques / mots totaux (TTR lexical) |
| Difficulté | 15 % | Longueur moyenne des options |

---

### Résultats par corpus — Ollama

| Corpus | Latence | Pertinence | Formulation | Diversité | Difficulté | Qualité /10 |
|---|---|---|---|---|---|---|
| OSI (court) | 306.9 s | 5.4 | 10.0 | 7.0 | 5.4 | 6.9 |
| Sécurité web (moyen) | 272.9 s | 4.9 | 10.0 | 7.1 | 5.9 | 6.8 |
| BDD / normalisation (long) | 264.6 s | 5.4 | 8.0 | 8.4 | 4.2 | 6.5 |

### Résultats par corpus — Groq

| Corpus | Lat. run1 | Qualité run1 | Lat. run2 | Qualité run2 |
|---|---|---|---|---|
| OSI (court) | 1.5 s | 5.8 | 1.5 s | 6.2 |
| Sécurité web (moyen) | 2.3 s | 6.9 | 2.2 s | 6.7 |
| BDD / normalisation (long) | 2.0 s | 7.0 | 2.6 s | 7.4 |

### Résultats par corpus — Mistral

| Corpus | Lat. run1 | Qualité run1 | Lat. run2 | Qualité run2 |
|---|---|---|---|---|
| OSI (court) | 3.3 s | 6.7 | 3.8 s | 6.9 |
| Sécurité web (moyen) | 4.8 s | 7.7 | 5.4 s | 7.9 |
| BDD / normalisation (long) | 4.4 s | 7.2 | 5.0 s | 8.1 |

---

## Notes techniques — Gemini et Cerebras

### Gemini (`gemini-2.0-flash`)

- **Modèle par défaut dans `.env` incorrect** : `gemini-1.5-flash` est déprécié →
  remplacer par `gemini-2.0-flash`.
- **Rate limit free tier** : 15 RPM / 1 500 RPD. Le benchmark (9 appels rapides)
  dépasse le quota instantané. Pour tester : espacer les appels ou attendre la fenêtre
  suivante (reset toutes les minutes).
- **Correction `.env`** : `GEMINI_MODEL=gemini-2.0-flash`

### Cerebras (`gpt-oss-120b`)

- **Modèle par défaut dans `.env` incorrect** : `llama-3.3-70b` n'existe plus sur
  l'API Cerebras → modèles disponibles au 30/06/2026 : `gpt-oss-120b`, `gemma-4-31b`,
  `zai-glm-4.7`.
- **Rate limit free tier** : très restrictif (~1 RPM). Inutilisable en benchmark
  multi-appels sans délai entre requêtes.
- **Correction `.env`** : `CEREBRAS_MODEL=gpt-oss-120b`

---

## Analyse et recommandation

### Score composite pondéré (RGPD-first)

| Critère | Poids |
|---|---|
| Conformité RGPD | 30 % |
| Qualité des quiz | 25 % |
| Vitesse | 20 % |
| Coût | 15 % |
| Fiabilité JSON | 10 % |

| Provider | RGPD | Qualité | Vitesse | Coût | JSON | **Score /10** | Source |
|---|---|---|---|---|---|---|---|
| **Ollama** | 10 | 6.7 | 4 (CPU) | 10 | 10 | **7.6** ★ | ✅ Mesuré |
| **Mistral** | 7 | **7.4** | 8 | 8 | 10 | **7.5** | ✅ Mesuré |
| **Groq** | 3 | 6.7 | **10** | 7 | 10 | **6.5** | ✅ Mesuré |
| Cerebras | 3 | ~6.2 | ~10 | 7 | — | ~6.4 | ⚠️ Partiel |
| Gemini | 2 | — | — | 8 | — | — | ❌ Non mesuré |

### Décision

**Provider recommandé en production : Ollama `llama3.1:8b`**

- RGPD natif : aucune donnée de cours ne quitte le serveur
- 100 % de parsing JSON réussi sur tous les runs
- Qualité 6.7/10 validée sur 3 corpus de longueurs variées
- Coût zéro, aucun quota, aucune clé API à gérer
- ⚠️ Latence ~4-5 min sur CPU — acceptable pour une génération asynchrone ;
  tombe à ~10 s avec un GPU NVIDIA

**Fallback cloud si la latence CPU bloque : Mistral `mistral-small-latest`**

- Meilleure qualité mesurée (7.4/10), seul provider EU du bench cloud
- Free tier disponible, fournisseur français (RGPD)
- 100 % JSON valide sur 6 runs
- Nécessite un ADR de mise à jour + accord équipe avant activation

**Groq** est le plus rapide (2s) mais pénalisé RGPD (US) et qualité identique à
Ollama — pas de raison de basculer sauf si la vitesse prime absolument sur la
souveraineté des données.

---

## Reproduire le benchmark

```bash
# Corriger d'abord les modèles dans .env :
#   GEMINI_MODEL=gemini-2.0-flash
#   CEREBRAS_MODEL=gpt-oss-120b

# Recréer le container pour recharger .env (restart ne suffit pas)
docker compose up -d --force-recreate backend

# Copier le script
docker cp scripts/benchmark_llm.py apocalipssi-2026-backend:/app/benchmark_llm.py

# Lancer (providers cloud rapides d'abord, Ollama séparément)
docker exec apocalipssi-2026-backend \
  python /app/benchmark_llm.py \
  --providers groq mistral \
  --runs 2 --output /tmp/bench_cloud

# Ollama (lent sur CPU — prévoir ~30 min)
docker exec apocalipssi-2026-backend \
  python /app/benchmark_llm.py \
  --providers ollama \
  --runs 2 --output /tmp/bench_ollama

# Récupérer les résultats
docker cp apocalipssi-2026-backend:/tmp/bench_cloud.json ./results/
docker cp apocalipssi-2026-backend:/tmp/bench_ollama.json ./results/
```

> **Note Gemini / Cerebras** : espacer les appels (1 requête/min) pour rester
> dans le free tier. Envisager un compte payant si des données réelles sont requises.

---

## Liens

- Script : `scripts/benchmark_llm.py`
- Documentation LLM : `docs/02-llm-integration.md`
