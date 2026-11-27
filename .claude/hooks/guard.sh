#!/bin/bash
# PreToolUse guard for Claude Code. exit 2 = block (stderr is shown to Claude). Needs jq + git.
input=$(cat)
tool=$(jq -r '.tool_name // ""' <<<"$input")
cmd=$(jq -r '.tool_input.command // ""' <<<"$input")
path=$(jq -r '.tool_input.file_path // .tool_input.path // ""' <<<"$input")
block() { echo "Blocked: $1" >&2; exit 2; }
is_env() { local b; b=$(basename -- "$1"); [[ "$b" == .env* && "$b" != ".env.example" ]]; }

# 1) No pushes to main/master: explicit target, or a plain push while on main.
if [[ "$tool" == "Bash" && "$cmd" =~ (^|[;&|[:space:]])git[[:space:]]+push ]]; then
  [[ "$cmd" =~ [[:space:]:+](main|master)([[:space:]]|$) ]] && block "no direct push to main. Push a branch."
  branch=$(git -C "${CLAUDE_PROJECT_DIR:-.}" branch --show-current 2>/dev/null)
  [[ "$branch" == "main" || "$branch" == "master" ]] && block "you are on $branch; create a branch before pushing."
fi

# 2) No .env* access (only .env.example), via file tools or shell.
[[ -n "$path" ]] && is_env "$path" && block ".env files are off-limits. Use .env.example."
if [[ "$tool" == "Bash" ]]; then
  while read -r tok; do
    [[ -n "$tok" ]] && is_env "$tok" && block ".env files are off-limits (ask the human to run env setup)."
  done < <(grep -oE "[^[:space:]\"'=<>|;&()]*\.env[[:alnum:]_.-]*" <<<"$cmd")
fi

# 3) openapi.yaml is the frozen contract.
if [[ "$tool" =~ ^(Edit|Write|MultiEdit|NotebookEdit)$ && "$(basename -- "$path")" == "openapi.yaml" ]]; then
  block "openapi.yaml is the frozen contract. Ask the human."
fi
if [[ "$tool" == "Bash" && "$cmd" =~ (sed[[:space:]]+-i|>|tee|mv|cp|rm)[^\;\&\|]*openapi\.yaml ]]; then
  block "openapi.yaml is the frozen contract. Ask the human."
fi
exit 0
