"""Print the self-improving score curve + the champion's component breakdown.

Usage:  python dashboard.py [--db outputs/dabic.sqlite]
"""
import argparse
import json

from edgelab.store import Store

SPARK = "▁▂▃▄▅▆▇█"


def sparkline(vals, lo=0.0, hi=100.0):
    if not vals:
        return ""
    return "".join(SPARK[min(len(SPARK) - 1, int((v - lo) / (hi - lo) * (len(SPARK) - 1)))]
                   for v in vals)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="outputs/dabic.sqlite")
    a = ap.parse_args()
    store = Store(a.db)

    curve = store.curve()
    if not curve:
        print("No submissions yet."); return

    best_so_far = [c[2] for c in curve]
    per_sub = [c[1] for c in curve]
    print(f"submissions: {len(curve)}")
    print(f"best-so-far : {sparkline(best_so_far)}  -> {best_so_far[-1]:.1f}/100")
    print(f"per-submit  : {sparkline(per_sub)}")

    row = store.best()
    print(f"\n champion (submission #{row['id']}, turn {row['turn']}): {row['score']:.1f}/100")
    for k in ("A", "B", "C", "D", "E", "F"):
        v = row[k]
        print(f"   {k}: {v if v is not None else '—'}")
    print(f"   summary: {row['summary']}")


if __name__ == "__main__":
    main()
