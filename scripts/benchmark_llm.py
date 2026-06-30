#!/usr/bin/env python
"""
Benchmark des providers LLM — IPSSI_APOCAL_KIT_13.

Script STANDALONE : ne nécessite ni Django, ni Docker, ni .env.
Les clés API sont lues depuis les variables d'environnement.

Usage :
    # Tous les providers configurés
    python scripts/benchmark_llm.py

    # Sélection + plusieurs runs par texte
    python scripts/benchmark_llm.py --providers groq mistral --runs 3

    # Passer les clés directement (PowerShell)
    $env:GROQ_API_KEY="gsk_..."; python scripts/benchmark_llm.py --providers groq

Sorties :
    - Tableau coloré dans le terminal
    - benchmark_results.json  (résultats bruts)
    - benchmark_results.md    (tableau prêt à coller dans l'ADR)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

try:
    import requests
except ImportError:
    print("ERREUR : installe requests d'abord →  python -m pip install requests")
    sys.exit(1)

# ── Prompt système (identique à quiz_prompt.py) ──────────────────────────────

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

QUIZ_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "questions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "prompt": {"type": "string"},
                    "options": {
                        "type": "array",
                        "items": {"type": "string"},
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

MAX_SOURCE_CHARS = 8000


def build_user_prompt(source_text: str, title: str) -> str:
    truncated = source_text[:MAX_SOURCE_CHARS]
    return f"TITRE DU COURS : {title}\n\nCOURS :\n{truncated}\n\nGÉNÈRE LE JSON MAINTENANT :"


# ── Validation (identique à parse_and_validate_quiz) ─────────────────────────

class LLMError(Exception):
    pass


def parse_and_validate_quiz(raw: str) -> list[dict]:
    if not raw or not raw.strip():
        raise LLMError("Réponse vide.")
    data = None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", raw)
        if not match:
            raise LLMError("Aucun bloc JSON trouvé.")
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError as exc:
            raise LLMError(f"JSON invalide : {exc}") from exc

    if not isinstance(data, dict) or "questions" not in data:
        raise LLMError("Clé 'questions' absente.")
    questions = data["questions"]
    if not isinstance(questions, list):
        raise LLMError("'questions' n'est pas une liste.")
    if len(questions) > 10:
        questions = questions[:10]
    elif len(questions) < 10:
        raise LLMError(f"Seulement {len(questions)} questions (10 attendues).")

    cleaned = []
    for i, q in enumerate(questions, 1):
        p, opts, ci = q.get("prompt"), q.get("options"), q.get("correct_index")
        if not isinstance(p, str) or not p.strip():
            raise LLMError(f"Q{i} : prompt manquant.")
        if not isinstance(opts, list) or len(opts) != 4:
            raise LLMError(f"Q{i} : il faut exactement 4 options.")
        if not all(isinstance(o, str) and o.strip() for o in opts):
            raise LLMError(f"Q{i} : options invalides.")
        if not isinstance(ci, int) or ci not in (0, 1, 2, 3):
            raise LLMError(f"Q{i} : correct_index invalide.")
        cleaned.append({"prompt": p.strip(), "options": [o.strip() for o in opts], "correct_index": ci})
    return cleaned


# ── Clients HTTP directs ──────────────────────────────────────────────────────

def _call_ollama(source_text: str, title: str, cfg: dict) -> list[dict]:
    host = cfg.get("host", "http://localhost:11434").rstrip("/")
    prompt = f"{SYSTEM_PROMPT}\n\n{build_user_prompt(source_text, title)}"
    resp = requests.post(
        f"{host}/api/generate",
        json={"model": cfg["model"], "prompt": prompt, "stream": False,
              "options": {"temperature": 0.4}, "format": QUIZ_JSON_SCHEMA},
        timeout=cfg.get("timeout", 120),
    )
    resp.raise_for_status()
    raw = resp.json().get("response", "")
    if not raw:
        raise LLMError("Ollama : réponse vide.")
    return parse_and_validate_quiz(raw)


def _call_openai_compat(source_text: str, title: str, cfg: dict) -> list[dict]:
    headers = {"Authorization": f"Bearer {cfg['api_key']}", "Content-Type": "application/json"}
    if cfg.get("extra_headers"):
        headers.update(cfg["extra_headers"])
    payload: dict[str, Any] = {
        "model": cfg["model"],
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_user_prompt(source_text, title)},
        ],
        "temperature": 0.4,
    }
    if cfg.get("json_mode", True):
        payload["response_format"] = {"type": "json_object"}
    resp = requests.post(
        f"{cfg['base_url'].rstrip('/')}/chat/completions",
        headers=headers, json=payload,
        timeout=cfg.get("timeout", 60),
    )
    resp.raise_for_status()
    try:
        return parse_and_validate_quiz(resp.json()["choices"][0]["message"]["content"])
    except (KeyError, IndexError) as exc:
        raise LLMError(f"Réponse inattendue : {exc}") from exc


def _call_gemini(source_text: str, title: str, cfg: dict) -> list[dict]:
    # Pause pour respecter le rate limit du free tier Gemini (15 req/min)
    time.sleep(cfg.get("delay_s", 6))
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{cfg['model']}:generateContent?key={cfg['api_key']}"
    )
    prompt = f"{SYSTEM_PROMPT}\n\n{build_user_prompt(source_text, title)}"
    resp = requests.post(
        url,
        json={"contents": [{"parts": [{"text": prompt}]}],
              "generationConfig": {"temperature": 0.4}},
        timeout=cfg.get("timeout", 60),
    )
    resp.raise_for_status()
    try:
        raw = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError) as exc:
        raise LLMError(f"Réponse Gemini inattendue : {exc}") from exc
    return parse_and_validate_quiz(raw)


# ── Config des providers ──────────────────────────────────────────────────────

def get_provider_configs() -> dict[str, dict]:
    e = os.environ.get
    return {
        "ollama": {
            "label": "Ollama (llama3.1:8b)",
            "rgpd_eu": True,
            "call": _call_ollama,
            "cfg": {
                "host": e("OLLAMA_HOST", "http://localhost:11434"),
                "model": e("OLLAMA_MODEL", "llama3.1:8b"),
                "timeout": int(e("OLLAMA_TIMEOUT", "120")),
            },
        },
        "groq": {
            "label": f"Groq ({e('GROQ_MODEL','llama-3.3-70b-versatile')})",
            "rgpd_eu": False,
            "call": _call_openai_compat,
            "cfg": {
                "api_key": e("GROQ_API_KEY", ""),
                "base_url": "https://api.groq.com/openai/v1",
                "model": e("GROQ_MODEL", "llama-3.3-70b-versatile"),
                "json_mode": True,
                "timeout": int(e("LLM_API_TIMEOUT", "60")),
            },
        },
        "mistral": {
            "label": f"Mistral ({e('MISTRAL_MODEL','mistral-small-latest')})",
            "rgpd_eu": True,
            "call": _call_openai_compat,
            "cfg": {
                "api_key": e("MISTRAL_API_KEY", ""),
                "base_url": "https://api.mistral.ai/v1",
                "model": e("MISTRAL_MODEL", "mistral-small-latest"),
                "json_mode": True,
                "timeout": int(e("LLM_API_TIMEOUT", "60")),
            },
        },
        "gemini": {
            "label": f"Gemini ({e('GEMINI_MODEL','gemini-2.5-flash')})",
            "rgpd_eu": False,
            "call": _call_gemini,
            "cfg": {
                "api_key": e("GEMINI_API_KEY", ""),
                "model": e("GEMINI_MODEL", "gemini-2.5-flash"),
                "timeout": int(e("LLM_API_TIMEOUT", "60")),
                "delay_s": 6,
            },
        },
        "cerebras": {
            "label": f"Cerebras ({e('CEREBRAS_MODEL','llama-3.3-70b')})",
            "rgpd_eu": False,
            "call": _call_openai_compat,
            "cfg": {
                "api_key": e("CEREBRAS_API_KEY", ""),
                "base_url": "https://api.cerebras.ai/v1",
                "model": e("CEREBRAS_MODEL", "llama-3.3-70b"),
                "json_mode": False,
                "timeout": int(e("LLM_API_TIMEOUT", "60")),
            },
        },
    }


ALL_PROVIDERS = ["ollama", "groq", "mistral", "gemini", "cerebras"]

# ── Corpus de test ───────────────────────────────────────────────────────────

CORPUS: list[dict[str, str]] = [
    {
        "title": "Modèle OSI (court ~500 cars)",
        "text": (
            "Le modèle OSI (Open Systems Interconnection) est un cadre conceptuel normalisé "
            "par l'ISO en 1984 pour décrire les fonctions d'un système de communication. "
            "Il est organisé en 7 couches : Physique, Liaison de données, Réseau, Transport, "
            "Session, Présentation et Application. Chaque couche communique uniquement avec "
            "les couches adjacentes via des interfaces définies. La couche Réseau (couche 3) "
            "gère l'adressage logique et le routage des paquets via des protocoles comme IP. "
            "La couche Transport (couche 4) assure la transmission fiable de bout en bout "
            "avec TCP ou la transmission rapide sans garantie avec UDP. Ce modèle sert de "
            "référence pour concevoir des protocoles interopérables indépendamment des "
            "implémentations matérielles."
        ),
    },
    {
        "title": "Sécurité des applications web (moyen ~1100 cars)",
        "text": (
            "La sécurité des applications web repose sur la compréhension et la mitigation "
            "des vulnérabilités recensées par l'OWASP. Parmi les risques les plus critiques "
            "figurent l'injection SQL, les failles XSS (Cross-Site Scripting) et la mauvaise "
            "configuration des accès.\n\nL'injection SQL consiste à insérer du code SQL "
            "malveillant dans une requête via un champ utilisateur non filtré, permettant à "
            "un attaquant de lire, modifier ou supprimer des données en base. La contre-mesure "
            "principale est l'utilisation de requêtes paramétrées (prepared statements).\n\n"
            "Le XSS injecte des scripts côté client dans des pages vues par d'autres "
            "utilisateurs. On distingue le XSS réfléchi (via URL), stocké (en base) et basé "
            "sur le DOM. Les défenses incluent l'encodage des sorties HTML et la politique "
            "CSP (Content Security Policy).\n\nLa gestion des authentifications est également "
            "critique : mots de passe hachés avec bcrypt ou Argon2, jetons JWT à durée de vie "
            "courte, mécanisme de rotation des tokens et implémentation du MFA. Le principe du "
            "moindre privilège impose que chaque composant n'ait accès qu'aux ressources "
            "strictement nécessaires à son fonctionnement."
        ),
    },
    {
        "title": "Bases de données relationnelles et normalisation (long ~2200 cars)",
        "text": (
            "Les bases de données relationnelles organisent les données en tables (relations) "
            "composées de lignes (tuples) et de colonnes (attributs). Edgar F. Codd a posé "
            "les fondements théoriques en 1970 avec son modèle relationnel fondé sur l'algèbre "
            "relationnelle. Le langage SQL est la norme de facto pour interroger et manipuler "
            "ces bases.\n\nLa normalisation est un processus de décomposition des tables pour "
            "éliminer la redondance et prévenir les anomalies de mise à jour :\n"
            "- 1NF : chaque attribut contient une valeur atomique, sans répétition de groupes.\n"
            "- 2NF : 1NF + tout attribut non-clé dépend fonctionnellement de la clé entière.\n"
            "- 3NF : 2NF + aucun attribut non-clé ne dépend transitivement d'un autre.\n"
            "- BCNF : variante renforcée de la 3NF éliminant certaines anomalies résiduelles.\n\n"
            "Les transactions garantissent les propriétés ACID : Atomicité (tout ou rien), "
            "Cohérence (respect des contraintes), Isolation (transactions sans interférence "
            "apparente) et Durabilité (données persistées même après une panne). Les niveaux "
            "d'isolation (READ UNCOMMITTED, READ COMMITTED, REPEATABLE READ, SERIALIZABLE) "
            "permettent de doser le compromis entre performance et cohérence.\n\n"
            "Les index accélèrent les lectures en maintenant une structure B-tree. Leur coût "
            "est une dégradation des performances en écriture due à la maintenance de l'index. "
            "Le modèle entité-association (EA) sert à conceptualiser le schéma avant "
            "l'implémentation : les entités deviennent des tables, les associations se "
            "traduisent par des clés étrangères ou des tables de jonction pour les N:N. "
            "L'intégrité référentielle est garantie par les contraintes FOREIGN KEY avec "
            "ON DELETE / ON UPDATE (CASCADE, SET NULL, RESTRICT)."
        ),
    },
]

# ── Couleurs ANSI ─────────────────────────────────────────────────────────────

_TTY = sys.stdout.isatty()


def _c(code: str, t: str) -> str:
    return f"\033[{code}m{t}\033[0m" if _TTY else t


def GREEN(t: str) -> str: return _c("32", t)
def RED(t: str) -> str:   return _c("31", t)
def YELLOW(t: str) -> str: return _c("33", t)
def BOLD(t: str) -> str:  return _c("1", t)
def DIM(t: str) -> str:   return _c("2", t)
def CYAN(t: str) -> str:  return _c("36", t)


# ── Scoring qualité ───────────────────────────────────────────────────────────

_INTERRO = {
    "quel", "quelle", "quels", "quelles", "qu", "comment", "pourquoi",
    "quand", "combien", "où", "lequel", "laquelle", "what", "which",
    "how", "why", "when", "where",
}


def score_quality(questions: list[dict]) -> dict[str, float]:
    n = len(questions)
    if n == 0:
        return {"pertinence": 0.0, "formulation": 0.0, "diversite": 0.0,
                "difficulte": 0.0, "total": 0.0}

    # Pertinence (40%) — longueur moyenne des questions (150 chars → 10)
    avg_len = sum(len(q["prompt"]) for q in questions) / n
    pertinence = min(10.0, avg_len / 15.0)

    # Formulation (25%) — % de questions interrogatives
    def is_interro(q: dict) -> bool:
        p = q["prompt"].strip()
        first = p.lower().split()[0].rstrip("'\"") if p else ""
        return "?" in p or first in _INTERRO

    formulation = (sum(1 for q in questions if is_interro(q)) / n) * 10.0

    # Diversité (20%) — TTR lexical sur les prompts
    words = " ".join(q["prompt"] for q in questions).lower().split()
    diversite = min(10.0, (len(set(words)) / len(words)) * 15.0) if words else 0.0

    # Difficulté (15%) — longueur moyenne des options (50 chars → 10)
    avg_opt = sum(len(o) for q in questions for o in q["options"]) / (n * 4)
    difficulte = min(10.0, avg_opt / 5.0)

    total = pertinence * 0.40 + formulation * 0.25 + diversite * 0.20 + difficulte * 0.15
    return {
        "pertinence": round(pertinence, 1),
        "formulation": round(formulation, 1),
        "diversite": round(diversite, 1),
        "difficulte": round(difficulte, 1),
        "total": round(total, 1),
    }


# ── Runner ────────────────────────────────────────────────────────────────────

def run_provider(provider_key: str, configs: dict, n_runs: int) -> dict[str, Any]:
    prov = configs[provider_key]
    label = prov["label"]
    call_fn = prov["call"]
    cfg = prov["cfg"]

    print(f"\n{BOLD(CYAN(f'>> {label}'))}")

    # Vérification clé API
    if "api_key" in cfg and not cfg["api_key"]:
        msg = f"Clé API manquante — définissez {provider_key.upper()}_API_KEY"
        print(f"  {RED('✗')} {msg}")
        return {"provider": provider_key, "label": label, "error": msg, "runs": []}

    runs: list[dict] = []
    for entry in CORPUS:
        for run_idx in range(n_runs):
            title, text = entry["title"], entry["text"]
            print(f"  - {title} (run {run_idx + 1}/{n_runs}) ... ", end="", flush=True)
            t0 = time.perf_counter()
            try:
                questions = call_fn(text, title, cfg)
                latency = time.perf_counter() - t0
                quality = score_quality(questions)
                runs.append({"corpus": title, "run": run_idx + 1,
                             "success": True, "latency_s": round(latency, 2),
                             "quality": quality})
                print(f"{GREEN('OK')}  {latency:.1f}s  qualité {GREEN(str(quality['total'])+'/ 10')}")
            except Exception as exc:
                latency = time.perf_counter() - t0
                runs.append({"corpus": title, "run": run_idx + 1,
                             "success": False, "latency_s": round(latency, 2),
                             "error": str(exc)})
                print(f"{RED('FAIL')}  {latency:.1f}s  {RED(str(exc)[:90])}")

    return {"provider": provider_key, "label": label,
            "rgpd_eu": prov["rgpd_eu"], "runs": runs}


def aggregate(result: dict) -> dict[str, Any]:
    runs = result.get("runs", [])
    ok_runs = [r for r in runs if r["success"]]
    total = len(runs)
    n_ok = len(ok_runs)

    base = {
        "provider": result["provider"],
        "label": result["label"],
        "rgpd_eu": result.get("rgpd_eu", False),
        "total_runs": total,
        "success_rate_pct": round(n_ok / total * 100) if total else 0,
    }

    if not ok_runs:
        return {**base, "latency_avg_s": None, "latency_min_s": None,
                "latency_max_s": None, "quality_avg": None, "quality_detail": None,
                "error": result.get("error", "Tous les runs ont échoué")}

    lats = [r["latency_s"] for r in ok_runs]
    quals = [r["quality"]["total"] for r in ok_runs]
    detail_keys = ("pertinence", "formulation", "diversite", "difficulte")
    return {
        **base,
        "latency_avg_s": round(sum(lats) / len(lats), 1),
        "latency_min_s": round(min(lats), 1),
        "latency_max_s": round(max(lats), 1),
        "quality_avg": round(sum(quals) / len(quals), 1),
        "quality_detail": {
            k: round(sum(r["quality"][k] for r in ok_runs) / len(ok_runs), 1)
            for k in detail_keys
        },
    }


# ── Affichage terminal ────────────────────────────────────────────────────────

def print_summary(stats: list[dict]) -> None:
    sep = "-" * 90
    print(f"\n{BOLD('=' * 90)}")
    print(BOLD("  RESULTATS BENCHMARK LLM"))
    print(BOLD("=" * 90))
    headers = f"  {'Provider':<26}  {'JSON OK':>7}  {'Lat.moy':>8}  {'Lat.min':>7}  {'Lat.max':>7}  {'Qualité':>8}  {'RGPD':>5}"
    print(BOLD(headers))
    print(f"  {sep}")

    for s in stats:
        if not s.get("total_runs") or (s.get("error") and not s.get("quality_avg")):
            print(f"  {RED(s['label'][:26]):<26}  {RED('ERREUR'):>7}  {'—':>8}  {'—':>7}  {'—':>7}  {'—':>8}  {'—':>5}")
            if s.get("error"):
                print(f"    {DIM(s['error'][:80])}")
            continue

        ok_pct = s["success_rate_pct"]
        ok_str = f"{ok_pct}%"
        ok_col = GREEN(ok_str) if ok_pct >= 80 else YELLOW(ok_str) if ok_pct >= 50 else RED(ok_str)

        lat = s["latency_avg_s"]
        lat_str = f"{lat}s"
        lat_col = GREEN(lat_str) if lat < 10 else YELLOW(lat_str) if lat < 30 else RED(lat_str)

        q = s["quality_avg"]
        q_str = f"{q}/10"
        q_col = GREEN(q_str) if q >= 7 else YELLOW(q_str) if q >= 5 else RED(q_str)

        rgpd = "EU oui" if s["rgpd_eu"] else "non"

        print(
            f"  {s['label'][:26]:<26}  {ok_col:>7}  {lat_col:>8}  "
            f"{s['latency_min_s']}s{'':<4}  {s['latency_max_s']}s{'':<4}  "
            f"{q_col:>8}  {rgpd:>5}"
        )
    print(f"  {sep}\n")


# ── Export Markdown ───────────────────────────────────────────────────────────

def to_markdown(stats: list[dict], n_runs: int) -> str:
    lines = [
        "## Tableau comparatif — résultats benchmark",
        "",
        f"_Corpus : {len(CORPUS)} textes × {n_runs} run(s) par provider._",
        "",
        "| Provider | Modèle | JSON OK | Lat. moy. | Lat. min | Lat. max | Qualité /10 | Pertinence | Formulation | Diversité | Difficulté | RGPD UE |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for s in stats:
        model = s["label"].split("(")[-1].rstrip(")") if "(" in s["label"] else "—"
        provider = s["label"].split("(")[0].strip()
        if not s.get("total_runs") or (s.get("error") and not s.get("quality_avg")):
            err = s.get("error", "Erreur")[:60]
            lines.append(f"| {provider} | {model} | ERREUR — {err} | — | — | — | — | — | — | — | — | — |")
            continue
        d = s.get("quality_detail") or {}
        rgpd = "✅ (UE)" if s["rgpd_eu"] else "❌"
        lines.append(
            f"| {provider} | {model} "
            f"| {s['success_rate_pct']}% "
            f"| {s['latency_avg_s']}s "
            f"| {s['latency_min_s']}s "
            f"| {s['latency_max_s']}s "
            f"| **{s['quality_avg']}** "
            f"| {d.get('pertinence','—')} "
            f"| {d.get('formulation','—')} "
            f"| {d.get('diversite','—')} "
            f"| {d.get('difficulte','—')} "
            f"| {rgpd} |"
        )
    lines += [
        "",
        "**Grille qualité (score /10) :**",
        "| Critère | Poids | Mesure automatique |",
        "|---|---|---|",
        "| Pertinence | 40 % | Longueur moyenne des questions (150 chars → 10/10) |",
        "| Formulation | 25 % | % de questions interrogatives (« ? » ou mot interrogatif) |",
        "| Diversité lexicale | 20 % | TTR : ratio mots uniques / mots totaux |",
        "| Difficulté options | 15 % | Longueur moyenne des options (50 chars → 10/10) |",
    ]
    return "\n".join(lines)


# ── Main ──────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Benchmark LLM providers — IPSSI_APOCAL_KIT_13")
    p.add_argument("--providers", nargs="+", default=ALL_PROVIDERS,
                   choices=ALL_PROVIDERS, metavar="PROVIDER",
                   help=f"Providers à tester (défaut : tous)")
    p.add_argument("--runs", type=int, default=1,
                   help="Runs par texte du corpus (défaut : 1)")
    p.add_argument("--output", default="benchmark_results",
                   help="Préfixe des fichiers de sortie (défaut : benchmark_results)")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    configs = get_provider_configs()

    print(BOLD("\n=== Benchmark LLM - IPSSI_APOCAL_KIT_13 ==="))
    print(f"Providers : {', '.join(args.providers)}")
    print(f"Corpus    : {len(CORPUS)} textes × {args.runs} run(s) = "
          f"{len(CORPUS) * args.runs} appels/provider")
    print(f"Sortie    : {args.output}.json  |  {args.output}.md")

    raw_results = []
    for provider_key in args.providers:
        result = run_provider(provider_key, configs, args.runs)
        raw_results.append(result)

    stats = [aggregate(r) for r in raw_results]
    stats.sort(key=lambda s: (-(s.get("quality_avg") or -1), s.get("latency_avg_s") or 9999))

    print_summary(stats)

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)

    json_path = out.with_suffix(".json")
    with json_path.open("w", encoding="utf-8") as f:
        json.dump({"stats": stats, "raw": raw_results,
                   "corpus": [c["title"] for c in CORPUS],
                   "runs_per_corpus": args.runs}, f, ensure_ascii=False, indent=2)
    print(f"JSON → {json_path}")

    md_path = out.with_suffix(".md")
    with md_path.open("w", encoding="utf-8") as f:
        f.write(to_markdown(stats, args.runs))
    print(f"MD   → {md_path}\n")


if __name__ == "__main__":
    main()