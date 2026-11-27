#!/usr/bin/env bash
# Run the same checks as .github/workflows/ci.yml, in order; stops on the first failure.
# Usage: bash scripts/ci-local.sh [--no-e2e]
# Thresholds mirror the workflow's env block; override them the same way (e.g. COV_MIN=70).
set -euo pipefail

COV_MIN="${COV_MIN:-60}"
BANDIT_LEVEL="${BANDIT_LEVEL:--ll}"
NPM_AUDIT_LEVEL="${NPM_AUDIT_LEVEL:-high}"
RUN_E2E=1
[[ "${1:-}" == "--no-e2e" ]] && RUN_E2E=0

ROOT=$(cd "$(dirname "$0")/.." && pwd)
step() { printf '\n\033[1m== %s\033[0m\n' "$*"; }

step "guard: agent hook tests"
GUARD_REPO=$(mktemp -d)
trap 'rm -rf "$GUARD_REPO"' EXIT
git init -q -b ci-test "$GUARD_REPO"   # same as CI: independent of the branch you're on
CLAUDE_PROJECT_DIR="$GUARD_REPO" bash "$ROOT/scripts/test-guard.sh"
step "guard: Antigravity hook tests"
AGY_GUARD_REPO="$GUARD_REPO" bash "$ROOT/scripts/test-agy-guard.sh"

cd "$ROOT/backend"
step "backend: uv sync --frozen";  uv sync --frozen
step "backend: ruff";              uv run ruff check . && uv run ruff format --check .
step "backend: pytest (cov >= ${COV_MIN}%)"
uv run pytest -q --cov=app --cov-report=term-missing --cov-fail-under="$COV_MIN"
step "backend: bandit";            uv run bandit -q -r app "$BANDIT_LEVEL"
step "backend: pip-audit";         uv run pip-audit

cd "$ROOT/frontend"
step "frontend: npm ci";           npm ci --no-audit --no-fund
step "frontend: lint";             npm run lint
step "frontend: format";           npm run format:check
step "frontend: typecheck";        npm run typecheck
step "frontend: vitest";           npm run test:coverage
step "frontend: npm audit (${NPM_AUDIT_LEVEL}+)"; npm audit --audit-level="$NPM_AUDIT_LEVEL"
step "frontend: build";            npm run build

if (( RUN_E2E )); then
  step "e2e: Playwright demo path + axe (LLM_MOCK=1)"
  LLM_MOCK=1 npm run test:e2e
fi

cd "$ROOT"
if command -v gitleaks >/dev/null; then
  step "secrets: gitleaks";        gitleaks git --no-banner .
else
  step "secrets: gitleaks not installed locally (CI runs it); skipping"
fi

printf '\n\033[1;32mci-local: all checks passed\033[0m\n'
