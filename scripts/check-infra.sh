#!/bin/bash
# =============================================================================
# check-infra.sh — Validation coherence infrastructure Docker
# =============================================================================
# Verifie que versions.env, Dockerfiles, docker-compose et Makefile sont
# coherents entre eux. Execute en pre-commit hook et manuellement.
# Inspire du pattern litho.
# =============================================================================

set -uo pipefail

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
    POSTGRES_IMAGE
    ADMINER_IMAGE
    MINIO_IMAGE
    MINIO_MC_IMAGE
    AIRFLOW_IMAGE
    REDIS_IMAGE
    PYTHON_VERSION
    PYTHON_CI_IMAGE
    SEMGREP_IMAGE
    SEMGREP_PRECOMMIT_VERSION
    HADOLINT_IMAGE
    RELEASE_CLI_IMAGE
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

for compose_file in docker-compose.yml docker-compose.staging.yml docker-compose.prod.yml ci/docker-compose.test.yml; do
    if [ ! -f "$compose_file" ]; then
        fail "$compose_file introuvable"
        continue
    fi

    # Le compose test a besoin de IMAGE_TAG pour valider
    EXTRA_ENV=""
    if echo "$compose_file" | grep -q "test"; then
        EXTRA_ENV="IMAGE_TAG=test:ci"
    fi

    if env $EXTRA_ENV docker compose -f "$compose_file" config > /dev/null 2>&1; then
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
# 5. Coherence des versions entre backend et frontend requirements
# =============================================================================
echo ""
echo "=== 5. Coherence versions requirements backend/frontend ==="

if [ -f backend/requirements.txt ] && [ -f frontend/requirements.txt ]; then
    # Extraire les packages communs et comparer les versions
    backend_pkgs=$(grep -E '^[a-zA-Z]' backend/requirements.txt | grep '==' | sort)
    frontend_pkgs=$(grep -E '^[a-zA-Z]' frontend/requirements.txt | grep '==' | sort)

    # Trouver les packages presents dans les deux fichiers
    common_pkgs=$(comm -12 \
        <(echo "$backend_pkgs" | cut -d= -f1 | tr '[:upper:]' '[:lower:]' | sort) \
        <(echo "$frontend_pkgs" | cut -d= -f1 | tr '[:upper:]' '[:lower:]' | sort))

    version_mismatch=false
    for pkg in $common_pkgs; do
        backend_ver=$(echo "$backend_pkgs" | grep -i "^${pkg}==" | head -1)
        frontend_ver=$(echo "$frontend_pkgs" | grep -i "^${pkg}==" | head -1)
        if [ "$backend_ver" != "$frontend_ver" ]; then
            fail "Version mismatch pour $pkg : backend=$backend_ver, frontend=$frontend_ver"
            version_mismatch=true
        fi
    done

    if [ "$version_mismatch" = false ]; then
        count=$(echo "$common_pkgs" | wc -w)
        pass "Versions coherentes ($count packages communs)"
    fi
else
    warn "requirements.txt manquant (backend ou frontend)"
fi

# =============================================================================
# 6. Resolution Makefile (dry-run)
# =============================================================================
echo ""
echo "=== 6. Verification resolution Makefile ==="

if [ -f Makefile ]; then
    if make -n dev-config > /dev/null 2>&1; then
        pass "Makefile resout les variables correctement"
    else
        fail "Makefile ne resout pas les variables (make -n dev-config echoue)"
    fi
else
    fail "Makefile introuvable"
fi

# =============================================================================
# 7. Dockerfiles — ARG sans valeur par defaut pour les variables de versions.env
# =============================================================================
echo ""
echo "=== 7. Verification ARG Dockerfiles (pas de valeur par defaut) ==="

for dockerfile in backend/Dockerfile frontend/Dockerfile; do
    if [ ! -f "$dockerfile" ]; then
        continue
    fi

    # Chercher les ARG avec valeur par defaut pour des variables presentes dans versions.env
    hardcoded_args=$(grep -E '^ARG\s+(PYTHON_VERSION)=' "$dockerfile" || true)
    if [ -n "$hardcoded_args" ]; then
        fail "$dockerfile contient des ARG avec valeur par defaut :\n  $hardcoded_args\n  Les valeurs doivent venir de versions.env via --build-arg"
    else
        pass "$dockerfile ARG sans valeur par defaut"
    fi
done

# =============================================================================
# 8. Synchronisation versions.env <-> .gitlab-ci.yml
# =============================================================================
echo ""
echo "=== 8. Synchronisation versions.env / .gitlab-ci.yml ==="

if [ -f .gitlab-ci.yml ]; then
    CI_VARS="PYTHON_CI_IMAGE SEMGREP_IMAGE HADOLINT_IMAGE RELEASE_CLI_IMAGE"
    sync_ok=true

    for var in $CI_VARS; do
        env_val=$(grep "^${var}=" versions.env | cut -d= -f2-)
        ci_val=$(grep "${var}:" .gitlab-ci.yml | head -1 | sed 's/.*: *"\(.*\)"/\1/')

        if [ -z "$env_val" ]; then
            fail "$var absent de versions.env"
            sync_ok=false
        elif [ -z "$ci_val" ]; then
            fail "$var absent de .gitlab-ci.yml"
            sync_ok=false
        elif [ "$env_val" != "$ci_val" ]; then
            fail "$var desynchronise : versions.env=$env_val, .gitlab-ci.yml=$ci_val"
            sync_ok=false
        fi
    done

    if [ "$sync_ok" = true ]; then
        count=$(echo "$CI_VARS" | wc -w)
        pass "versions.env et .gitlab-ci.yml synchronises ($count variables)"
    fi
else
    warn ".gitlab-ci.yml introuvable"
fi

# =============================================================================
# 9b. Synchronisation versions.env <-> .pre-commit-config.yaml (semgrep)
# =============================================================================
# Pas fonctionnelle (pre-commit ne lit pas versions.env : son "rev:" doit etre
# un tag git litteral, resolu par le framework pre-commit lui-meme). Ce check
# garde juste versions.env comme point unique a consulter, avec alerte en cas
# de derive plutot qu'une vraie source commune (impossible ici techniquement).
echo ""
echo "=== 9b. Synchronisation versions.env / .pre-commit-config.yaml (semgrep) ==="

if [ -f .pre-commit-config.yaml ]; then
    precommit_semgrep_rev=$(awk '/repo: https:\/\/github.com\/semgrep\/semgrep/{getline; print}' .pre-commit-config.yaml | sed -E 's/.*rev:[[:space:]]*v?//')
    env_semgrep_precommit=$(grep "^SEMGREP_PRECOMMIT_VERSION=" versions.env | cut -d= -f2-)

    if [ -z "$env_semgrep_precommit" ]; then
        fail "SEMGREP_PRECOMMIT_VERSION absent de versions.env"
    elif [ -z "$precommit_semgrep_rev" ]; then
        fail "rev semgrep introuvable dans .pre-commit-config.yaml"
    elif [ "$env_semgrep_precommit" != "$precommit_semgrep_rev" ]; then
        fail "Semgrep pre-commit desynchronise : versions.env=$env_semgrep_precommit, .pre-commit-config.yaml=$precommit_semgrep_rev"
    else
        pass "Semgrep pre-commit synchronise (v$precommit_semgrep_rev)"
    fi
else
    warn ".pre-commit-config.yaml introuvable"
fi

# =============================================================================
# 9. Coherence requirements.txt <-> requirements.txt.template
# =============================================================================
echo ""
echo "=== 9. Verification des requirements.txt generes ==="

if [ -f scripts/generate-requirements.py ]; then
    # Executer le generateur de requirements
    python3 scripts/generate-requirements.py > /dev/null 2>&1

    # Verifier s'il y a un diff git sur les fichiers generes
    if git diff --exit-code -- backend/requirements.txt jobs/requirements.txt orchestration/requirements.txt > /dev/null 2>&1; then
        pass "Fichiers requirements.txt synchronises avec les templates"
    else
        fail "Fichiers requirements.txt desynchronises ! Lancez 'python3 scripts/generate-requirements.py' et commitez les modifications."
        # Afficher le diff pour aider le developpeur
        git diff -- backend/requirements.txt jobs/requirements.txt orchestration/requirements.txt
    fi
else
    fail "scripts/generate-requirements.py introuvable"
fi

# =============================================================================
# Resultat
# =============================================================================
echo ""
if [ $ERRORS -gt 0 ]; then
    echo -e "${RED}=== $ERRORS erreur(s) detectee(s) ===${NC}"
    exit 1
else
    echo -e "${GREEN}=== Toutes les verifications passent (10 checks) ===${NC}"
    exit 0
fi
