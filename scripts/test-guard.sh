#!/bin/bash
# Usage: bash scripts/test-guard.sh  (run from a non-main branch)
G="$(dirname "$0")/../.claude/hooks/guard.sh"; [[ -x "$G" ]] || G=./guard.sh
fail=0
t() { printf '%s' "$2" | "$G" >/dev/null 2>&1; local rc=$?; if [[ $rc -ne $1 ]]; then echo "FAIL (got $rc, want $1): $3"; fail=1; else echo "ok   $3"; fi; }
B='{"tool_name":"Bash","tool_input":{"command":'
t 2 "${B}\"git push origin main\"}}"            "push origin main"
t 2 "${B}\"git push -f origin HEAD:main\"}}"    "push HEAD:main"
t 0 "${B}\"git push origin feat/maintenance\"}}" "branch name containing main"
t 2 "${B}\"cat .env.local\"}}"                   "cat .env.local"
t 2 "${B}\"cat backend/.env.production\"}}"      "cat .env.production"
t 2 "${B}\"grep KEY .env\"}}"                    "grep .env"
t 0 "${B}\"cat .env.example\"}}"                 "cat .env.example"
t 0 "${B}\"ls -la\"}}"                           "harmless command"
t 2 '{"tool_name":"Read","tool_input":{"file_path":"/r/.env.production"}}' "Read .env.production"
t 0 '{"tool_name":"Read","tool_input":{"file_path":"/r/.env.example"}}'    "Read .env.example"
t 2 '{"tool_name":"Grep","tool_input":{"pattern":"KEY","path":"/r/.env"}}' "Grep .env"
t 2 '{"tool_name":"Edit","tool_input":{"file_path":"/r/openapi.yaml"}}'    "Edit openapi.yaml"
t 0 '{"tool_name":"Read","tool_input":{"file_path":"/r/openapi.yaml"}}'    "Read openapi.yaml"
t 2 "${B}\"sed -i s/a/b/ openapi.yaml\"}}"       "sed -i openapi.yaml"
t 0 "${B}\"npx @stoplight/prism-cli mock openapi.yaml -p 4010\"}}" "prism mock reads openapi.yaml"
exit $fail
