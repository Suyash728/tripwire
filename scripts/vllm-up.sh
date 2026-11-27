#!/usr/bin/env bash
# Tier 3 local model control. On the owner's desktop this delegates to the GPU-lease
# switcher in ~/AI (one model at a time, never pkill). Elsewhere it prints the raw command.
#   bash scripts/vllm-up.sh coding|vision|omni|stop|status
set -euo pipefail
SWITCH="${AI_DIR:-$HOME/AI}/scripts/switch_model.sh"
if [[ -x "$SWITCH" ]]; then exec "$SWITCH" "${1:-status}"; fi
case "${1:-coding}" in
  coding) M=nvidia/Qwen3-14B-NVFP4 ;; vision) M=nvidia/Qwen2.5-VL-7B-Instruct-NVFP4 ;;
  omni) M=nvidia/Phi-4-multimodal-instruct-NVFP4 ;; *) echo "usage: $0 coding|vision|omni"; exit 1 ;;
esac
echo "vllm serve $M --port 8001 --gpu-memory-utilization 0.80 --max-model-len 16384 --enable-auto-tool-choice --tool-call-parser hermes"
