#!/bin/bash
# Check Docker containers status and health
# Usage: ./scripts/docker_status.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}=== Docker Containers Status ===${NC}"
echo ""

cd "$PROJECT_ROOT"

# Check if docker-compose is running
if ! docker compose ps --quiet 2>/dev/null | grep -q .; then
    echo -e "${YELLOW}No containers running${NC}"
    echo "Start with: docker compose up -d"
    exit 0
fi

# Show container status
docker compose ps

echo ""
echo -e "${CYAN}=== Health Checks ===${NC}"

# Backend health
if curl -sf http://localhost:8009/health > /dev/null 2>&1; then
    echo -e "Backend:  ${GREEN}healthy${NC} (http://localhost:8009)"
else
    echo -e "Backend:  ${RED}unhealthy${NC}"
fi

# Frontend health
if curl -sf http://localhost:8501/_stcore/health > /dev/null 2>&1; then
    echo -e "Frontend: ${GREEN}healthy${NC} (http://localhost:8501)"
else
    echo -e "Frontend: ${RED}unhealthy${NC}"
fi

# Database
if docker compose exec -T postgres pg_isready -U postgres > /dev/null 2>&1; then
    echo -e "Postgres: ${GREEN}healthy${NC}"
else
    echo -e "Postgres: ${RED}unhealthy${NC}"
fi

echo ""
echo -e "${CYAN}=== Recent Logs (last 5 lines) ===${NC}"
echo -e "${YELLOW}Backend:${NC}"
docker compose logs --tail=5 backend 2>/dev/null || echo "No logs"
echo ""
echo -e "${YELLOW}Frontend:${NC}"
docker compose logs --tail=5 frontend 2>/dev/null || echo "No logs"
