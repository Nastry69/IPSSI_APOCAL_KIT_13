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
from .quiz_prompt import QUIZ_JSON_SCHEMA, generate_quiz_robust


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

    def generate_quiz(self, source_text: str, title: str) -> list[dict]:
        # Boucle de génération robuste mutualisée (perturbation J4 « qualité ») :
        # récupère les questions valides et ne régénère QUE le manque jusqu'à 10.
        # Le seul morceau spécifique à Ollama est l'appel brut `_complete`.
        return generate_quiz_robust(self._complete, source_text, title)

    # ----- internals -----

    def _complete(self, system: str, user: str) -> str:
        """Exécute UN appel Ollama et renvoie le texte brut de la réponse.

        Ollama /api/generate attend UN prompt unique (pas de séparation
        system/user) : on concatène donc les deux.
        """
        prompt = f"{system}\n\n{user}"
        try:
            response = requests.post(
                f"{self.host}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.4},  # peu de créativité : on veut du factuel
                    # « Structured output » (Ollama ≥ 0.5.0) : le modèle est
                    # CONTRAINT au schéma, ce qui supprime à la source l'essentiel
                    # des sorties mal formées (≠ 4 options, correct_index hors bornes).
                    "format": QUIZ_JSON_SCHEMA,
                },
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
