#!/bin/sh
# Demarre en root (pas de USER avant ENTRYPOINT dans le Dockerfile) pour pouvoir
# corriger les permissions des dossiers potentiellement bind-montes en root:root
# par Docker (ex. VM ou le hote a cree ces dossiers avant le premier `up`), puis
# bascule vers l'utilisateur non-root "app" avant de lancer la vraie commande.
# Meme pattern que les images officielles postgres/minio.
set -e

mkdir -p /app/logs /app/artifacts
chown -R app:app /app/logs /app/artifacts

exec gosu app "$@"
