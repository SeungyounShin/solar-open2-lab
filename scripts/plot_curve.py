"""Render the self-improving learning curve for the dabic run -> assets/dabic_curve.png.

Score vs elapsed wall-clock time (EdgeBench-style): faint per-submission dots +
the best-so-far envelope, annotated with the current best and A-F breakdown.
Regenerate anytime; the run's SQLite store is the single source of truth.
"""
import argparse
import sqlite3
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def load(db):
    c = sqlite3.connect(db)
    rows = c.execute("SELECT ts, score, A, B, C, D, E, F FROM submissions ORDER BY id").fetchall()
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="outputs/dabic.sqlite")
    ap.add_argument("--out", default="assets/dabic_curve.png")
    a = ap.parse_args()

    rows = load(a.db)
    if not rows:
        print("no submissions yet"); return

    t0 = rows[0][0]
    hrs = [(r[0] - t0) / 3600.0 for r in rows]
    scores = [r[1] for r in rows]
    best, cur = [], -1.0
    for s in scores:
        cur = max(cur, s); best.append(cur)

    best_i = max(range(len(rows)), key=lambda i: rows[i][1])
    comp = {k: rows[best_i][i] for i, k in enumerate("ABCDEF", start=2)}
    peak = scores[best_i]

    plt.rcParams.update({"font.size": 11, "figure.dpi": 130})
    fig, ax = plt.subplots(figsize=(8, 4.6))
    ax.scatter(hrs, scores, s=22, color="#c0392b", alpha=0.35, label="each submission", zorder=2)
    ax.plot(hrs, best, color="#c0392b", lw=2.4, marker="o", ms=3.5,
            label="best-so-far", zorder=3)
    ax.fill_between(hrs, 0, best, color="#c0392b", alpha=0.06)

    ax.set_title("solar-open2 self-improving on EdgeBench\n"
                 "dabic_gravity_inversion — scored by the real judge", fontsize=12, loc="left")
    ax.set_xlabel("elapsed wall-clock time (hours)")
    ax.set_ylabel("judge score (/100)")
    ax.set_ylim(0, max(20, peak * 1.35))
    ax.set_xlim(0, max(0.5, hrs[-1] * 1.02))
    ax.grid(True, alpha=0.25)
    ax.legend(loc="lower right", frameon=False, fontsize=9)

    txt = (f"best = {peak:.1f}/100   ({len(rows)} submissions)\n"
           f"A {comp['A'] or 0:.0f} · B {comp['B'] or 0:.1f} · C {comp['C'] or 0:.1f} · "
           f"D {comp['D'] or 0:.1f} · E {comp['E'] or 0:.1f} · F {comp['F'] or 0:.0f}")
    ax.text(0.02, 0.97, txt, transform=ax.transAxes, va="top", fontsize=9,
            bbox=dict(boxstyle="round,pad=0.4", fc="#fbeae7", ec="#c0392b", alpha=0.9))

    fig.tight_layout()
    import os
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    fig.savefig(a.out)
    print(f"wrote {a.out}: best={peak:.1f}/100 over {len(rows)} submissions, {hrs[-1]:.2f}h")


if __name__ == "__main__":
    main()
