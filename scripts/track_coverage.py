#!/usr/bin/env python3
"""Ajoute une ligne a docs/coverage_history.csv a partir des coverage.json generes
par `make test-coverage` (backend+utils a la racine, frontend dans frontend/).

Usage : make test-coverage && python3 scripts/track_coverage.py
"""

import csv
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parent.parent
BACKEND_UTILS_JSON = APP_ROOT / "coverage.json"
FRONTEND_JSON = APP_ROOT / "frontend" / "coverage.json"
HISTORY_CSV = APP_ROOT / "docs" / "coverage_history.csv"
REPORT_MD = APP_ROOT / "docs" / "coverage_report.md"

CSV_HEADER = ["date", "backend_utils_pct", "frontend_pct"]


def load_coverage_json(json_path: Path) -> dict:
    if not json_path.exists():
        print(f"Fichier introuvable : {json_path} -- lance 'make test-coverage' d'abord.", file=sys.stderr)
        sys.exit(1)
    return json.loads(json_path.read_text())


def append_row(backend_utils_pct: float, frontend_pct: float) -> None:
    HISTORY_CSV.parent.mkdir(parents=True, exist_ok=True)
    is_new_file = not HISTORY_CSV.exists()

    with HISTORY_CSV.open("a", newline="") as f:
        writer = csv.writer(f)
        if is_new_file:
            writer.writerow(CSV_HEADER)
        writer.writerow([datetime.now(UTC).date().isoformat(), backend_utils_pct, frontend_pct])


def render_file_table(data: dict) -> str:
    """Tableau Markdown trie par % croissant (les fichiers les moins couverts en premier)."""
    rows = []
    for path, file_data in data["files"].items():
        summary = file_data["summary"]
        if summary["num_statements"] == 0:
            continue
        rows.append(
            (
                path,
                summary["num_statements"],
                summary["missing_lines"],
                summary["percent_covered"],
                file_data["missing_lines"],
            )
        )
    rows.sort(key=lambda r: r[3])

    lines = ["| Fichier | Lignes | Manquantes | % | Lignes non couvertes |",
             "|---|---|---|---|---|"]
    for path, num_statements, missing_count, pct, missing_lines in rows:
        missing_repr = ", ".join(str(n) for n in missing_lines[:15])
        if len(missing_lines) > 15:
            missing_repr += ", ..."
        lines.append(f"| {path} | {num_statements} | {missing_count} | {pct:.0f}% | {missing_repr} |")
    return "\n".join(lines)


def render_report(backend_utils_data: dict, frontend_data: dict) -> str:
    date_str = datetime.now(UTC).date().isoformat()
    backend_pct = backend_utils_data["totals"]["percent_covered"]
    frontend_pct = frontend_data["totals"]["percent_covered"]

    return f"""# Rapport de couverture de test

Snapshot du {date_str} -- regenere a chaque `python3 scripts/track_coverage.py`
(ecrase le precedent, pas un historique -- voir `coverage_history.csv` pour l'evolution du %).

## Backend + utils ({backend_pct:.1f}%)

{render_file_table(backend_utils_data)}

## Frontend ({frontend_pct:.1f}%)

{render_file_table(frontend_data)}
"""


def write_report(backend_utils_data: dict, frontend_data: dict) -> None:
    REPORT_MD.parent.mkdir(parents=True, exist_ok=True)
    REPORT_MD.write_text(render_report(backend_utils_data, frontend_data))


def main() -> None:
    backend_utils_data = load_coverage_json(BACKEND_UTILS_JSON)
    frontend_data = load_coverage_json(FRONTEND_JSON)

    backend_utils_pct = round(backend_utils_data["totals"]["percent_covered"], 2)
    frontend_pct = round(frontend_data["totals"]["percent_covered"], 2)

    append_row(backend_utils_pct, frontend_pct)
    write_report(backend_utils_data, frontend_data)

    print(f"Ajoute a {HISTORY_CSV} : backend+utils={backend_utils_pct}%, frontend={frontend_pct}%")
    print(f"Rapport detaille regenere dans {REPORT_MD}")


if __name__ == "__main__":
    main()
