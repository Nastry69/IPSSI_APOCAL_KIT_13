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

    def generate_text(self, source_text: str, title: str, kind: str) -> str:
        """Génère un document de révision en TEXTE libre (markdown) — Release 2.

        Contrairement à `generate_quiz` (sortie JSON stricte), renvoie du texte
        libre selon le format demandé :
            - kind="note"    → fiche de révision concise (markdown)
            - kind="summary" → résumé structuré (markdown)

        Implémentation PAR DÉFAUT : lève une LLMError « non supporté ». Les
        clients qui savent produire du texte libre (mock, Ollama, base
        openai-compatible…) redéfinissent cette méthode. Les autres héritent de
        ce comportement et échouent clairement.

        Raises:
            LLMError: si le backend ne supporte pas la génération de texte, ou
                      si le LLM est indisponible.
        """
        raise LLMError(
            f"Le backend « {type(self).__name__} » ne supporte pas encore la "
            "génération de documents de révision (fiche / résumé). Utilisez "
            "LLM_BACKEND=ollama, mock, ou un fournisseur au format OpenAI."
        )


class LLMError(Exception):
    """Erreur générique côté LLM (indisponibilité, parsing, validation)."""
