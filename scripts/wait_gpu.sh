#!/usr/bin/env bash
# Wait until GPU-1 looks free enough for a Photo-SLAM / GS job.
# Default: free >= 40000 MiB and util <= 5% for STABLE consecutive samples.
set -euo pipefail

GPU_INDEX="${GPU_INDEX:-1}"
MIN_FREE_MIB="${MIN_FREE_MIB:-40000}"
MAX_UTIL="${MAX_UTIL:-5}"
STABLE="${STABLE:-3}"
POLL_S="${POLL_S:-30}"
LOG="${LOG:-/tmp/wait_gpu${GPU_INDEX}.log}"

ok=0
echo "$(date -Is) waiting on GPU-${GPU_INDEX}: free>=${MIN_FREE_MIB}MiB util<=${MAX_UTIL}% x${STABLE}" | tee -a "$LOG"
while true; do
  read -r free util < <(nvidia-smi -i "$GPU_INDEX" \
    --query-gpu=memory.free,utilization.gpu --format=csv,noheader,nounits \
    | tr -d ' ')
  echo "$(date -Is) GPU-${GPU_INDEX} free=${free}MiB util=${util}%" | tee -a "$LOG"
  if (( free >= MIN_FREE_MIB && util <= MAX_UTIL )); then
    ok=$((ok + 1))
    echo "  consecutive ok ${ok}/${STABLE}" | tee -a "$LOG"
    if (( ok >= STABLE )); then
      echo "$(date -Is) GPU-${GPU_INDEX} ready" | tee -a "$LOG"
      exit 0
    fi
  else
    ok=0
  fi
  sleep "$POLL_S"
done
