"""Best-workspace checkpointing: keep the good, discard the bad."""
import shutil
from pathlib import Path

from edgelab import docker_env

BEST_WS = Path("outputs/best_workspace")


def snapshot_best():
    if BEST_WS.exists():
        shutil.rmtree(BEST_WS)
    shutil.copytree(docker_env.WORKSPACE, BEST_WS,
                    ignore=shutil.ignore_patterns("__pycache__"))


def restore_best():
    if not BEST_WS.exists():
        return False
    for p in docker_env.WORKSPACE.glob("*"):
        if p.name == "__pycache__":
            continue
        shutil.rmtree(p) if p.is_dir() else p.unlink()
    for p in BEST_WS.glob("*"):
        dst = docker_env.WORKSPACE / p.name
        shutil.copytree(p, dst) if p.is_dir() else shutil.copy2(p, dst)
    return True
