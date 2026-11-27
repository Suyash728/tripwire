#!/usr/bin/env bash
# Deterministic demo-path check. Usage: API=http://localhost:8787 bash scripts/smoke_demo.sh [--privacy]
set -euo pipefail
API="${API:-http://localhost:8787}"
PRIV=false; [[ "${1:-}" == "--privacy" ]] && PRIV=true
echo "== health";  curl -fsS "$API/health"; echo
echo "== samples"; INPUT=$(curl -fsS "$API/samples" | jq -r '.data[0].input'); echo "$INPUT"
echo "== start run (privacy_mode=$PRIV)"
RID=$(curl -fsS -X POST "$API/runs" -H 'content-type: application/json' \
  -d "$(jq -n --arg i "$INPUT" --argjson p "$PRIV" '{input:$i, privacy_mode:$p}')" | jq -r .data.run_id)
echo "run_id=$RID"
for _ in $(seq 1 120); do
  S=$(curl -fsS "$API/runs/$RID" | jq -r '[.data.events[].status] | last')
  [[ "$S" == "interrupted" || "$S" == "error" ]] && break; sleep 1
done
curl -fsS "$API/runs/$RID" | jq -c '.data.events[] | {node,status,tier_used,ms,error}'
[[ "$S" == "interrupted" ]] || { echo "FAIL: graph did not reach approval"; exit 1; }
echo "== approve"; curl -fsS -X POST "$API/runs/$RID/resume" -H 'content-type: application/json' -d '{"approve":true}'; echo
for _ in $(seq 1 30); do
  R=$(curl -fsS "$API/runs/$RID" | jq -r '.data.state.result // empty'); [[ -n "$R" ]] && break; sleep 1
done
echo "result=$R"; [[ "$R" == "action executed" ]] && echo "SMOKE PASS" || { echo "SMOKE FAIL"; exit 1; }
