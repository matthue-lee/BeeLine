#!/usr/bin/env bash
set -euo pipefail

ENV_FILE=${ENV_FILE:-.env.docker}

if [[ -z "${DATABASE_URL:-}" && -f "${ENV_FILE}" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "${ENV_FILE}"
  set +a
fi

DATABASE_URL=${DATABASE_URL:-sqlite:///db/beeline.db}

python - <<'PY'
import os
from pathlib import Path
from sqlalchemy.engine import make_url

database_url = os.environ.get("DATABASE_URL", "sqlite:///db/beeline.db")
url = make_url(database_url)
if url.get_backend_name() == "sqlite":
    path = url.database
    if path and path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).unlink(missing_ok=True)
PY

alembic upgrade head
