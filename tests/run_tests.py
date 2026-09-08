"""
run_tests.py

Livrable Phase 4 : execute le jeu de descriptions de test a travers le
pipeline complet (generation + validation sandbox) et produit :
  - un rapport detaille (tests/report.csv)
  - le taux de reussite global et par pattern (affiche en console)

Usage :
    python run_tests.py

Necessite ANTHROPIC_API_KEY, N8N_API_URL, N8N_API_KEY dans l'environnement.
"""

import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))
from agent.generate import generate_workflow, GenerationError
from validation.validate import validate_workflow

TEST_FILE = Path(__file__).parent / "test_descriptions.json"
REPORT_FILE = Path(__file__).parent / "report.csv"


def load_test_cases() -> list[dict]:
    with open(TEST_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def run_single_test(case: dict) -> dict:
    """Execute generation + validation pour un cas de test et retourne le resultat."""
    row = {
        "id": case["id"],
        "pattern_attendu": case["pattern"],
        "description": case["description"],
        "generation_ok": False,
        "validation_ok": False,
        "stage_echec": "",
        "detail": "",
    }

    # --- Etape 1 : generation ---
    try:
        workflow = generate_workflow(case["description"])
    except GenerationError as e:
        row["stage_echec"] = "generation"
        row["detail"] = str(e)
        return row

    row["generation_ok"] = True

    # Cas volontairement hors-perimetre : succes si l'agent le detecte bien
    if case["pattern"] == "out_of_scope":
        if isinstance(workflow, dict) and workflow.get("error") == "out_of_scope":
            row["validation_ok"] = True
            row["detail"] = "Hors-perimetre correctement detecte"
        else:
            row["stage_echec"] = "faux_positif"
            row["detail"] = "L'agent a genere un workflow pour un cas hors-perimetre"
        return row

    # --- Etape 2 : validation sandbox ---
    result = validate_workflow(workflow)
    row["validation_ok"] = result.passed
    row["stage_echec"] = "" if result.passed else result.stage
    row["detail"] = result.detail

    return row


def compute_and_print_summary(rows: list[dict]) -> None:
    total = len(rows)
    passed = sum(1 for r in rows if r["generation_ok"] and r["validation_ok"])
    print(f"\n=== Taux de reussite global : {passed}/{total} ({100 * passed / total:.1f}%) ===\n")

    by_pattern = defaultdict(lambda: {"total": 0, "passed": 0})
    for r in rows:
        p = r["pattern_attendu"]
        by_pattern[p]["total"] += 1
        if r["generation_ok"] and r["validation_ok"]:
            by_pattern[p]["passed"] += 1

    print("Detail par pattern :")
    for pattern, stats in sorted(by_pattern.items()):
        rate = 100 * stats["passed"] / stats["total"]
        print(f"  Pattern {pattern:12s} : {stats['passed']}/{stats['total']} ({rate:.1f}%)")


def main():
    cases = load_test_cases()
    rows = []

    for case in cases:
        print(f"[{case['id']}] Test en cours... ", end="", flush=True)
        row = run_single_test(case)
        status = "PASS" if (row["generation_ok"] and row["validation_ok"]) else "FAIL"
        print(status)
        rows.append(row)

    # Ecriture du rapport CSV (livrable Phase 4)
    with open(REPORT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nRapport detaille ecrit dans : {REPORT_FILE}")
    compute_and_print_summary(rows)


if __name__ == "__main__":
    main()
