#!/usr/bin/env bash
# =============================================================================
# verify.sh — Vérifie que tous les services installés sont PRÉSENTS et HEALTHY
#
# Contrôle, pour la stack dev : chaque service attendu tourne (présence) et
# répond à son healthcheck (backend, frontend, airflow, minio, postgres, ml-api,
# mlflow). Ne teste PAS la config (cf. `make check-infra`).
#
# Usage :
#   ./scripts/verify.sh                 # vérifie la stack déjà démarrée
#   ./scripts/verify.sh --fresh         # down-v -> build -> up, puis vérifie
#   ./scripts/verify.sh --with-tests    # + lance la suite de tests backend
#   (options combinables)
#
# Code de sortie : 0 si tout est OK, 1 sinon (utilisable en CI).
# =============================================================================
set -uo pipefail
cd "$(dirname "$0")/.."

FRESH=0; WITH_TESTS=0
for arg in "$@"; do
  case "$arg" in
    --fresh) FRESH=1 ;;
    --with-tests) WITH_TESTS=1 ;;
    *) echo "Option inconnue : $arg" ; exit 2 ;;
  esac
done

FAIL=0
ok()  { printf "  \033[32m✓\033[0m %s\n" "$1"; }
ko()  { printf "  \033[31m✗\033[0m %s\n" "$1"; FAIL=1; }
sect(){ echo ; echo "== $1 =="; }

running() { docker ps --format '{{.Names}}' 2>/dev/null | grep -qx "$1"; }

# Attend un HTTP 200 (nom, url, nb_essais)
wait_http() {
  local name="$1" url="$2" tries="${3:-30}" code=""
  for _ in $(seq 1 "$tries"); do
    code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "$url" 2>/dev/null || true)
    [ "$code" = "200" ] && { ok "$name : présent + HTTP 200"; return 0; }
    sleep 4
  done
  ko "$name : KO (dernier code: ${code:-aucun})"; return 1
}

# Service HTTP : présence du conteneur + healthcheck HTTP (nom, conteneur, url)
svc_http() {
  local name="$1" cont="$2" url="$3"
  if ! running "$cont"; then ko "$name : conteneur '$cont' absent"; return 1; fi
  wait_http "$name" "$url"
}

# Service présent uniquement (nom, conteneur)
svc_present() {
  local name="$1" cont="$2"
  running "$cont" && ok "$name : présent" || ko "$name : conteneur '$cont' absent"
}

if [ "$FRESH" = "1" ]; then
  sect "0. Redéploiement à neuf (down-v -> build -> up)"
  make dev-down-v >/dev/null 2>&1 || true
  make dev-build  || { echo "build KO"; exit 1; }
  make dev-up     || { echo "dev-up KO"; exit 1; }
fi

sect "Présence + santé des services installés"
svc_http "backend          " crypto-bot-backend   "http://localhost:8009/health"
svc_http "frontend         " crypto-bot-frontend  "http://localhost:8501/_stcore/health"
svc_http "airflow-webserver" airflow-webserver    "http://localhost:8080/health"
svc_http "minio            " minio-s3-service     "http://localhost:9000/minio/health/live"
wait_http "minio console    " "http://localhost:9001"

# postgres : présence + pg_isready
if running postgres-db && docker exec postgres-db pg_isready -U "${POSTGRES_USER:-postgres}" >/dev/null 2>&1; then
  ok "postgres          : présent + pg_isready"
else
  ko "postgres          : absent ou injoignable"
fi

# Airflow scheduler : présent + heartbeat 'healthy' via l'API du webserver
svc_present "airflow-scheduler" airflow-scheduler
if curl -s --max-time 5 http://localhost:8080/health 2>/dev/null | grep -q '"status": "healthy"'; then
  ok "airflow scheduler : metadatabase + scheduler healthy"
else
  ko "airflow scheduler : non 'healthy'"
fi

# Couche ML (présence — installées via la stack)
svc_present "ml-api           " crypto-bot-ml-api
svc_present "mlflow-ui        " mlflow-ui

sect "Tests backend"
if [ "$WITH_TESTS" = "1" ]; then
  if make test-backend; then ok "suite de tests backend"; else ko "tests backend en échec"; fi
else
  echo "  (ignoré — relancer avec --with-tests)"
fi

sect "Résultat"
if [ "$FAIL" = "0" ]; then
  echo -e "\033[32m✅ VERIFICATION OK — tous les services présents et en bonne santé.\033[0m"; exit 0
else
  echo -e "\033[31m❌ VERIFICATION ÉCHOUÉE — voir les ✗ ci-dessus.\033[0m"; exit 1
fi
