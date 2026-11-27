#!/usr/bin/env bash
# Lighthouse scores (performance, accessibility, best-practices) for a running UI.
# Usage: bash scripts/lighthouse.sh <url>        e.g. bash scripts/lighthouse.sh http://localhost:3000
# Measure a production build (`npm run build && npx next start`); `next dev` scores are not representative.
# Chrome: uses $CHROME_PATH if set, otherwise Playwright's Chromium (cd frontend && npx playwright install chromium).
set -euo pipefail

URL="${1:-}"
[[ -n "$URL" ]] || { echo "Usage: bash scripts/lighthouse.sh <url>" >&2; exit 1; }
command -v jq >/dev/null || { echo "Missing: jq" >&2; exit 1; }

ROOT=$(cd "$(dirname "$0")/.." && pwd)
if [[ -z "${CHROME_PATH:-}" ]]; then
  CHROME_PATH=$(cd "$ROOT/frontend" &&
    node -e 'console.log(require("@playwright/test").chromium.executablePath())' 2>/dev/null || true)
fi
[[ -x "${CHROME_PATH:-}" ]] || { echo "No Chrome found: set CHROME_PATH or install Playwright Chromium." >&2; exit 1; }
export CHROME_PATH

REPORT=$(mktemp)
trap 'rm -f "$REPORT"' EXIT

npx -y lighthouse@13 "$URL" \
  --only-categories=performance,accessibility,best-practices \
  --output=json --output-path="$REPORT" --quiet \
  --chrome-flags="--headless=new --no-sandbox"

jq -r '"Lighthouse: \(.finalDisplayedUrl // .finalUrl)",
  (.categories | to_entries[] | "  \(.value.title): \((.value.score * 100) | round)")' "$REPORT"
