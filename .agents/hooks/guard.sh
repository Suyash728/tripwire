#!/bin/bash
# Antigravity CLI PreToolUse guard (registered in .agents/hooks.json). Same rules as .claude/hooks/guard.sh.
# Contract (https://antigravity.google/docs/hooks?tab=cli): stdin JSON has toolCall.name + toolCall.args;
# reply on stdout with {"decision":"allow"|"deny","reason":...} and exit 0. Needs jq + git.
input=$(cat)
tool=$(jq -r '.toolCall.name // ""' <<<"$input")
cmd=$(jq -r '.toolCall.args.CommandLine // ""' <<<"$input")
path=$(jq -r '.toolCall.args | (.AbsolutePath // .TargetFile // .SearchPath // "")' <<<"$input")
repo=${AGY_GUARD_REPO:-$(jq -r '.toolCall.args.Cwd // .workspacePaths[0] // "."' <<<"$input")}

decide() { jq -cn --arg d "$1" --arg r "$2" 'if $r == "" then {decision: $d} else {decision: $d, reason: $r} end'; exit 0; }
block() { decide deny "Blocked: $1"; }
is_env() { local b; b=$(basename -- "$1"); [[ "$b" == .env* && "$b" != ".env.example" ]]; }

# 1) No pushes to main/master: explicit target, or a plain push while on main.
if [[ "$tool" == "run_command" && "$cmd" =~ (^|[;&|[:space:]])git[[:space:]]+push ]]; then
  [[ "$cmd" =~ [[:space:]:+](main|master)([[:space:]]|$) ]] && block "no direct push to main. Push a branch."
  branch=$(git -C "$repo" branch --show-current 2>/dev/null)
  [[ "$branch" == "main" || "$branch" == "master" ]] && block "you are on $branch; create a branch before pushing."
fi

# 2) No .env* access (only .env.example), via file tools or shell.
[[ -n "$path" ]] && is_env "$path" && block ".env files are off-limits. Use .env.example."
if [[ "$tool" == "run_command" ]]; then
  while read -r tok; do
    [[ -n "$tok" ]] && is_env "$tok" && block ".env files are off-limits (ask the human to run env setup)."
  done < <(grep -oE "[^[:space:]\"'=<>|;&()]*\.env[[:alnum:]_.-]*" <<<"$cmd")
fi

# 3) openapi.yaml is the frozen contract.
if [[ "$tool" =~ ^(write_to_file|replace_file_content|multi_replace_file_content)$ && "$(basename -- "$path")" == "openapi.yaml" ]]; then
  block "openapi.yaml is the frozen contract. Ask the human."
fi
if [[ "$tool" == "run_command" && "$cmd" =~ (sed[[:space:]]+-i|>|tee|mv|cp|rm)[^\;\&\|]*openapi\.yaml ]]; then
  block "openapi.yaml is the frozen contract. Ask the human."
fi
decide allow ""
