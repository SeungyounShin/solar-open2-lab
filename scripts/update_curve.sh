#!/usr/bin/env bash
# Keep the README learning curve fresh: every INTERVAL seconds, regenerate the
# PNG from the run store and push it — but only when it actually changed (i.e.
# when a new submission moved the curve). Uses stored git creds (no token here).
#
# Run:   bash scripts/update_curve.sh     (stop with Ctrl-C / TaskStop)
set -u
cd "$(dirname "$0")/.."
export PATH="/opt/homebrew/bin:$PATH"
INTERVAL="${INTERVAL:-1200}"     # 20 min

while true; do
  .venv/bin/python scripts/plot_curve.py >/dev/null 2>&1 || true
  if [ -n "$(git status --porcelain -- assets/dabic_curve.png)" ]; then
    best=$(.venv/bin/python -c "from edgelab.store import Store; s=Store('outputs/dabic.sqlite'); r=s.best(); print(round(r['score'],1) if r else 0)" 2>/dev/null || echo "?")
    git add assets/dabic_curve.png
    git -c user.name="SeungyounShin" -c user.email="logan@upstage.ai" \
        commit -q -m "chore: update learning curve (best=${best}/100)"
    git push -q && echo "[curve] pushed best=${best} $(date '+%F %T')"
  else
    echo "[curve] no change $(date '+%F %T')"
  fi
  sleep "$INTERVAL"
done
