#!/usr/bin/env bash
# Public HTTPS URL for the local API (quick tunnel, no Cloudflare login needed).
set -euo pipefail
exec cloudflared tunnel --url "http://localhost:${PORT:-8787}"
