#!/bin/bash
# dev-deploy.sh — Build, push et deploy sur le namespace dev du cluster K8s
#
# Usage :
#   ./scripts/dev-deploy.sh           # Build et deploy backend + frontend
#   ./scripts/dev-deploy.sh backend   # Build et deploy backend uniquement
#   ./scripts/dev-deploy.sh frontend  # Build et deploy frontend uniquement
#
# Prerequis :
#   - docker login registry.gitlab.com (une seule fois)
#   - Tailscale actif avec --accept-routes (reseau 10.10.0.0/24 accessible)
#   - kubectl configure avec le context admin@crypto-bot

set -e

REGISTRY="registry.gitlab.com/dst_crypto/crypto-bot-app"
TAG="dev"
COMPONENT=${1:-all}
NAMESPACE="dev"

# Verifier qu'on est a la racine du repo
if [ ! -f "docker-compose.yml" ]; then
    echo "Erreur : lance ce script depuis la racine du repo Crypto-bot-app/"
    exit 1
fi

# Verifier la connexion au cluster
if ! kubectl --context admin@crypto-bot get ns dev &>/dev/null; then
    echo "Erreur : impossible de joindre le cluster. Tailscale est actif (--accept-routes) ?"
    exit 1
fi

# versions.env = source unique de verite (memes images/versions que la CI et
# le docker-compose local) -- PYTHON_VERSION n'a pas de defaut dans les
# Dockerfiles, sans ce chargement le build echoue (ARG vide -> "FROM python:-slim").
export $(grep -v '^\s*#' versions.env | grep '=' | xargs)

echo "=== Dev Deploy (tag :$TAG) ==="

if [[ "$COMPONENT" == "backend" || "$COMPONENT" == "all" ]]; then
    echo ""
    echo "[1/2] Building backend..."
    # Contexte = racine du repo (pas ./backend) : backend/Dockerfile fait COPY utils/,
    # le package multi-exchange partage avec jobs/orchestration (cf. issue #10).
    docker build --build-arg PYTHON_VERSION=${PYTHON_VERSION} --target runtime -f backend/Dockerfile -t "$REGISTRY/backend:$TAG" .
    echo "Pushing backend:$TAG..."
    docker push "$REGISTRY/backend:$TAG"
    echo "Restarting backend pods..."
    kubectl --context admin@crypto-bot rollout restart deployment/crypto-bot-backend -n $NAMESPACE
fi

if [[ "$COMPONENT" == "frontend" || "$COMPONENT" == "all" ]]; then
    echo ""
    echo "[2/2] Building frontend..."
    docker build --build-arg PYTHON_VERSION=${PYTHON_VERSION} --build-arg APP_VERSION=$TAG -t "$REGISTRY/frontend:$TAG" ./frontend
    echo "Pushing frontend:$TAG..."
    docker push "$REGISTRY/frontend:$TAG"
    echo "Restarting frontend pods..."
    kubectl --context admin@crypto-bot rollout restart deployment/crypto-bot-frontend -n $NAMESPACE
fi

echo ""
echo "=== Deploy termine ==="
echo "Suivre les pods : kubectl --context admin@crypto-bot get pods -n $NAMESPACE -w"
echo "Logs backend    : kubectl --context admin@crypto-bot logs -n $NAMESPACE -f deployment/crypto-bot-backend"
echo "Logs frontend   : kubectl --context admin@crypto-bot logs -n $NAMESPACE -f deployment/crypto-bot-frontend"
echo "Port-forward    : kubectl --context admin@crypto-bot port-forward -n $NAMESPACE svc/crypto-bot-frontend 8501:8501"
