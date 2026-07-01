"""Interface abstraite pour un client LLM générateur de quiz."""

from abc import ABC, abstractmethod


class LLMClient(ABC):
    """Interface commune à Ollama / Mock / autres backends futurs.

    Le contrat : `generate_quiz` reçoit un texte source et renvoie une liste
    de 10 dicts (prompt, options[4], correct_index) — structure validée par
    le générateur en amont du save en DB.
    """

    @abstractmethod
    def generate_quiz(
        self,
        source_text: str,
        title: str,
        *,
        num_questions: int = 10,
        difficulty: str = "medium",
        theme: str = "",
    ) -> list[dict]:
        """Renvoie `num_questions` questions QCM générées à partir du texte source.

        Args:
            num_questions: nombre de questions attendu (5 à 20).
            difficulty: niveau demandé ("easy" | "medium" | "hard").
            theme: thème/chapitre à cibler (optionnel).

        Raises:
            LLMError: si le LLM est indisponible, lent, ou renvoie une
                      structure invalide qui ne peut être réparée.
        """
        raise NotImplementedError


class LLMError(Exception):
    """Erreur générique côté LLM (indisponibilité, parsing, validation)."""
