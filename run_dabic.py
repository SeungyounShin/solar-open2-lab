"""Entrypoint: run the Solar self-improving loop on the real EdgeBench dabic task.

Prereqs (one-time):
  1. A Docker runtime (e.g. `colima start --vm-type vz --vz-rosetta`).
  2. Pull the public task images:
       docker pull --platform linux/amd64 seededge/edgebench.work.dabic_gravity_inversion:85db0aba8a5f
       docker pull --platform linux/amd64 seededge/edgebench.judge.dabic_gravity_inversion:517eb738b87b
  3. Put the D-ABIC/Xu paper texts + task README + starter.py in resources/ (extract from the
     work image — see README). These are copyrighted; they are gitignored, never committed.
  4. UPSTAGE_API_KEY in .env.

Usage:
  python run_dabic.py --minutes 720          # 12-hour EdgeBench-style run
  python run_dabic.py --max-turns 3          # quick smoke test
"""
import argparse
from edgelab.harness import run

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="outputs/dabic.sqlite")
    ap.add_argument("--minutes", type=float, default=None, help="wall-clock budget")
    ap.add_argument("--max-turns", type=int, default=1000)
    ap.add_argument("--model", default=None, help="override SOLAR_MODEL (default solar-open2)")
    ap.add_argument("--effort", default="high", choices=["low", "medium", "high"])
    a = ap.parse_args()
    run(db=a.db, minutes=a.minutes, max_turns=a.max_turns, model=a.model, effort=a.effort)
