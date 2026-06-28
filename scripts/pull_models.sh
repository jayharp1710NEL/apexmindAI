#!/usr/bin/env bash
# Pull 10 good free local models for ApexMind (via Ollama).
# Usage: bash scripts/pull_models.sh
# Big models need more RAM; comment out any your machine can't handle.
set -e

models=(
  "qwen2.5-coder:7b"      # best free local coder
  "qwen2.5-coder:3b"      # lighter coder (low RAM)
  "qwen2.5:7b"            # strong general
  "llama3.1"              # general
  "mistral:7b"            # general, fast
  "gemma2:9b"             # Google general
  "llama3.2:3b"           # fast / lightweight
  "phi3.5"                # tiny, decent
  "deepseek-r1:8b"        # reasoning + math
  "deepseek-coder-v2:16b" # bigger coder (~16GB RAM / GPU)
)

for m in "${models[@]}"; do
  echo "=== pulling $m ==="
  ollama pull "$m"
done

echo "Done. They will appear in the Chat model dropdown automatically."
