#!/usr/bin/env bash

set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <beehive-url>" >&2
  exit 1
fi

URL="$1"
USER_AGENT="${HTTP_USER_AGENT:-BeeLineReleaseMonitor/1.0 (+mailto:matthew.r.c.lee@outlook.com)}"
OUTDIR="curl_captures"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
BODY_FILE="$OUTDIR/${TIMESTAMP}_body.html"
LOG_FILE="$OUTDIR/${TIMESTAMP}_curl.log"

mkdir -p "$OUTDIR"

echo "Saving response body to $BODY_FILE"
echo "Saving verbose curl log to $LOG_FILE"

curl -v -A "$USER_AGENT" "$URL" -o "$BODY_FILE" 2>"$LOG_FILE"

echo "Done. Attach $BODY_FILE and $LOG_FILE in your email to Beehive support."
