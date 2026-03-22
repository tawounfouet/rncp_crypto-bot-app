#!/bin/bash
# Run linting for backend and/or frontend
# Usage: ./scripts/run_lint.sh [backend|frontend|all] [--fix]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

# Default values
TARGET="${1:-all}"
FIX_MODE=false

# Parse arguments
for arg in "$@"; do
    case $arg in
        --fix) FIX_MODE=true ;;
    esac
done

run_lint() {
    local name=$1
    local path=$2

    echo -e "${CYAN}=== Linting $name ===${NC}"

    # Flake8
    echo -e "${YELLOW}Running flake8...${NC}"
    if flake8 "$path" --max-line-length=120 --exclude=tests --statistics; then
        echo -e "${GREEN}flake8: OK${NC}"
    else
        echo -e "${RED}flake8: FAILED${NC}"
        LINT_FAILED=true
    fi

    # Black
    echo -e "${YELLOW}Running black...${NC}"
    if [ "$FIX_MODE" = true ]; then
        black "$path" --exclude='tests/'
        echo -e "${GREEN}black: Fixed${NC}"
    else
        if black --check "$path" --exclude='tests/'; then
            echo -e "${GREEN}black: OK${NC}"
        else
            echo -e "${RED}black: FAILED (run with --fix to auto-format)${NC}"
            LINT_FAILED=true
        fi
    fi

    echo ""
}

LINT_FAILED=false

case $TARGET in
    backend)
        run_lint "Backend" "$PROJECT_ROOT/backend/src"
        ;;
    frontend)
        run_lint "Frontend" "$PROJECT_ROOT/frontend/src"
        ;;
    all)
        run_lint "Backend" "$PROJECT_ROOT/backend/src"
        run_lint "Frontend" "$PROJECT_ROOT/frontend/src"
        ;;
    *)
        echo "Usage: $0 [backend|frontend|all] [--fix]"
        exit 1
        ;;
esac

if [ "$LINT_FAILED" = true ]; then
    echo -e "${RED}Linting failed!${NC}"
    exit 1
else
    echo -e "${GREEN}All linting passed!${NC}"
fi
