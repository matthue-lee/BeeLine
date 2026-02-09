#!/usr/bin/env bash
set -euo pipefail

ENV_FILE=${ENV_FILE:-.env.docker}

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "Missing ${ENV_FILE}. Copy .env.docker.example and update secrets." >&2
  exit 1
fi

docker compose --env-file "${ENV_FILE}" up -d --build "$@"
