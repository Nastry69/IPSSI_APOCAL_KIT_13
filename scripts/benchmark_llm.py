#!/usr/bin/env python
"""
Benchmark des providers LLM — IPSSI_APOCAL_KIT_13.

Usage :
    python scripts/benchmark_llm.py
    python scripts/benchmark_llm.py --providers ollama groq mistral
    python scripts/benchmark_llm.py --runs 5 --output results/bench.json

Métriques par provider :
  - Latence  : moyenne / min / max (secondes)
  - JSON OK  : taux de réussite parse_and_validate_quiz (%)
  - Qualité  : score /10 sur 4 critères pondérés (pertinence, formulation,
               diversité lexicale, richesse des options)

Sorties :
  - Tableau coloré dans le terminal
  - <output>.json  (résultats bruts, tous les runs)
  - <output>.md    (tableau markdown prêt à coller dans l'ADR)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

# ── Django bootstrap ────────────────────────────────────────────────────────
BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "apocal.settings")

import django  # noqa: E402

django.setup()

# ── Imports projet (après django.setup) ─────────────────────────────────────
from django.conf import settings  # noqa: E402

from llm.services.base import LLMError  # noqa: E402
from llm.services.cerebras_client import CerebrasLLMClient  # noqa: E402
from llm.services.gemini_client import GeminiLLMClient  # noqa: E402
from llm.services.groq_client import GroqLLMClient  # noqa: E402
from llm.services.mistral_client import MistralLLMClient  # noqa: E402
from llm.services.ollama_client import OllamaLLMClient  # noqa: E402
from llm.services.quiz_prompt import parse_and_validate_quiz  # noqa: E402

# ── Corpus de test ───────────────────────────────────────────────────────────
# 3 textes académiques francophones, longueurs variées (~300 / ~900 / ~2500 cars)

CORPUS: list[dict[str, str]] = [
    {
        "title": "Modèle OSI (court)",
        "text": (
            "Le modèle OSI (Open Systems Interconnection) est un cadre conceptuel "
            "normalisé par l'ISO en 1984 pour décrire les fonctions d'un système de "
            "communication. Il est organisé en 7 couches : Physique, Liaison de données, "
            "Réseau, Transport, Session, Présentation et Application. Chaque couche "
            "communique uniquement avec les couches adjacentes via des interfaces définies. "
            "La couche Réseau (couche 3) gère l'adressage logique et le routage des paquets "
            "via des protocoles comme IP. La couche Transport (couche 4) assure la "
            "transmission fiable de bout en bout avec TCP ou la transmission rapide sans "
            "garantie avec UDP. Ce modèle sert de référence pour concevoir des protocoles "
            "interopérables indépendamment des implémentations matérielles."
        ),
    },
    {
        "title": "Sécurité des applications web (moyen)",
        "text": (
            "La sécurité des applications web repose sur la compréhension et la mitigation "
            "des vulnérabilités recensées par l'OWASP (Open Web Application Security Project). "
            "Parmi les risques les plus critiques figurent l'injection SQL, les failles XSS "
            "(Cross-Site Scripting) et la mauvaise configuration des accès. "
            "\n\nL'injection SQL consiste à insérer du code SQL malveillant dans une requête "
            "via un champ utilisateur non filtré, permettant à un attaquant de lire, modifier "
            "ou supprimer des données en base. La contre-mesure principale est l'utilisation "
            "de requêtes paramétrées (prepared statements). "
            "\n\nLe XSS injecte des scripts côté client dans des pages vues par d'autres "
            "utilisateurs. On distingue le XSS réfléchi (via URL), stocké (en base) et basé "
            "sur le DOM. Les défenses incluent l'encodage des sorties HTML et la politique "
            "CSP (Content Security Policy). "
            "\n\nLa gestion des authentifications est également critique : mots de passe hachés "
            "avec bcrypt ou Argon2, jetons JWT à durée de vie courte, mécanisme de rotation "
            "des tokens et implémentation du MFA (authentification multi-facteurs). "
            "\n\nLe principe du moindre privilège impose que chaque composant n'ait accès "
            "qu'aux ressources strictement nécessaires à son fonctionnement, limitant la "
            "surface d'attaque en cas de compromission."
        ),
    },
    {
        "title": "Bases de données relationnelles et normalisation (long)",
        "text": (
            "Les bases de données relationnelles organisent les données en tables (relations) "
            "composées de lignes (tuples) et de colonnes (attributs). Edgar F. Codd a posé "
            "les fondements théoriques en 1970 avec son modèle relationnel fondé sur l'algèbre "
            "relationnelle. Le langage SQL (Structured Query Language) est la norme de facto "
            "pour interroger et manipuler ces bases. "
            "\n\nLa normalisation est un processus de décomposition des tables pour éliminer "
            "la redondance et prévenir les anomalies de mise à jour. Elle s'appuie sur les "
            "formes normales : "
            "\n- Première forme normale (1NF) : chaque attribut contient une valeur atomique, "
            "sans répétition de groupes. "
            "\n- Deuxième forme normale (2NF) : 1NF + tout attribut non-clé dépend "
            "fonctionnellement de la clé primaire entière (pas d'une partie de clé composite). "
            "\n- Troisième forme normale (3NF) : 2NF + aucun attribut non-clé ne dépend "
            "transitivement d'un autre attribut non-clé. "
            "\n- Forme normale de Boyce-Codd (BCNF) : variante renforcée de la 3NF éliminant "
            "certaines anomalies résiduelles. "
            "\n\nLes transactions garantissent les propriétés ACID : Atomicité (tout ou rien), "
            "Cohérence (respect des contraintes d'intégrité), Isolation (transactions "
            "concurrentes sans interférence apparente) et Durabilité (données persistées même "
            "après une panne). Les niveaux d'isolation (READ UNCOMMITTED, READ COMMITTED, "
            "REPEATABLE READ, SERIALIZABLE) permettent de doser le compromis entre performance "
            "et cohérence. "
            "\n\nLes index accélèrent les lectures en maintenant une structure de données "
            "ordonnée (B-tree par défaut dans la plupart des SGBD). Leur coût est une "
            "dégradation des performances en écriture (INSERT, UPDATE, DELETE) due à la "
            "maintenance de l'index. Les index partiels et les index couvrants permettent "
            "d'affiner ce compromis. "
            "\n\nLe modèle entité-association (EA) sert à conceptualiser le schéma avant "
            "l'implémentation : les entités deviennent des tables, les associations se "
            "traduisent par des clés étrangères ou des tables de jonction (pour les "
            "cardinalités N:N). L'intégrité référentielle est garantie par les contraintes "
            "FOREIGN KEY avec les règles ON DELETE / ON UPDATE (CASCADE, SET NULL, RESTRICT)."
        ),
    },
]

# ── Configuration des providers à benchmarker ───────────────────────────────

ALL_PROVIDERS = ["ollama", "groq", "mistral", "gemini", "cerebras"]

# Couleurs ANSI (désactivées si le terminal ne les supporte pas)
_COLORS = sys.stdout.isatty()


def _c(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m" if _COLORS else text


GREEN = lambda t: _c("32", t)  # noqa: E731
RED = lambda t: _c("31", t)  # noqa: E731
YELLOW = lambda t: _c("33", t)  # noqa: E731
BOLD = lambda t: _c("1", t)  # noqa: E731
DIM = lambda t: _c("2", t)  # noqa: E731
CYAN = lambda t: _c("36", t)  # noqa: E731


# ── Instanciation des clients ────────────────────────────────────────────────

def build_client(provider: str):
    """Instancie le client LLM pour le provider donné (sans passer par la DB)."""
    if provider == "ollama":
        return OllamaLLMClient()

    key_map = {
        "groq": ("GROQ_API_KEY", "GROQ_MODEL", GroqLLMClient),
        "mistral": ("MISTRAL_API_KEY", "MISTRAL_MODEL", MistralLLMClient),
        "gemini": ("GEMINI_API_KEY", "GEMINI_MODEL", GeminiLLMClient),
        "cerebras": ("CEREBRAS_API_KEY", "CEREBRAS_MODEL", CerebrasLLMClient),
    }
    if provider not in key_map:
        raise ValueError(f"Provider inconnu pour le benchmark : {provider!r}")

    key_attr, model_attr, cls = key_map[provider]
    api_key = getattr(settings, key_attr, "")
    model = getattr(settings, model_attr, "") or None
    return cls(api_key=api_key, model=model, timeout=None)


# ── Scoring qualité ──────────────────────────────────────────────────────────

_INTERROGATIVE = {
    "quel", "quelle", "quels", "quelles", "qu", "comment",
    "pourquoi", "quand", "combien", "où", "lequel", "laquelle",
    "what", "which", "how", "why", "when", "where", "define", "explain",
}


def score_quality(questions: list[dict]) -> dict[str, float]:
    """
    Score qualité /10 sur 4 critères pondérés.

    Pertinence  (40%) — longueur moyenne des questions : proxy de spécificité.
                        Une question longue est généralement plus précise.
    Formulation (25%) — % de questions interrogatives (avec "?" ou mot interrogatif).
    Diversité   (20%) — diversité lexicale (mots uniques / mots totaux).
    Difficulté  (15%) — longueur moyenne des options : distracteurs courts = trop simples.
    """
    n = len(questions)
    if n == 0:
        return {"pertinence": 0, "formulation": 0, "diversite": 0, "difficulte": 0, "total": 0}

    # 1. Pertinence — 150 caractères moyens → 10/10
    avg_prompt_len = sum(len(q["prompt"]) for q in questions) / n
    pertinence = min(10.0, avg_prompt_len / 15.0)

    # 2. Formulation — question marquée interrogative
    def is_interrogative(q: dict) -> bool:
        p = q["prompt"].strip()
        first_word = p.lower().split()[0].rstrip("'\"") if p else ""
        return "?" in p or first_word in _INTERROGATIVE

    formulation = (sum(1 for q in questions if is_interrogative(q)) / n) * 10.0

    # 3. Diversité lexicale — ratio mots uniques / total
    all_words = " ".join(q["prompt"] for q in questions).lower().split()
    if all_words:
        lex_ratio = len(set(all_words)) / len(all_words)
        diversite = min(10.0, lex_ratio * 15.0)  # ratio 0.67 → 10/10
    else:
        diversite = 0.0

    # 4. Difficulté — longueur moyenne des options (50 chars → 10/10)
    avg_opt_len = sum(len(o) for q in questions for o in q["options"]) / (n * 4)
    difficulte = min(10.0, avg_opt_len / 5.0)

    total = (
        pertinence * 0.40
        + formulation * 0.25
        + diversite * 0.20
        + difficulte * 0.15
    )

    return {
        "pertinence": round(pertinence, 1),
        "formulation": round(formulation, 1),
        "diversite": round(diversite, 1),
        "difficulte": round(difficulte, 1),
        "total": round(total, 1),
    }


# ── Runner ───────────────────────────────────────────────────────────────────

def run_provider(provider: str, n_runs: int) -> dict[str, Any]:
    """Lance N runs (un par texte du corpus × répétitions) et agrège les résultats."""
    print(f"\n{BOLD(CYAN(f'▶  {provider.upper()}'))}")

    try:
        client = build_client(provider)
    except LLMError as exc:
        print(f"  {RED('✗')} Impossible d'instancier le client : {exc}")
        return {"provider": provider, "error": str(exc), "runs": []}

    runs: list[dict] = []

    for corpus_entry in CORPUS:
        for run_idx in range(n_runs):
            title = corpus_entry["title"]
            text = corpus_entry["text"]
            label = f"{title} (run {run_idx + 1}/{n_runs})"
            print(f"  {DIM('·')} {label} … ", end="", flush=True)

            t0 = time.perf_counter()
            try:
                questions = client.generate_quiz(text, title)
                latency = time.perf_counter() - t0
                quality = score_quality(questions)
                runs.append({
                    "corpus": title,
                    "run": run_idx + 1,
                    "success": True,
                    "latency_s": round(latency, 2),
                    "quality": quality,
                })
                q_str = GREEN(f"{quality['total']:.1f}/10")
                print(f"{GREEN('OK')}  {latency:.1f}s  qualité {q_str}")
            except (LLMError, Exception) as exc:
                latency = time.perf_counter() - t0
                runs.append({
                    "corpus": title,
                    "run": run_idx + 1,
                    "success": False,
                    "latency_s": round(latency, 2),
                    "error": str(exc),
                })
                print(f"{RED('FAIL')}  {latency:.1f}s  {RED(str(exc)[:80])}")

    return {"provider": provider, "runs": runs}


def aggregate(result: dict) -> dict[str, Any]:
    """Calcule les statistiques agrégées pour un provider."""
    runs = result.get("runs", [])
    successful = [r for r in runs if r["success"]]
    total = len(runs)
    ok = len(successful)

    if not successful:
        return {
            "provider": result["provider"],
            "total_runs": total,
            "success_rate_pct": 0,
            "latency_avg_s": None,
            "latency_min_s": None,
            "latency_max_s": None,
            "quality_avg": None,
            "error": result.get("error", "Tous les runs ont échoué"),
        }

    latencies = [r["latency_s"] for r in successful]
    qualities = [r["quality"]["total"] for r in successful]

    return {
        "provider": result["provider"],
        "total_runs": total,
        "success_rate_pct": round(ok / total * 100),
        "latency_avg_s": round(sum(latencies) / len(latencies), 1),
        "latency_min_s": round(min(latencies), 1),
        "latency_max_s": round(max(latencies), 1),
        "quality_avg": round(sum(qualities) / len(qualities), 1),
        "quality_detail": {
            k: round(sum(r["quality"][k] for r in successful) / len(successful), 1)
            for k in ("pertinence", "formulation", "diversite", "difficulte")
        },
    }


# ── Affichage terminal ───────────────────────────────────────────────────────

def print_summary(stats: list[dict]) -> None:
    col_w = [12, 10, 14, 14, 14, 12, 14]
    headers = ["Provider", "JSON OK", "Lat. moy.", "Lat. min", "Lat. max", "Qualité", "Pertinence"]

    sep = "─" * (sum(col_w) + len(col_w) * 3 + 1)
    print(f"\n{BOLD('═' * len(sep))}")
    print(BOLD("  RÉSULTATS BENCHMARK LLM"))
    print(BOLD("═" * len(sep)))

    row = "  ".join(BOLD(h.ljust(col_w[i])) for i, h in enumerate(headers))
    print(f"  {row}")
    print(f"  {sep}")

    for s in stats:
        p = s["provider"]
        if s.get("error") and s["success_rate_pct"] == 0:
            print(f"  {RED(p.ljust(col_w[0]))}  {RED('ERREUR — ' + s.get('error', '')[:60])}")
            continue

        ok_str = f"{s['success_rate_pct']}%"
        ok_colored = GREEN(ok_str) if s["success_rate_pct"] >= 80 else YELLOW(ok_str)

        lat = f"{s['latency_avg_s']}s"
        lat_colored = (
            GREEN(lat) if s["latency_avg_s"] < 10
            else YELLOW(lat) if s["latency_avg_s"] < 30
            else RED(lat)
        )

        q = s["quality_avg"]
        q_str = f"{q}/10"
        q_colored = (
            GREEN(q_str) if q >= 7
            else YELLOW(q_str) if q >= 5
            else RED(q_str)
        )

        pert = s.get("quality_detail", {}).get("pertinence", "-")

        row_vals = [
            p.ljust(col_w[0]),
            ok_colored.ljust(col_w[1] + (9 if _COLORS else 0)),
            lat_colored.ljust(col_w[2] + (9 if _COLORS else 0)),
            f"{s['latency_min_s']}s".ljust(col_w[3]),
            f"{s['latency_max_s']}s".ljust(col_w[4]),
            q_colored.ljust(col_w[5] + (9 if _COLORS else 0)),
            str(pert).ljust(col_w[6]),
        ]
        print("  " + "  ".join(row_vals))

    print(f"  {sep}\n")


# ── Export Markdown ──────────────────────────────────────────────────────────

RGPD_EU = {"ollama", "mistral"}


def to_markdown(stats: list[dict], providers: list[str], n_runs: int, corpus: list[dict]) -> str:
    lines = [
        "## Tableau comparatif — résultats benchmark",
        "",
        f"_Corpus : {len(corpus)} textes × {n_runs} run(s) par provider._",
        "",
        "| Provider | JSON OK | Lat. moy. | Lat. min | Lat. max | Qualité /10 | Pertinence | Formulation | Diversité | Difficulté | RGPD UE |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]

    for s in stats:
        if s.get("error") and s["success_rate_pct"] == 0:
            lines.append(f"| {s['provider']} | ERREUR | — | — | — | — | — | — | — | — | — |")
            continue
        d = s.get("quality_detail", {})
        rgpd = "✅" if s["provider"] in RGPD_EU else "❌"
        lines.append(
            f"| {s['provider']} "
            f"| {s['success_rate_pct']}% "
            f"| {s['latency_avg_s']}s "
            f"| {s['latency_min_s']}s "
            f"| {s['latency_max_s']}s "
            f"| {s['quality_avg']} "
            f"| {d.get('pertinence', '—')} "
            f"| {d.get('formulation', '—')} "
            f"| {d.get('diversite', '—')} "
            f"| {d.get('difficulte', '—')} "
            f"| {rgpd} |"
        )

    lines += [
        "",
        "**Grille qualité (score /10) :**",
        "| Critère | Poids | Mesure automatique |",
        "|---|---|---|",
        "| Pertinence | 40% | Longueur moyenne des questions (150 chars → 10/10) |",
        "| Formulation | 25% | % de questions interrogatives (« ? » ou mot interrogatif) |",
        "| Diversité | 20% | Ratio mots uniques / mots totaux (TTR lexical) |",
        "| Difficulté | 15% | Longueur moyenne des options (50 chars → 10/10) |",
        "",
    ]
    return "\n".join(lines)


# ── Main ─────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Benchmark LLM providers")
    parser.add_argument(
        "--providers", nargs="+", default=ALL_PROVIDERS,
        choices=ALL_PROVIDERS, metavar="PROVIDER",
        help=f"Providers à tester (défaut : {' '.join(ALL_PROVIDERS)})",
    )
    parser.add_argument(
        "--runs", type=int, default=1,
        help="Nombre de runs par texte du corpus (défaut : 1)",
    )
    parser.add_argument(
        "--output", default="benchmark_results",
        help="Préfixe des fichiers de sortie (.json et .md) — défaut : benchmark_results",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    print(BOLD("\n=== Benchmark LLM — IPSSI_APOCAL_KIT_13 ==="))
    print(f"Providers : {', '.join(args.providers)}")
    print(f"Corpus    : {len(CORPUS)} textes  ×  {args.runs} run(s)  =  "
          f"{len(CORPUS) * args.runs} appels / provider")
    print(f"Sortie    : {args.output}.json  |  {args.output}.md")

    raw_results = []
    for provider in args.providers:
        result = run_provider(provider, args.runs)
        raw_results.append(result)

    stats = [aggregate(r) for r in raw_results]
    stats.sort(key=lambda s: (-(s.get("quality_avg") or -1), s.get("latency_avg_s") or 9999))

    print_summary(stats)

    # Sauvegarde JSON
    json_path = Path(args.output).with_suffix(".json")
    json_path.parent.mkdir(parents=True, exist_ok=True)
    with json_path.open("w", encoding="utf-8") as f:
        json.dump({"stats": stats, "raw": raw_results}, f, ensure_ascii=False, indent=2)
    print(f"  JSON → {json_path}")

    # Sauvegarde Markdown
    md_path = Path(args.output).with_suffix(".md")
    md_content = to_markdown(stats, args.providers, args.runs, CORPUS)
    with md_path.open("w", encoding="utf-8") as f:
        f.write(md_content)
    print(f"  MD   → {md_path}\n")


if __name__ == "__main__":
    main()
