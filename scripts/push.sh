#!/bin/bash
# push.sh — Push la branche courante sur le remote
#
# Usage :
#   ./scripts/push.sh                # Push la branche courante
#   ./scripts/push.sh feature/auth   # Push une branche specifique

set -e

BRANCH="${1:-$(git rev-parse --abbrev-ref HEAD)}"

if [ "${BRANCH}" = "HEAD" ]; then
    echo "Erreur : HEAD detache. Specifie une branche : ./scripts/push.sh ma-branche"
    exit 1
fi

echo ""
echo "=== Push '${BRANCH}' ==="
echo ""

git push origin "${BRANCH}" 2>/dev/null || \
    git push --set-upstream origin "${BRANCH}"

echo ""
echo "=== Done ==="
echo ""
