## Tableau comparatif — résultats benchmark

_Corpus : 3 textes × 1 run(s) par provider._

| Provider | Modèle | JSON OK | Lat. moy. | Lat. min | Lat. max | Qualité /10 | Pertinence | Formulation | Diversité | Difficulté | RGPD UE |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Ollama | llama3.1:8b | ERREUR — Tous les runs ont échoué | — | — | — | — | — | — | — | — | — |
| Groq | llama-3.3-70b-versatile | ERREUR — Clé API manquante — définissez GROQ_API_KEY | — | — | — | — | — | — | — | — | — |
| Mistral | mistral-small-latest | ERREUR — Clé API manquante — définissez MISTRAL_API_KEY | — | — | — | — | — | — | — | — | — |
| Gemini | gemini-1.5-flash | ERREUR — Clé API manquante — définissez GEMINI_API_KEY | — | — | — | — | — | — | — | — | — |
| Cerebras | llama-3.3-70b | ERREUR — Clé API manquante — définissez CEREBRAS_API_KEY | — | — | — | — | — | — | — | — | — |

**Grille qualité (score /10) :**
| Critère | Poids | Mesure automatique |
|---|---|---|
| Pertinence | 40 % | Longueur moyenne des questions (150 chars → 10/10) |
| Formulation | 25 % | % de questions interrogatives (« ? » ou mot interrogatif) |
| Diversité lexicale | 20 % | TTR : ratio mots uniques / mots totaux |
| Difficulté options | 15 % | Longueur moyenne des options (50 chars → 10/10) |