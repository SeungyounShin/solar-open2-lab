"""Docker orchestration for the real EdgeBench dabic task.

Two images (public on Docker Hub under `seededge`, linux/amd64):
  - WORK  : SimPEG environment + task (starter/, data/, docs/) — runs the agent's code
  - JUDGE : hidden evaluator + hidden scenarios — produces the real 0-100 score

The agent's deliverables live in a host directory (`workspace/`) that we bind-mount
into each container at `<task>/outputs`, so edits persist and both containers see them.
"""
from __future__ import annotations
import json
import subprocess
from pathlib import Path

WORK_IMAGE = "seededge/edgebench.work.dabic_gravity_inversion:85db0aba8a5f"
JUDGE_IMAGE = "seededge/edgebench.judge.dabic_gravity_inversion:517eb738b87b"
TASK_DIR = "/home/workspace/dabic_gravity_vinton"
OUT_MOUNT = TASK_DIR + "/outputs"

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKSPACE = REPO_ROOT / "workspace"      # host dir == the agent's outputs/
PLATFORM = "linux/amd64"


def _docker(args: list[str], timeout: float) -> subprocess.CompletedProcess:
    return subprocess.run(["docker", *args], capture_output=True, text=True, timeout=timeout)


def run_in_work(cmd: str, *, timeout: float = 1800, as_root: bool = True) -> dict:
    """Run a shell command inside the WORK container (SimPEG env).

    `workspace/` is mounted at outputs/. cwd is the task dir, so the agent's
    scripts can `import` starter and read data/ + docs/ from the image.
    """
    WORKSPACE.mkdir(parents=True, exist_ok=True)
    args = ["run", "--rm", "--platform", PLATFORM,
            "-v", f"{WORKSPACE}:{OUT_MOUNT}",
            "-w", TASK_DIR]
    if as_root:
        args += ["--user", "0"]
    args += ["--entrypoint", "bash", WORK_IMAGE, "-lc", cmd]
    try:
        p = _docker(args, timeout)
        return {"exit": p.returncode, "stdout": p.stdout[-8000:], "stderr": p.stderr[-4000:],
                "timed_out": False}
    except subprocess.TimeoutExpired as e:
        return {"exit": -1, "stdout": (e.stdout or "")[-4000:] if isinstance(e.stdout, str) else "",
                "stderr": f"TIMEOUT after {timeout}s", "timed_out": True}


def run_judge(*, timeout: float = 3600) -> dict:
    """Run the real JUDGE on the current workspace/ and return the parsed result.

    Returns the evaluator's structured JSON (score, per-component A-F breakdown,
    metrics like is_data_space / beta_truly_updated / uses_proper_logdet), or
    {"error": ...} if it could not be produced/parsed.
    """
    WORKSPACE.mkdir(parents=True, exist_ok=True)
    cmd = (f"cd {TASK_DIR} && PYTHONPATH=/opt/evaluator "
           f"python /opt/evaluator/eval_dabic_v2.py ./outputs/")
    args = ["run", "--rm", "--platform", PLATFORM,
            "-v", f"{WORKSPACE}:{OUT_MOUNT}",
            "--entrypoint", "bash", JUDGE_IMAGE, "-lc", cmd]
    try:
        p = _docker(args, timeout)
    except subprocess.TimeoutExpired:
        return {"error": f"judge timed out after {timeout}s", "score": 0.0}

    out = p.stdout
    start = out.find(">>>>> Start Structured Result")
    end = out.find(">>>>> End Structured Result")
    if start == -1 or end == -1:
        return {"error": "no structured result", "raw": (out or p.stderr)[-2000:], "score": 0.0}
    blob = out[start + len(">>>>> Start Structured Result"):end].strip()
    try:
        return json.loads(blob)
    except json.JSONDecodeError:
        return {"error": "unparseable structured result", "raw": blob[:2000], "score": 0.0}


def images_present() -> bool:
    p = _docker(["images", "-q", WORK_IMAGE], timeout=30)
    j = _docker(["images", "-q", JUDGE_IMAGE], timeout=30)
    return bool(p.stdout.strip()) and bool(j.stdout.strip())
