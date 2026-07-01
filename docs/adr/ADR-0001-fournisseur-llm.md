# ADR-0001 — Choix du fournisseur LLM pour la génération de QCM

- **Statut** : Accepté
- **Date** : 2026-07-01
- **Auteurs (équipe 13)** : Tristan DZIOCH, Sebastien GERARD, Syphax ALILI,
  Killian MARTINS, Amine TALEB, Jacqueline MAPENZI, Moussa DIOP

---

## Contexte

Le cœur fonctionnel d'EduTutor IA est la génération, par un modèle de langage
(LLM), de **10 QCM** à partir du texte d'un cours (`source_text`) fourni par
l'utilisateur (saisie directe ou extraction PDF). Ce choix de fournisseur
conditionne directement deux contraintes du cahier des charges :

- **R1 — Latence** : la génération doit rester dans une enveloppe de temps
  acceptable pour l'utilisateur. Un modèle local sur CPU est nettement plus lent
  qu'une API cloud accélérée (GPU/ASIC).
- **R3 — RGPD / confidentialité** : le `source_text` du cours est **envoyé au
  fournisseur** pour être analysé. Dès qu'un fournisseur cloud est utilisé, ce
  contenu **quitte notre infrastructure** et, pour la plupart des offres, part
  **hors Union européenne**. Cela déclenche des obligations de transparence
  (Politique de confidentialité) et de transferts encadrés.

Le code applicatif est déjà découplé du fournisseur (patron Strategy + Factory,
cf. `backend/llm/services/factory.py`) : le fournisseur effectif est résolu à
l'exécution via `LLM_BACKEND` (variable d'environnement) ou via la configuration
stockée en base et pilotable depuis l'admin Django. Le présent ADR **acte** ce
choix par défaut, jusqu'ici implicite dans le code.

---

## Options évaluées

### (a) Ollama en local
Modèle exécuté sur notre propre infrastructure (conteneur `ollama`).

- **Avantages** : **gratuit**, **aucune clé API** à gérer, données **hors
  cloud** — le `source_text` ne quitte jamais notre infrastructure (meilleur
  profil RGPD).
- **Inconvénients** : latence CPU élevée (plusieurs minutes pour 10 QCM),
  téléchargement du modèle (~4,7 Go), qualité en retrait des grands modèles
  cloud.

### (b) Cloud « free-tier » (Groq / Gemini / Cerebras / Mistral)
Offres gratuites d'API d'inférence.

- **Avantages** : **très rapide** (bonne réponse à R1), qualité souvent
  supérieure, pas de coût direct sur le palier gratuit.
- **Inconvénients** : le `source_text` est **transféré** au fournisseur, le plus
  souvent **hors UE** (Groq, Gemini, Cerebras aux États-Unis ; Mistral, éditeur
  européen, restant l'exception) ; quotas et disponibilité du free-tier
  incertains ; dépendance à un tiers.

### (c) Cloud payant (OpenAI / Anthropic)
API commerciales premium.

- **Avantages** : meilleure qualité et latence maîtrisée.
- **Inconvénients** : **coût récurrent**, transfert de données **hors UE**,
  clés à sécuriser. Réservé à une future version premium.

### (d) Mock
Faux QCM déterministes générés localement, sans LLM.

- **Avantages** : instantané, sans dépendance, idéal pour les **tests** et le
  développement hors-ligne.
- **Inconvénients** : ne produit aucun contenu réel — inutilisable en
  production.

---

## Décision

**Ollama en local est le fournisseur par défaut** (`LLM_BACKEND=ollama`).

C'est le **meilleur compromis RGPD** : le texte du cours **ne quitte pas notre
infrastructure**, ce qui satisfait R3 sans mécanisme de transfert hors UE ni
mise à jour de la Politique de confidentialité. Le **coût est nul** et aucune
clé API n'est requise, ce qui simplifie l'exploitation et le déploiement
pédagogique.

Les fournisseurs cloud (options b et c) et le mock (option d) restent
**sélectionnables depuis l'admin Django** (configuration en base prioritaire sur
la variable d'environnement). On peut ainsi arbitrer **au cas par cas** entre
latence, qualité et confidentialité, sans redéploiement, tout en gardant Ollama
comme défaut sûr.

---

## Conséquences

- **Latence CPU** plus élevée : un modèle 8B met facilement plusieurs minutes
  pour 10 QCM sur CPU. Le délai d'attente est fixé en conséquence
  (`OLLAMA_TIMEOUT = 600 s`).
- **Téléchargement du modèle** (~4,7 Go) au premier lancement du conteneur
  `ollama`, à prévoir dans la mise en route.
- **Si un fournisseur cloud est activé** (par l'admin ou via `LLM_BACKEND`), le
  `source_text` part chez ce tiers, souvent **hors UE** : la **Politique de
  confidentialité** (section transferts hors UE) **doit être mise à jour** en
  conséquence, et cet ADR révisé.
- **Gouvernance** : **tout changement de fournisseur par défaut donne lieu à un
  nouvel ADR** documentant le nouveau compromis latence / qualité / RGPD.
