#!/usr/bin/env bash
# Per-event MCP servers for THIS project only (Claude Code, Antigravity CLI, opencode).
# Usage: bash scripts/event-mcp.sh <supabase_project_ref> [--read-only] [--n8n] [--firebase]
#   --read-only  add &read_only=true to Supabase (use for anything holding real user data)
#   --n8n        add n8n-MCP (docs/validation tools only; no API key is written)
#   --firebase   add the Firebase MCP (uses firebase.json in the repo root)
# Idempotent: re-running updates the same entries. Never writes tokens: Supabase uses OAuth on first use.
# Docs: n8n-MCP README (github.com/czlonkowski/n8n-mcp), Firebase https://firebase.google.com/docs/ai-assistance/mcp-server,
#       Antigravity https://antigravity.google/docs/settings?tab=cli (workspace MCP: .agents/mcp_config.json, serverUrl).
# shellcheck disable=SC2016  # $url / $schema in single quotes are jq variables, not shell expansions
set -euo pipefail

usage() { sed -n '2,6p' "$0" | sed 's/^# \{0,1\}//'; exit "${1:-0}"; }

REF="" READ_ONLY=0 WANT_N8N=0 WANT_FIREBASE=0
for arg in "$@"; do
  case "$arg" in
    --read-only) READ_ONLY=1 ;;
    --n8n) WANT_N8N=1 ;;
    --firebase) WANT_FIREBASE=1 ;;
    -h|--help) usage 0 ;;
    -*) echo "Unknown flag: $arg" >&2; usage 1 ;;
    *) [[ -z "$REF" ]] || { echo "Only one project ref allowed" >&2; exit 1; }; REF="$arg" ;;
  esac
done
[[ -n "$REF" ]] || usage 1
[[ "$REF" =~ ^[a-z0-9]{20}$ ]] || { echo "Project ref must be 20 lowercase letters/digits (Supabase dashboard > Project Settings)." >&2; exit 1; }

for bin in jq claude; do command -v "$bin" >/dev/null || { echo "Missing: $bin" >&2; exit 1; }; done

ROOT=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
cd "$ROOT"
TS=$(date +%Y%m%d-%H%M)
AGY_CFG=".agents/mcp_config.json"
OC_CFG="opencode.json"

SUPABASE_URL="https://mcp.supabase.com/mcp?project_ref=${REF}&features=database,docs,debugging,development"
(( READ_ONLY )) && SUPABASE_URL="${SUPABASE_URL}&read_only=true"

backup() { # backup <file>: timestamped copy once per run, only if it exists
  [[ -f "$1" && ! -f "$1.bak-$TS" ]] && cp -p "$1" "$1.bak-$TS" && echo "  backup: $1.bak-$TS"
  return 0
}

merge_json() { # merge_json <file> <jq filter> [jq args...]: create if missing, validate, replace atomically
  local file=$1 filter=$2; shift 2
  local tmp
  backup "$file"
  mkdir -p "$(dirname "$file")"
  [[ -s "$file" ]] || echo '{}' > "$file"
  tmp=$(mktemp "${file}.tmp.XXXXXX")
  if jq "$@" "$filter" "$file" > "$tmp" && jq -e . "$tmp" >/dev/null; then
    mv "$tmp" "$file"
  else
    rm -f "$tmp"; echo "Failed to update $file" >&2; exit 1
  fi
}

claude_add() { # claude_add <name> <claude mcp add args...>: remove project entry if present, then add
  local name=$1; shift
  claude mcp remove --scope project "$name" >/dev/null 2>&1 || true
  claude mcp add --scope project "$@"
}

OC_SCHEMA='."$schema" = (."$schema" // "https://opencode.ai/config.json")'
REMOVE=()

# ---------- Supabase (remote, OAuth) ----------
echo "== supabase (project_ref=$REF, read_only=$READ_ONLY)"
claude_add supabase --transport http supabase "$SUPABASE_URL"
merge_json "$AGY_CFG" '.mcpServers.supabase = {serverUrl: $url}' --arg url "$SUPABASE_URL"
merge_json "$OC_CFG" "$OC_SCHEMA"' | .mcp.supabase = {type: "remote", url: $url, enabled: true}' --arg url "$SUPABASE_URL"
REMOVE+=(supabase)

# ---------- n8n-MCP (stdio, docs + validation tools) ----------
if (( WANT_N8N )); then
  echo "== n8n-mcp"
  claude_add n8n-mcp n8n-mcp -e MCP_MODE=stdio -e LOG_LEVEL=error -e DISABLE_CONSOLE_OUTPUT=true -- npx n8n-mcp
  merge_json "$AGY_CFG" '.mcpServers["n8n-mcp"] = {command: "npx", args: ["n8n-mcp"],
    env: {MCP_MODE: "stdio", LOG_LEVEL: "error", DISABLE_CONSOLE_OUTPUT: "true"}}'
  merge_json "$OC_CFG" "$OC_SCHEMA"' | .mcp["n8n-mcp"] = {type: "local", command: ["npx", "n8n-mcp"], enabled: true,
    environment: {MCP_MODE: "stdio", LOG_LEVEL: "error", DISABLE_CONSOLE_OUTPUT: "true"}}'
  REMOVE+=(n8n-mcp)
  echo "  Workflow-management tools need N8N_API_URL + N8N_API_KEY: add them per agent by hand from your shell env;"
  echo "  never commit the key."
fi

# ---------- Firebase MCP (stdio via firebase-tools) ----------
if (( WANT_FIREBASE )); then
  echo "== firebase"
  claude_add firebase firebase -- npx -y firebase-tools@latest mcp
  merge_json "$AGY_CFG" '.mcpServers.firebase = {command: "npx", args: ["-y", "firebase-tools@latest", "mcp"]}'
  merge_json "$OC_CFG" "$OC_SCHEMA"' | .mcp.firebase = {type: "local", command: ["npx", "-y", "firebase-tools@latest", "mcp"], enabled: true}'
  REMOVE+=(firebase)
  echo "  Sign in once with: npx -y firebase-tools@latest login"
fi

# ---------- Next steps + removal ----------
cat <<EOF

Done. Files touched: .mcp.json (Claude Code), $AGY_CFG (Antigravity), $OC_CFG (opencode).
First use:
  Claude Code: run /mcp, approve the project servers, authenticate supabase (browser OAuth).
  Antigravity: run /mcp in agy (OAuth starts on first use).
  opencode:    opencode mcp auth supabase && opencode mcp list
EOF

echo
echo "After the event, remove with:"
for name in "${REMOVE[@]}"; do
  echo "  claude mcp remove --scope project $name"
  echo "  jq 'del(.mcpServers[\"$name\"])' $AGY_CFG > $AGY_CFG.tmp && mv $AGY_CFG.tmp $AGY_CFG"
  echo "  jq 'del(.mcp[\"$name\"])' $OC_CFG > $OC_CFG.tmp && mv $OC_CFG.tmp $OC_CFG"
done
echo "  opencode mcp logout supabase   # drop stored OAuth tokens"
