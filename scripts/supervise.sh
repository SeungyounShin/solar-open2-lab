#!/usr/bin/env bash
# Auto-resume supervisor for the dabic self-improving loop.
#
# The emulated SimPEG + judge containers occasionally get OOM-killed (SIGKILL)
# on a laptop. State is durable (outputs/dabic.sqlite + workspace/), so we just
# relaunch: each run resumes from the best-so-far and continues turn numbering.
# Short chunks keep per-process memory from creeping.
#
# Run:   bash scripts/supervise.sh        (stop with Ctrl-C / TaskStop)
set -u
cd "$(dirname "$0")/.."
export PATH="/opt/homebrew/bin:$PATH"

CHUNK_MIN="${CHUNK_MIN:-30}"
EFFORT="${EFFORT:-medium}"

i=0
while true; do
  i=$((i + 1))
  echo "=== [supervisor] launch #$i $(date '+%F %T') (chunk=${CHUNK_MIN}m effort=${EFFORT}) ==="
  # free memory from any stray containers before starting
  cids=$(docker ps -q 2>/dev/null); [ -n "$cids" ] && docker kill $cids >/dev/null 2>&1 || true
  .venv/bin/python -u run_dabic.py --minutes "$CHUNK_MIN" --effort "$EFFORT"
  code=$?
  echo "=== [supervisor] run #$i exited code=$code $(date '+%F %T') ==="
  sleep 5
done
