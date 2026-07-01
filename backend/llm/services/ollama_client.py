"""
Client Ollama — appel HTTP vers le service LLM LOCAL (gratuit).

[Note pédagogique] Ollama fait tourner un modèle open-source (Llama, Phi,
Mistral…) en local, sans clé API ni coût. C'est le backend par DÉFAUT du kit :
souveraineté des données + zéro coût. Sa contrepartie est la latence sur CPU
(cf. perturbation J2). Le prompt et la validation sont mutualisés dans
quiz_prompt.py et partagés avec les clients OpenAI / Claude.
"""

import requests
from django.conf import settings

from .base import LLMClient, LLMError
from .quiz_prompt import (
    QUIZ_JSON_SCHEMA,
    SYSTEM_PROMPT,
    build_user_prompt,
    parse_and_validate_quiz,
)
from .study_prompt import build_study_user_prompt, system_prompt_for


class OllamaLLMClient(LLMClient):
    """Client HTTP minimal pour Ollama (/api/generate)."""

    def __init__(
        self, *, model: str | None = None, host: str | None = None, timeout: int | None = None
    ) -> None:
        # Overrides éventuels (config admin en base, Lot 8) sinon valeurs .env.
        self.host = (host or settings.OLLAMA_HOST).rstrip("/")
        self.model = model or settings.OLLAMA_MODEL
        # Configurable via OLLAMA_TIMEOUT (.env). Défaut 600 s : une génération
        # 8B sur CPU peut dépasser largement 120 s (cf. perturbation J2 latence).
        self.timeout = timeout or settings.OLLAMA_TIMEOUT

    def generate_quiz(
        self,
        source_text: str,
        title: str,
        *,
        num_questions: int = 10,
        difficulty: str = "medium",
        theme: str = "",
    ) -> list[dict]:
        # Séparation system / user : /api/generate accepte un champ `system`
        # DISTINCT du `prompt` (contenu utilisateur). On isole ainsi les consignes
        # du contenu du cours — défense de base contre l'injection (J3).
        raw = self._call_ollama(
            system=SYSTEM_PROMPT,
            prompt=build_user_prompt(
                source_text,
                title,
                num_questions=num_questions,
                difficulty=difficulty,
                theme=theme,
            ),
            # Structured output : JSON SCHEMA pour CONTRAINDRE le modèle (4
            # options/question). Indispensable avec un petit modèle local.
            fmt=QUIZ_JSON_SCHEMA,
        )
        return parse_and_validate_quiz(raw, expected_count=num_questions)

    def generate_text(self, source_text: str, title: str, kind: str) -> str:
        # Génération de TEXTE libre : PAS de `format` JSON (contrairement au quiz).
        try:
            system = system_prompt_for(kind)
        except KeyError as exc:
            raise LLMError(f"kind inconnu : {kind!r} (attendu 'note' | 'summary').") from exc
        raw = self._call_ollama(
            system=system,
            prompt=build_study_user_prompt(source_text, title, kind),
            fmt=None,
        )
        return raw.strip()

    # ----- internals -----

    def _call_ollama(self, system: str, prompt: str, *, fmt: dict | None = None) -> str:
        payload = {
            "model": self.model,
            "system": system,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.4},  # peu de créativité : on veut du factuel
        }
        # `format` (JSON schema) UNIQUEMENT pour le quiz ; en texte libre on laisse
        # le modèle produire du markdown.
        if fmt is not None:
            payload["format"] = fmt
        try:
            response = requests.post(
                f"{self.host}/api/generate",
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise LLMError(f"Ollama injoignable : {exc}") from exc

        data = response.json()
        raw = data.get("response", "")
        if not raw:
            raise LLMError("Ollama a renvoyé une réponse vide.")
        return raw
