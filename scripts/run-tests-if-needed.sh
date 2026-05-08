#!/usr/bin/env bash
# =============================================================================
# Pre-commit hook : lance lint + tests si du code applicatif a ete modifie
# =============================================================================
# Declenchement : fichiers .py sous backend/src/ ou frontend/src/
# Si les tests passent, les rapports sont ajoutes au commit automatiquement.
# =============================================================================

set -euo pipefail

REPORT_TXT="ci/test-results/test_report.txt"
REPORT_XML="ci/test-results/report.xml"

# Verifier que le venv existe
if [ ! -f ".venv/bin/python" ]; then
    echo "ERREUR: venv introuvable (.venv). Creez-le avec :"
    echo "  python3.11 -m venv .venv && .venv/bin/pip install -r backend/requirements-dev.txt"
    exit 1
fi

# Verifier si des fichiers applicatifs sont stages
STAGED_APP_FILES=$(git diff --cached --name-only --diff-filter=ACMR \
    -- 'backend/src/**/*.py' 'frontend/src/**/*.py' || true)

if [ -z "$STAGED_APP_FILES" ]; then
    echo "Aucun fichier applicatif modifie, tests ignores."
    exit 0
fi

echo "Fichiers applicatifs modifies :"
echo "$STAGED_APP_FILES" | sed 's/^/  /'
echo ""

# --- Lint ---
echo "=== Lint ==="
if ! make lint; then
    echo ""
    echo "Lint echoue. Lancez 'make lint-fix' pour corriger."
    exit 1
fi

# --- Tests ---
echo ""
echo "=== Tests ==="
if ! make test; then
    echo ""
    echo "Les tests ont echoue. Commit annule."
    exit 1
fi

echo ""
echo "Lint + tests OK."

# Ajouter les rapports au commit si ils existent
for report in "$REPORT_TXT" "$REPORT_XML"; do
    if [ -f "$report" ]; then
        git add "$report"
    fi
done
