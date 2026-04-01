#!/bin/bash
# =============================================================================
# check-infra.sh — Validation coherence infrastructure Docker
# =============================================================================
# Verifie que versions.env, Dockerfiles, docker-compose et Makefile sont
# coherents entre eux. Execute en pre-commit hook et manuellement.
# Inspire du pattern litho.
# =============================================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

ERRORS=0

fail() {
    echo -e "${RED}FAIL: $1${NC}"
    ERRORS=$((ERRORS + 1))
}

pass() {
    echo -e "${GREEN}OK: $1${NC}"
}

warn() {
    echo -e "${YELLOW}WARN: $1${NC}"
}

# =============================================================================
# 1. versions.env — toutes les variables attendues sont definies
# =============================================================================
echo ""
echo "=== 1. Verification versions.env ==="

REQUIRED_VARS=(
    MONGO_IMAGE
    MONGO_EXPRESS_IMAGE
    POSTGRES_IMAGE
    ADMINER_IMAGE
    MINIO_IMAGE
    MINIO_MC_IMAGE
    PYTHON_VERSION
    PYTHON_CI_IMAGE
    SEMGREP_IMAGE
    HADOLINT_IMAGE
)

if [ ! -f versions.env ]; then
    fail "versions.env introuvable"
else
    for var in "${REQUIRED_VARS[@]}"; do
        value=$(grep "^${var}=" versions.env | cut -d= -f2-)
        if [ -z "$value" ]; then
            fail "Variable $var manquante ou vide dans versions.env"
        fi
    done

    # Verifier qu'aucune ligne ne contient de secret (mot de passe, token)
    if grep -iE '(password|secret|token|key)=' versions.env | grep -v '^\s*#' > /dev/null 2>&1; then
        fail "versions.env semble contenir des secrets ! Utiliser .env pour les secrets."
    fi

    if [ $ERRORS -eq 0 ]; then
        pass "versions.env complet (${#REQUIRED_VARS[@]} variables)"
    fi
fi

# =============================================================================
# 2. docker-compose config — les 3 fichiers se resolvent sans erreur
# =============================================================================
echo ""
echo "=== 2. Verification docker-compose config ==="

# Charger versions.env pour la validation
export $(grep -v '^\s*#' versions.env | grep '=' | xargs) 2>/dev/null

for compose_file in docker-compose.yml docker-compose.staging.yml docker-compose.prod.yml; do
    if [ ! -f "$compose_file" ]; then
        fail "$compose_file introuvable"
        continue
    fi

    if docker compose -f "$compose_file" config > /dev/null 2>&1; then
        # Compter les services (hors profiles)
        services=$(docker compose -f "$compose_file" config --services 2>/dev/null | wc -l)
        pass "$compose_file valide ($services services)"
    else
        fail "$compose_file invalide"
        docker compose -f "$compose_file" config 2>&1 | head -5
    fi
done

# =============================================================================
# 3. Dockerfiles — pas de versions hardcodees
# =============================================================================
echo ""
echo "=== 3. Verification Dockerfiles (pas de versions hardcodees) ==="

for dockerfile in backend/Dockerfile frontend/Dockerfile; do
    if [ ! -f "$dockerfile" ]; then
        fail "$dockerfile introuvable"
        continue
    fi

    # Verifier que FROM utilise un ARG, pas une version en dur
    # On accepte : FROM python:${PYTHON_VERSION}-slim
    # On refuse  : FROM python:3.11-slim (sans ARG)
    hardcoded_from=$(grep -E '^FROM\s+\S+:\S+' "$dockerfile" | grep -v '\$' || true)
    if [ -n "$hardcoded_from" ]; then
        fail "$dockerfile contient des versions hardcodees dans FROM:\n  $hardcoded_from"
    else
        pass "$dockerfile utilise des ARG pour les versions"
    fi
done

# =============================================================================
# 4. Detection de secrets dans les fichiers d'infra
# =============================================================================
echo ""
echo "=== 4. Detection de secrets dans les fichiers d'infra ==="

INFRA_FILES="docker-compose.yml docker-compose.staging.yml docker-compose.prod.yml Makefile versions.env"
SECRET_PATTERN='(password|passwd|secret|token|api_key)[[:space:]]*[:=][[:space:]]*[^$#]'

found_secrets=false
for f in $INFRA_FILES; do
    if [ -f "$f" ]; then
        # Ignorer les lignes avec ${...} (variables d'environnement) et les commentaires
        matches=$(grep -inE '(password|passwd|secret|token|api_key)\s*[:=]\s*[a-zA-Z0-9]' "$f" | grep -v '^\s*#' | grep -v '\${' || true)
        if [ -n "$matches" ]; then
            fail "Secrets potentiels dans $f :\n$matches"
            found_secrets=true
        fi
    fi
done

if [ "$found_secrets" = false ]; then
    pass "Aucun secret detecte dans les fichiers d'infra"
fi

# =============================================================================
# Resultat
# =============================================================================
echo ""
if [ $ERRORS -gt 0 ]; then
    echo -e "${RED}=== $ERRORS erreur(s) detectee(s) ===${NC}"
    exit 1
else
    echo -e "${GREEN}=== Toutes les verifications passent ===${NC}"
    exit 0
fi
