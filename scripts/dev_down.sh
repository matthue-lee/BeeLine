#!/usr/bin/env bash
set -euo pipefail

ENV_FILE=${ENV_FILE:-.env}

# Default: keep volumes (preserve data)
# Pass --volumes or -v flag to delete data
if [[ -f "${ENV_FILE}" ]]; then
  docker compose --env-file "${ENV_FILE}" down "$@"
else
  docker compose down "$@"
fi