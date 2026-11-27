#!/usr/bin/env bash
# Run API (:8787) and UI (:3000) together; Ctrl-C stops both.
set -euo pipefail
cd "$(dirname "$0")/.."
trap 'kill 0' EXIT
(cd backend && uv run uvicorn app.main:app --port 8787 --reload) &
(cd frontend && npm run dev) &
wait
