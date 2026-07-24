"""The 24/7 self-improving loop around the REAL dabic judge.

Each turn Solar edits the deliverables and scores against the real judge; we keep
the best-across-submissions (EdgeBench's rule), print the climbing curve, and
periodically compress history into `lessons` so context stays bounded forever.
"""
from __future__ import annotations
import json
import time

from solar import get_client, DEFAULT_MODEL
from edgelab import agent, docker_env
from edgelab.store import Store
from edgelab.tools import _compact_score

SUMMARIZE_EVERY = 6


def _summarize_lessons(store: Store, model: str | None) -> str:
    rows = store.recent(limit=10)
    digest = [{"turn": r["turn"], "score": r["score"], "summary": (r["summary"] or "")[:200]}
              for r in rows]
    client = get_client()
    prompt = (
        "You are keeping a running lab notebook for a D-ABIC gravity-inversion agent.\n"
        "Given recent judge results, write <=8 terse bullet lessons: what raised the score, "
        "what broke components (import errors, non-data-space, bad logdet, beta not updating, "
        "results.json schema, Vinton settings), and what to try next. Bullets only.\n\n"
        f"Recent:\n{json.dumps(digest, ensure_ascii=False)}"
    )
    r = client.chat.completions.create(
        model=model or DEFAULT_MODEL, messages=[{"role": "user", "content": prompt}],
        max_tokens=4000, reasoning_effort="low", temperature=0.3)
    return (r.choices[0].message.content or "").strip()


def run(*, db="outputs/dabic.sqlite", minutes=None, max_turns=1000,
        model=None, effort="high"):
    if not docker_env.images_present():
        raise SystemExit(
            "dabic images not found. Pull them first:\n"
            f"  docker pull --platform linux/amd64 {docker_env.WORK_IMAGE}\n"
            f"  docker pull --platform linux/amd64 {docker_env.JUDGE_IMAGE}")

    store = Store(db)
    deadline = time.time() + minutes * 60 if minutes else None
    best_row = store.best()
    best = best_row["score"] if best_row else 0.0
    # Resume: carry the champion's feedback into turn 1 so we build on it, not restart.
    last_score: dict = {}
    if best_row:
        try:
            last_score = _compact_score(json.loads(best_row["result_json"]))
        except Exception:
            pass
    lessons = store.get_lessons()

    print(f"=== dabic self-improving loop (model={model or DEFAULT_MODEL}, effort={effort}) ===")
    print(f"    starting best={best:.1f}/100, prior submissions={store.count()}")

    turn = 0
    while turn < max_turns and (deadline is None or time.time() < deadline):
        turn += 1
        t0 = time.time()
        print(f"\n--- turn {turn} (elapsed {int(time.time()-t0)}s) ---")
        out = agent.run_turn(store=store, turn=turn, last_score=last_score,
                             lessons=lessons, best_score=best, model=model, effort=effort)
        last_score = out["last_score"] or last_score

        # Safety net: guarantee one graded submission per turn even if the agent
        # spent all its steps editing/debugging and forgot to call `score`.
        if not out["scored"]:
            print("    [auto-score] agent didn't score; running judge on current outputs/")
            result = docker_env.run_judge()
            store.add_submission(turn=turn, result=result)
            last_score = _compact_score(result)
            print(f"    [auto-score] {result.get('score')}/100  {str(result.get('summary'))[:70]}")

        row = store.best()
        new_best = row["score"] if row else 0.0
        arrow = " ⬆" if new_best > best + 1e-9 else ""
        best = new_best
        dt = int(time.time() - t0)
        cur = last_score.get("score")
        print(f"    turn {turn}: scored={out['scored']} this={cur} best={best:.1f}/100{arrow} "
              f"({out['steps']} steps, {out['calls']} calls, {dt}s)")

        if turn % SUMMARIZE_EVERY == 0:
            try:
                lessons = _summarize_lessons(store, model)
                store.set_lessons(lessons)
                print(f"    [lessons updated]")
            except Exception as e:
                print(f"    [lessons skip: {e}]")

    print(f"\n=== done. best={best:.1f}/100 over {store.count()} submissions ===")
    return best
