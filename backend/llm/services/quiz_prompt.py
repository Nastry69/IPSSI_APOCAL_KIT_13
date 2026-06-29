"""
Prompt système et validation PARTAGÉS pour la génération de quiz.

[Note pédagogique] Cette logique (le prompt qui cadre le LLM + la validation
stricte de sa sortie) est réutilisée par TOUS les clients : Ollama, OpenAI,
Claude. La factoriser ici (principe DRY — Don't Repeat Yourself) évite de la
dupliquer dans chaque client. Conséquence concrète : quand vous améliorerez le
prompt ou durcirez la validation (perturbations J3 « prompt injection » et J4
« qualité »), vous le ferez à UN SEUL endroit, et tous les fournisseurs en
profitent automatiquement.
"""

import json
import logging
import re

from .base import LLMError

logger = logging.getLogger(__name__)

# Limite de caractères en entrée pour ne pas saturer le contexte d'un petit
# modèle (Llama 8B ~8k tokens). Les gros modèles API tolèrent bien plus, mais
# on garde une limite commune pour des coûts/latences maîtrisés.
MAX_SOURCE_CHARS = 8000

# Nombre de questions visé par quiz, et nombre MAX d'appels LLM autorisés pour y
# parvenir (1 génération initiale + compléments ciblés). Borne basse volontaire :
# chaque tentative est un appel LLM complet, coûteux en latence CPU (perturbation
# J2). Exposables en config admin plus tard si besoin.
TARGET_QUESTIONS = 10
MAX_GENERATION_ATTEMPTS = 3

SYSTEM_PROMPT = """Tu es un assistant pédagogique francophone spécialisé en
génération de QCM. À partir du cours fourni, tu génères exactement 10 questions
à choix multiples pour aider un étudiant à réviser.

Règles ABSOLUES :
- Exactement 10 questions.
- Chaque question a EXACTEMENT 4 options.
- Une seule bonne réponse par question, indiquée par "correct_index" (0 à 3).
- Pas de markdown, pas de balises HTML, pas d'explications hors JSON.
- Sortie = JSON STRICT et UNIQUEMENT JSON.

Format de sortie :
{
  "questions": [
    {"prompt": "...", "options": ["...","...","...","..."], "correct_index": 0},
    ... (10 entrées)
  ]
}
"""

# Schéma JSON pour le mode « structured output » d'Ollama (≥ 0.5.0) : passé dans
# le champ `format` de /api/generate, il CONTRAINT le modèle, à la génération, à
# produire cette structure. Cela élimine à la SOURCE l'essentiel des sorties mal
# formées (≠ 4 options, correct_index hors bornes, champ vide) — la cause de
# l'erreur « il faut exactement 4 options ».
#
# On NE borne PAS le nombre de questions ici (`questions` n'a ni minItems ni
# maxItems) : le compte exact de 10 est géré par generate_quiz_robust (les appels
# de complément demandent K ≠ 10 questions), et les petits modèles tiennent mal
# une longueur de tableau imposée par grammaire.
QUIZ_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "questions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "prompt": {"type": "string", "minLength": 1},
                    "options": {
                        "type": "array",
                        "items": {"type": "string", "minLength": 1},
                        "minItems": 4,
                        "maxItems": 4,
                    },
                    "correct_index": {"type": "integer", "minimum": 0, "maximum": 3},
                },
                "required": ["prompt", "options", "correct_index"],
            },
        }
    },
    "required": ["questions"],
}


def build_user_prompt(source_text: str, title: str) -> str:
    """Construit le message utilisateur (cours + consigne finale)."""
    truncated = source_text[:MAX_SOURCE_CHARS]
    return (
        f"TITRE DU COURS : {title}\n\n" f"COURS :\n{truncated}\n\n" f"GÉNÈRE LE JSON MAINTENANT :"
    )


def build_full_prompt(source_text: str, title: str) -> str:
    """Prompt complet (system + user) pour les API « completion » simples
    comme Ollama /api/generate qui n'ont pas de séparation system/user."""
    return f"{SYSTEM_PROMPT}\n\n{build_user_prompt(source_text, title)}"


def build_backfill_prompt(source_text: str, title: str, count: int, seen_prompts: list[str]) -> str:
    """Message utilisateur pour un appel de COMPLÉMENT : on ne redemande que
    `count` questions SUPPLÉMENTAIRES, distinctes de celles déjà obtenues.

    [Note pédagogique] On ne régénère JAMAIS les 10 questions à chaque essai :
    on garde le travail valide déjà produit et on ne demande que ce qui manque
    (gain de latence J2). La liste des énoncés déjà couverts évite les doublons.
    """
    truncated = source_text[:MAX_SOURCE_CHARS]
    deja = "\n".join(f"- {p}" for p in seen_prompts) or "(aucune)"
    return (
        f"TITRE DU COURS : {title}\n\n"
        f"COURS :\n{truncated}\n\n"
        f"Questions DÉJÀ produites (NE PAS les répéter) :\n{deja}\n\n"
        f"GÉNÈRE MAINTENANT EXACTEMENT {count} NOUVELLE(S) question(s), distincte(s) "
        f'des précédentes, au même format JSON {{"questions": [...]}} :'
    )


def _extract_quiz_dict(raw: str) -> dict:
    """Extrait et parse le JSON `{ "questions": [...] }` de la réponse LLM.

    Tolère du texte autour du JSON (fallback regex sur le premier bloc `{...}`).

    Raises:
        LLMError: réponse vide, aucun JSON, JSON invalide, ou clé 'questions'
                  absente.
    """
    if not raw or not raw.strip():
        raise LLMError("Le LLM a renvoyé une réponse vide.")

    # 1. Tente le parse direct (cas idéal : le LLM renvoie du JSON pur)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        # 2. Fallback : extrait le premier bloc { ... } si du texte entoure le JSON
        match = re.search(r"\{[\s\S]*\}", raw)
        if not match:
            raise LLMError("Aucun bloc JSON trouvé dans la réponse LLM.") from None
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError as exc:
            raise LLMError(f"JSON LLM invalide : {exc}") from exc

    if not isinstance(data, dict) or "questions" not in data:
        raise LLMError("Le JSON LLM ne contient pas la clé 'questions'.")
    return data


def validate_question(q: object) -> tuple[dict | None, str | None]:
    """Valide UNE question. Renvoie `(question_nettoyée, None)` si valide, sinon
    `(None, message_d_erreur)`.

    [Note pédagogique] NE JAMAIS faire confiance aveuglément à la sortie d'un
    LLM : prompt non vide, EXACTEMENT 4 options non vides, `correct_index` ∈ 0-3.
    Cette fonction NE lève PAS — c'est l'appelant qui décide quoi faire d'une
    question invalide (la rejeter, ou faire échouer le lot).
    """
    if not isinstance(q, dict):
        return None, "n'est pas un objet."
    prompt = q.get("prompt")
    options = q.get("options")
    correct_index = q.get("correct_index")

    if not isinstance(prompt, str) or not prompt.strip():
        return None, "prompt manquant."
    if not isinstance(options, list) or len(options) != 4:
        return None, "il faut exactement 4 options."
    if not all(isinstance(o, str) and o.strip() for o in options):
        return None, "options invalides."
    # bool est une sous-classe de int en Python : on exclut explicitement True/False.
    if isinstance(correct_index, bool) or not isinstance(correct_index, int):
        return None, "correct_index doit être 0, 1, 2 ou 3."
    if correct_index not in (0, 1, 2, 3):
        return None, "correct_index doit être 0, 1, 2 ou 3."

    return (
        {
            "prompt": prompt.strip(),
            "options": [o.strip() for o in options],
            "correct_index": correct_index,
        },
        None,
    )


def parse_and_validate_quiz(raw: str) -> list[dict]:
    """Validation STRICTE (tout-ou-rien) : extrait le JSON et exige exactement 10
    questions toutes valides. Lève à la PREMIÈRE anomalie.

    Conservée pour les clients qui ne passent pas (encore) par la boucle robuste.
    Pour une validation tolérante (récupération partielle), voir
    parse_valid_questions / generate_quiz_robust.

    Raises:
        LLMError: si la réponse est vide, non-JSON, ou structurellement invalide.
    """
    data = _extract_quiz_dict(raw)

    questions = data["questions"]
    if not isinstance(questions, list):
        raise LLMError("'questions' n'est pas une liste.")

    if len(questions) != TARGET_QUESTIONS:
        logger.warning("LLM a renvoyé %d questions au lieu de %d", len(questions), TARGET_QUESTIONS)
        if len(questions) > TARGET_QUESTIONS:
            questions = questions[:TARGET_QUESTIONS]  # tolérance : on tronque
        else:
            raise LLMError(
                f"Seulement {len(questions)} questions générées ({TARGET_QUESTIONS} attendues)."
            )

    cleaned: list[dict] = []
    for i, q in enumerate(questions, start=1):
        validated, error = validate_question(q)
        if validated is None:
            raise LLMError(f"Question {i} : {error}")
        cleaned.append(validated)

    return cleaned


def parse_valid_questions(raw: str) -> list[dict]:
    """Validation TOLÉRANTE : renvoie la liste des questions valides trouvées,
    en IGNORANT silencieusement les invalides (et un JSON inexploitable → []).

    [Note pédagogique] Contrairement à parse_and_validate_quiz, on ne fait pas
    échouer tout le lot pour une seule question mal formée : on récupère ce qui
    est bon, et generate_quiz_robust régénère le manque.
    """
    try:
        data = _extract_quiz_dict(raw)
    except LLMError:
        return []

    questions = data.get("questions")
    if not isinstance(questions, list):
        return []

    valid: list[dict] = []
    for q in questions:
        validated, _ = validate_question(q)
        if validated is not None:
            valid.append(validated)
    return valid


def _normalize_prompt(text: str) -> str:
    """Clé de dé-duplication d'un énoncé : minuscules + espaces compactés."""
    return re.sub(r"\s+", " ", text).strip().lower()


def generate_quiz_robust(
    complete_fn,
    source_text: str,
    title: str,
    *,
    target: int = TARGET_QUESTIONS,
    max_attempts: int = MAX_GENERATION_ATTEMPTS,
) -> list[dict]:
    """Génère un quiz d'EXACTEMENT `target` questions valides, en tolérant les
    sorties LLM partielles ou partiellement invalides (perturbation J4 « qualité »).

    Stratégie : on garde les questions valides, on les dé-duplique par énoncé, et
    on RÉGÉNÈRE seulement le manque (complément ciblé) jusqu'à atteindre `target`,
    dans la limite de `max_attempts` appels LLM.

    Args:
        complete_fn: fonction `(system: str, user: str) -> str` qui exécute UN
            appel LLM brut et renvoie le texte de la réponse. C'est le seul
            morceau spécifique au fournisseur — la logique de robustesse reste
            ici, mutualisée (DRY).

    Raises:
        LLMError: si on n'atteint pas `target` questions valides après
            `max_attempts` tentatives (message explicite), ou si `complete_fn`
            échoue (LLM injoignable, réponse vide…).
    """
    collected: list[dict] = []
    seen: set[str] = set()

    for attempt in range(1, max_attempts + 1):
        missing = target - len(collected)
        if attempt == 1:
            user = build_user_prompt(source_text, title)
        else:
            user = build_backfill_prompt(
                source_text, title, missing, [q["prompt"] for q in collected]
            )

        raw = complete_fn(SYSTEM_PROMPT, user)

        for q in parse_valid_questions(raw):
            key = _normalize_prompt(q["prompt"])
            if key in seen:
                continue  # doublon : on évite de re-compter la même question
            seen.add(key)
            collected.append(q)
            if len(collected) == target:
                break

        logger.info(
            "Génération quiz : tentative %d/%d — %d/%d questions valides cumulées",
            attempt,
            max_attempts,
            len(collected),
            target,
        )
        if len(collected) >= target:
            break

    if len(collected) < target:
        raise LLMError(
            f"Seulement {len(collected)}/{target} questions valides "
            f"après {max_attempts} tentatives."
        )

    return collected[:target]
