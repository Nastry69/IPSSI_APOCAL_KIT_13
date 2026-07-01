"""
Factory de client LLM.

[Note pédagogique] Le « factory pattern » centralise le choix du fournisseur.
Le reste de l'application appelle get_llm_client() sans savoir lequel est branché.

Depuis le Lot 8, la configuration peut venir de DEUX sources, avec priorité :
1. La base de données (modèle LLMConfig), modifiable depuis l'interface d'admin.
2. À défaut, le fichier `.env` (settings).
=> « La base l'emporte si renseignée, sinon repli sur le .env. »

Le catalogue des fournisseurs (métadonnées + attributs settings de repli) est
décrit une seule fois dans llm/providers.py.
"""

import logging

from django.conf import settings

from ..providers import PROVIDERS
from .anthropic_client import AnthropicLLMClient
from .base import LLMClient, LLMError
from .cerebras_client import CerebrasLLMClient
from .gemini_client import GeminiLLMClient
from .groq_client import GroqLLMClient
from .mistral_client import MistralLLMClient
from .mock_client import MockLLMClient
from .ollama_client import OllamaLLMClient
from .openai_client import OpenAILLMClient
from .openrouter_client import OpenRouterLLMClient
from .quiz_prompt import QuizValidationError

logger = logging.getLogger(__name__)

# Backends CLOUD : les données du cours sortent du serveur local (enjeu RGPD,
# cf. perturbation J3-bis). Dérivé du registre des fournisseurs.
CLOUD_BACKENDS = {k for k, p in PROVIDERS.items() if p.cloud}
PAID_BACKENDS = {k for k, p in PROVIDERS.items() if p.paid}

_BACKENDS = {
    "mock": MockLLMClient,
    "ollama": OllamaLLMClient,
    "openai": OpenAILLMClient,
    "anthropic": AnthropicLLMClient,
    "gemini": GeminiLLMClient,
    "groq": GroqLLMClient,
    "openrouter": OpenRouterLLMClient,
    "cerebras": CerebrasLLMClient,
    "mistral": MistralLLMClient,
}

# Backends qui NE déclenchent JAMAIS de fallback quand ils sont le primaire :
#   - "mock"   : utilisé par les tests (déterministe, offline) — un fallback
#                casserait l'isolation des tests (@override_settings(LLM_BACKEND="mock")).
#   - "ollama" : backend LOCAL/souverain choisi volontairement ; on ne veut pas
#                faire fuiter les données vers un cloud de secours à son insu (RGPD).
_NO_FALLBACK_PRIMARY = {"mock", "ollama"}


class FallbackLLMClient(LLMClient):
    """Wrapper « filet de sécurité » : primaire d'abord, secours si échec.

    Délègue `generate_quiz` / `generate_text` au client PRIMAIRE. Si la
    génération échoue pour une raison d'INDISPONIBILITÉ (LLMError « réseau /
    quota / clé manquante » ou exception inattendue), on logue l'incident puis
    on RÉESSAIE une fois avec le client de SECOURS.

    Ce qui N'ENTRAÎNE PAS de bascule (on relaie tel quel au primaire) :
      - QuizValidationError : sortie mal formée. C'est un problème de QUALITÉ,
        pas de disponibilité ; la vue (GenerateQuizView) la rattrape déjà pour
        RE-TENTER sur le même backend (défense J3). Basculer ici casserait ce
        contrat de re-tentative.

    Le wrapper n'est construit QUE lorsqu'un secours distinct et configuré (clé
    présente) existe : voir get_llm_client(). Il ne modifie donc jamais le
    comportement en mode mock/ollama ni le contrat des méthodes.
    """

    def __init__(self, primary: LLMClient, backup: LLMClient, *, backup_name: str = "") -> None:
        self.primary = primary
        self.backup = backup
        self.backup_name = backup_name

    def _with_fallback(self, method_name: str, *args, **kwargs):
        try:
            return getattr(self.primary, method_name)(*args, **kwargs)
        except QuizValidationError:
            # Problème de QUALITÉ de sortie : NE PAS basculer (la vue re-tente).
            raise
        except Exception as exc:  # LLMError réseau/quota/clé, ou imprévu.
            logger.warning(
                "[LLM] Backend primaire (%s) en échec sur %s : %s. Bascule sur le "
                "backend de secours « %s ».",
                type(self.primary).__name__,
                method_name,
                exc,
                self.backup_name or type(self.backup).__name__,
            )
            try:
                return getattr(self.backup, method_name)(*args, **kwargs)
            except Exception as backup_exc:
                # Les DEUX ont échoué : on remonte une LLMError explicite qui
                # cite les deux incidents (la vue la transforme en 502).
                raise LLMError(
                    f"Backend primaire ET backend de secours "
                    f"« {self.backup_name or type(self.backup).__name__} » ont "
                    f"échoué. Primaire : {exc} | Secours : {backup_exc}"
                ) from backup_exc

    def generate_quiz(
        self,
        source_text: str,
        title: str,
        *,
        num_questions: int = 10,
        difficulty: str = "medium",
        theme: str = "",
    ) -> list[dict]:
        return self._with_fallback(
            "generate_quiz",
            source_text,
            title,
            num_questions=num_questions,
            difficulty=difficulty,
            theme=theme,
        )

    def generate_text(self, source_text: str, title: str, kind: str) -> str:
        return self._with_fallback("generate_text", source_text, title, kind)


def _resolve_config(cfg, backend: str) -> dict:
    """Construit le dict de config effective pour UN backend donné.

    Applique la règle « base prioritaire, repli .env » du projet : le modèle et
    la clé viennent d'abord de LLMConfig (base), sinon des settings (.env). Les
    clés `api_keys` de la base sont indexées par nom de backend, ce qui permet de
    résoudre AUSSI la config du backend de secours à partir du même LLMConfig.
    """
    prov = PROVIDERS.get(backend)

    model, api_key = "", ""
    if prov is not None:
        # Modèle : valeur en base sinon défaut .env du fournisseur.
        if prov.settings_model_attr:
            # Le modèle en base ne s'applique QU'au backend primaire choisi en
            # base ; pour tout autre backend (ex. secours), on prend le défaut .env.
            base_model = cfg.model if backend == (cfg.backend or "").lower() else ""
            model = base_model or getattr(settings, prov.settings_model_attr, "")
        # Clé : valeur en base sinon défaut .env (uniquement si le fournisseur en a besoin).
        if prov.needs_key and prov.settings_key_attr:
            api_key = (cfg.api_keys or {}).get(backend) or getattr(
                settings, prov.settings_key_attr, ""
            )

    return {
        "backend": backend,
        "model": model,
        "api_key": api_key,
        "ollama_host": cfg.ollama_host or "",
        "timeout": cfg.timeout or None,
    }


def resolve_active() -> dict:
    """Résout la config LLM effective (base prioritaire, repli .env).

    Renvoie un dict : { backend, model, api_key, ollama_host, timeout }.
    Import local de LLMConfig pour éviter les soucis d'ordre de chargement.
    """
    from ..models import LLMConfig

    cfg = LLMConfig.load()
    backend = (cfg.backend or settings.LLM_BACKEND or "ollama").lower()
    return _resolve_config(cfg, backend)


def resolve_fallback() -> dict | None:
    """Résout la config du backend de SECOURS, ou None si pas de fallback.

    Renvoie None (=> pas de wrapper de fallback) dès qu'une de ces conditions
    n'est pas remplie :
      - le backend primaire est "mock" ou "ollama" (voir _NO_FALLBACK_PRIMARY) ;
      - LLM_FALLBACK_BACKEND est vide, inconnu, ou identique au primaire ;
      - le backend de secours requiert une clé API et n'en a pas (dev sans clé)
        -> pas de fallback, l'erreur primaire remontera telle quelle.
    """
    from ..models import LLMConfig

    cfg = LLMConfig.load()
    primary = (cfg.backend or settings.LLM_BACKEND or "ollama").lower()
    if primary in _NO_FALLBACK_PRIMARY:
        return None

    fallback = (getattr(settings, "LLM_FALLBACK_BACKEND", "") or "").lower()
    if not fallback or fallback == primary or fallback not in _BACKENDS:
        return None

    conf = _resolve_config(cfg, fallback)
    prov = PROVIDERS.get(fallback)
    # Secours nécessitant une clé mais sans clé configurée -> on ne l'active pas.
    if prov is not None and prov.needs_key and not conf["api_key"]:
        return None
    return conf


def effective_backend() -> str:
    """Renvoie le nom du backend actif (utile pour /ping)."""
    return resolve_active()["backend"]


def _build_client(conf: dict) -> LLMClient:
    """Instancie un client BRUT (sans fallback) à partir d'une config résolue."""
    backend = conf["backend"]

    if backend in CLOUD_BACKENDS:
        # Garde-fou pédagogique (on N'INTERROMPT PAS, c'est un choix assumé).
        cout = "PAYANT (crédit requis)" if backend in PAID_BACKENDS else "free tier disponible"
        logger.warning(
            "[LLM] Backend CLOUD activé : '%s' (%s). Les données du cours quittent "
            "le serveur local (enjeu RGPD, cf. perturbation J3-bis). En développement, "
            "préférez Ollama (local, gratuit, souverain).",
            backend,
            cout,
        )

    client_cls = _BACKENDS.get(backend)
    if client_cls is None:
        raise ValueError(
            f"LLM_BACKEND inconnu : '{backend}'. Valeurs autorisées : "
            + " | ".join(f"'{k}'" for k in _BACKENDS)
        )

    model = conf["model"] or None
    timeout = conf["timeout"]

    if backend == "mock":
        return MockLLMClient()
    if backend == "ollama":
        return OllamaLLMClient(model=model, host=conf["ollama_host"] or None, timeout=timeout)
    if backend in ("gemini", "anthropic"):
        return client_cls(api_key=conf["api_key"], model=model, timeout=timeout)
    # Fournisseurs au format OpenAI (openai, groq, cerebras, mistral, openrouter)
    return client_cls(api_key=conf["api_key"], model=model, timeout=timeout)


def get_llm_client() -> LLMClient:
    """Renvoie le client LLM correspondant à la configuration effective.

    Si un backend de SECOURS est configuré et applicable (voir resolve_fallback),
    le client primaire est enveloppé dans un FallbackLLMClient : en cas d'échec
    RÉEL de génération (indisponibilité, quota, clé manquante), la génération est
    automatiquement re-tentée sur le secours. En mode mock/ollama, ou sans
    secours valide, on renvoie le client primaire NU (comportement inchangé).
    """
    primary_conf = resolve_active()
    fallback_conf = resolve_fallback()

    # Pas de secours applicable (mock/ollama, non configuré, sans clé…) :
    # comportement historique strictement inchangé.
    if fallback_conf is None:
        return _build_client(primary_conf)

    # Construction du primaire. Si le PRIMAIRE échoue dès l'instanciation (ex.
    # clé manquante -> LLMError levée dans __init__), on bascule immédiatement
    # sur le secours seul plutôt que de faire échouer tout get_llm_client().
    try:
        primary = _build_client(primary_conf)
    except LLMError as exc:
        logger.warning(
            "[LLM] Backend primaire « %s » non instanciable (%s) — utilisation "
            "directe du backend de secours « %s ».",
            primary_conf["backend"],
            exc,
            fallback_conf["backend"],
        )
        return _build_client(fallback_conf)

    backup = _build_client(fallback_conf)
    return FallbackLLMClient(primary, backup, backup_name=fallback_conf["backend"])
