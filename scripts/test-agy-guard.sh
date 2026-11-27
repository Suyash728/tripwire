#!/bin/bash
# Tests .agents/hooks/guard.sh (Antigravity) with the same cases as scripts/test-guard.sh (Claude Code).
# Usage: bash scripts/test-agy-guard.sh  (AGY_GUARD_REPO defaults to a throwaway repo on branch ci-test)
G="$(dirname "$0")/../.agents/hooks/guard.sh"
if [[ -z "${AGY_GUARD_REPO:-}" ]]; then
  AGY_GUARD_REPO=$(mktemp -d); trap 'rm -rf "$AGY_GUARD_REPO"' EXIT
  git init -q -b ci-test "$AGY_GUARD_REPO"
fi
export AGY_GUARD_REPO
fail=0
t() {
  local got; got=$(printf '%s' "$2" | "$G" 2>/dev/null | jq -r '.decision // "invalid"' 2>/dev/null)
  if [[ "$got" != "$1" ]]; then echo "FAIL (got ${got:-no output}, want $1): $3"; fail=1; else echo "ok   $3"; fi
}
R='{"toolCall":{"name":"run_command","args":{"CommandLine":'
t deny  "${R}\"git push origin main\"}}}"            "push origin main"
t deny  "${R}\"git push -f origin HEAD:main\"}}}"    "push HEAD:main"
t allow "${R}\"git push origin feat/maintenance\"}}}" "branch name containing main"
t deny  "${R}\"cat .env.local\"}}}"                   "cat .env.local"
t deny  "${R}\"cat backend/.env.production\"}}}"      "cat .env.production"
t deny  "${R}\"grep KEY .env\"}}}"                    "grep .env"
t deny  "${R}\"cat .env.example .env.local\"}}}"      "env file next to .env.example"
t allow "${R}\"cat .env.example\"}}}"                 "cat .env.example"
t allow "${R}\"ls -la\"}}}"                           "harmless command"
t deny  '{"toolCall":{"name":"view_file","args":{"AbsolutePath":"/r/.env.production"}}}'   "view_file .env.production"
t allow '{"toolCall":{"name":"view_file","args":{"AbsolutePath":"/r/.env.example"}}}'      "view_file .env.example"
t deny  '{"toolCall":{"name":"grep_search","args":{"SearchPath":"/r/.env","Query":"KEY"}}}' "grep_search .env"
t deny  '{"toolCall":{"name":"write_to_file","args":{"TargetFile":"/r/.env.local"}}}'      "write_to_file .env.local"
t deny  '{"toolCall":{"name":"replace_file_content","args":{"TargetFile":"/r/openapi.yaml"}}}'       "replace openapi.yaml"
t deny  '{"toolCall":{"name":"multi_replace_file_content","args":{"TargetFile":"/r/openapi.yaml"}}}' "multi-replace openapi.yaml"
t allow '{"toolCall":{"name":"view_file","args":{"AbsolutePath":"/r/openapi.yaml"}}}'      "view_file openapi.yaml"
t deny  "${R}\"sed -i s/a/b/ openapi.yaml\"}}}"       "sed -i openapi.yaml"
t allow "${R}\"npx @stoplight/prism-cli mock openapi.yaml -p 4010\"}}}" "prism mock reads openapi.yaml"
exit $fail
