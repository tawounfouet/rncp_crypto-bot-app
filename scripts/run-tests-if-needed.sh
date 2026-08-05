#!/usr/bin/env bash
# =============================================================================
# Pre-commit hook : lance lint (complet) + tests (cibles) si du code applicatif
# a ete modifie
# =============================================================================
# Declenchement : fichiers .py sous backend/{src,tests}/, frontend/{src,tests}/,
# utils/ ou jobs/. Seules les suites de tests concernees par les zones modifiees
# sont relancees (voir mapping de dependances plus bas), pas toute la suite a
# chaque commit. Si les tests passent, les rapports sont ajoutes au commit
# automatiquement.
# =============================================================================

set -euo pipefail

REPORT_TXT="ci/test-results/test_report.txt"
REPORT_XML="ci/test-results/report.xml"

# Verifier que le venv existe (Linux/macOS/WSL2 : .venv/bin/python, Windows : .venv/Scripts/python.exe)
if [ -f ".venv/bin/python" ]; then
    VENV_PYTHON=".venv/bin/python"
elif [ -f ".venv/Scripts/python.exe" ]; then
    VENV_PYTHON=".venv/Scripts/python.exe"
else
    echo "ERREUR: venv introuvable (.venv). Creez-le avec :"
    echo "  Linux/macOS/WSL2  : python3.11 -m venv .venv && .venv/bin/python -m pip install -r backend/requirements-dev.txt"
    echo "  Windows PowerShell: py -3.11 -m venv .venv && .\\.venv\\Scripts\\python.exe -m pip install -r backend\\requirements-dev.txt"
    echo "  Windows Git Bash  : py -3.11 -m venv .venv && .venv/Scripts/python.exe -m pip install -r backend/requirements-dev.txt"
    exit 1
fi

echo "Venv detecte : $VENV_PYTHON"

# Verifier si des fichiers applicatifs sont stages
STAGED_APP_FILES=$(git diff --cached --name-only --diff-filter=ACMR \
    -- 'backend/src/**/*.py' 'backend/tests/**/*.py' 'frontend/src/**/*.py' 'frontend/tests/**/*.py' \
       'utils/**/*.py' 'jobs/**/*.py' || true)

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
# Cible uniquement les suites concernees par les zones modifiees, au lieu de toute la suite
# a chaque commit. backend/ et jobs/ dependent tous les deux de utils/ (verifie via grep sur
# les imports "from utils.X"), donc un changement dans utils/ relance aussi ces deux-la ;
# frontend/ est totalement independant (son propre package utils/ local, aucun import du
# utils/ racine) et n'est jamais relance par un changement ailleurs.
TARGETS=""
echo "$STAGED_APP_FILES" | grep -q '^backend/' && TARGETS="$TARGETS test-backend"
echo "$STAGED_APP_FILES" | grep -q '^frontend/' && TARGETS="$TARGETS test-frontend"
echo "$STAGED_APP_FILES" | grep -q '^jobs/' && TARGETS="$TARGETS test-jobs"
if echo "$STAGED_APP_FILES" | grep -q '^utils/'; then
    TARGETS="$TARGETS test-utils test-backend test-jobs"
fi
TARGETS=$(echo "$TARGETS" | tr ' ' '\n' | sort -u | tr '\n' ' ')

echo ""
echo "=== Tests (cibles : $TARGETS) ==="
if ! make $TARGETS; then
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
