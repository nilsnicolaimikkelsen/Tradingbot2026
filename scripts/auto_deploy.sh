#!/bin/bash
# Auto-deploy: checks for new commits on the current branch and redeploys if found.
# Meant to run periodically via cron on the droplet (see README/setup instructions).
set -e

cd "$(dirname "$0")/.."

BRANCH=$(git rev-parse --abbrev-ref HEAD)
git fetch origin "$BRANCH"

LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse "origin/$BRANCH")

if [ "$LOCAL" != "$REMOTE" ]; then
    echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) Ny commit funnet (${LOCAL:0:7} -> ${REMOTE:0:7}), oppdaterer..."
    git pull origin "$BRANCH"
    docker compose up -d --build
    echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) Oppdatering fullført."
else
    echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) Ingen nye commits."
fi
