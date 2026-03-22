#!/bin/bash
# Run tests for backend and/or frontend
# Usage: ./scripts/run_tests.sh [backend|frontend|all] [--coverage] [--verbose]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Default values
TARGET="${1:-backend}"
COVERAGE=""
VERBOSE="-v"

# Parse arguments
for arg in "$@"; do
    case $arg in
        --coverage) COVERAGE="--cov=src --cov-report=term-missing" ;;
        --verbose) VERBOSE="-vv" ;;
        --quiet) VERBOSE="" ;;
    esac
done

run_backend_tests() {
    echo -e "${YELLOW}Running backend tests...${NC}"
    cd "$PROJECT_ROOT/backend"

    # Set PYTHONPATH
    export PYTHONPATH="$PROJECT_ROOT/backend"

    pytest src/tests $VERBOSE $COVERAGE --tb=short

    if [ $? -eq 0 ]; then
        echo -e "${GREEN}Backend tests passed!${NC}"
    else
        echo -e "${RED}Backend tests failed!${NC}"
        return 1
    fi
}

run_frontend_tests() {
    echo -e "${YELLOW}Running frontend tests...${NC}"
    cd "$PROJECT_ROOT/frontend"

    # Set PYTHONPATH
    export PYTHONPATH="$PROJECT_ROOT/frontend"

    # Check if tests directory exists
    if [ -d "src/tests" ]; then
        pytest src/tests $VERBOSE --tb=short
    else
        echo -e "${YELLOW}No tests found for frontend${NC}"
    fi
}

case $TARGET in
    backend)
        run_backend_tests
        ;;
    frontend)
        run_frontend_tests
        ;;
    all)
        run_backend_tests
        echo ""
        run_frontend_tests
        ;;
    *)
        echo "Usage: $0 [backend|frontend|all] [--coverage] [--verbose]"
        exit 1
        ;;
esac
