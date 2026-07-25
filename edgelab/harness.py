"""Run driver: one long agentic episode per invocation.

The supervisor calls this repeatedly (short chunks that survive OOM). Each call
resumes from the best-known workspace + the store, then runs a single continuous
episode (see episode.py). State is durable, so progress accumulates across
restarts even though each process is short-lived.
"""
from __future__ import annotations
import time

from solar import DEFAULT_MODEL
from edgelab import docker_env, checkpoint
from edgelab.episode import run_episode
from edgelab.store import Store


def run(*, db="outputs/dabic.sqlite", minutes=30, max_turns=None,
        model=None, effort="medium"):
    if not docker_env.images_present():
        raise SystemExit(
            "dabic images not found. Pull them:\n"
            f"  docker pull --platform linux/amd64 {docker_env.WORK_IMAGE}\n"
            f"  docker pull --platform linux/amd64 {docker_env.JUDGE_IMAGE}")

    store = Store(db)
    row = store.best()
    best = row["score"] if row else 0.0

    # Resume from the best-known files (a prior episode may have died mid-regression).
    if checkpoint.restore_best():
        print(f"[resume] restored best workspace (best={best:.1f}/100)")

    print(f"=== dabic self-improving (model={model or DEFAULT_MODEL}, effort={effort}) "
          f"start best={best:.1f}/100, prior submissions={store.count()} ===")

    run_episode(store, minutes=minutes or 30, model=model, effort=effort)

    final = store.best()
    print(f"=== chunk done. best={final['score']:.1f}/100 over {store.count()} submissions ===")
    return final["score"]
