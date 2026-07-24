"""The toolset the Solar coding-agent uses to solve the dabic task.

Files: read curated resources (task readme, starter, the two papers, even the
judge source), and read/write the deliverables in workspace/. Actions: run code
in the SimPEG WORK container, and `score` against the REAL judge.
"""
from __future__ import annotations
import json
from dataclasses import dataclass
from pathlib import Path

from edgelab import docker_env
from edgelab.store import Store

REPO_ROOT = Path(__file__).resolve().parent.parent
RESOURCES = REPO_ROOT / "resources"
WORKSPACE = REPO_ROOT / "workspace"

RESOURCE_FILES = {
    "task_README.md": "The full task spec (phases, deliverables, results.json schema, constraints).",
    "starter.py": "Provides mesh, m_true, rxLoc, sim_fwd, d_obs, sigma_per_pt. Import it; don't modify its model/data logic.",
    "paper_geo20250233.txt": "Song et al. 2025 — the D-ABIC method paper (data-space ABIC, logdet, adaptive beta). ~2500 lines.",
    "paper_Xu2025_HMC.txt": "Xu et al. 2025 — HMC benchmark + Vinton settings (grid, depth, density bounds, cap-rock depth ~150m).",
    "JUDGE_eval_dabic_v2.py": "The exact scorer. Read it to see what earns A/B/C/D/E/F points and the metric gates.",
}


@dataclass
class ToolCtx:
    store: Store
    turn: int
    last_score: dict


def _norm_out(rel: str) -> str:
    """Files live in workspace/ which IS the container's outputs/. Accept both
    'dabic_directive.py' and 'outputs/dabic_directive.py' -> same place."""
    rel = rel.strip().lstrip("/")
    for pre in ("outputs/", "./outputs/", "workspace/"):
        if rel.startswith(pre):
            rel = rel[len(pre):]
    return rel or "."


def _safe(base: Path, rel: str) -> Path:
    p = (base / _norm_out(rel)).resolve()
    if base not in p.parents and p != base:
        raise ValueError(f"path escapes {base.name}/")
    return p


def _lines(text: str, offset: int, limit: int | None) -> str:
    if offset <= 0 and not limit:
        return text
    ls = text.splitlines()
    seg = ls[offset: (offset + limit) if limit else None]
    return f"[lines {offset}..{offset + len(seg)} of {len(ls)}]\n" + "\n".join(seg)


TOOLS = [
    {"type": "function", "function": {
        "name": "read_resource",
        "description": "Read a reference file (task spec, starter, papers, judge source). "
                       "Big files: use offset/limit (lines) to page.",
        "parameters": {"type": "object", "properties": {
            "name": {"type": "string", "enum": list(RESOURCE_FILES)},
            "offset": {"type": "integer", "description": "start line (default 0)"},
            "limit": {"type": "integer", "description": "max lines (default all; use ~400 for papers)"},
        }, "required": ["name"]}}},
    {"type": "function", "function": {
        "name": "list_outputs",
        "description": "List the files you have written under outputs/ (the deliverables dir).",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "read_output",
        "description": "Read one of your deliverable files under outputs/.",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string"}, "offset": {"type": "integer"}, "limit": {"type": "integer"},
        }, "required": ["path"]}}},
    {"type": "function", "function": {
        "name": "write_output",
        "description": "Create/overwrite a deliverable file. Use a BARE name — it lands in outputs/ "
                       "(e.g. path='dabic_directive.py'). In run_work, reference it as 'outputs/dabic_directive.py'. "
                       "A leading 'outputs/' in the path is accepted and ignored (no nesting).",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string"}, "content": {"type": "string"},
        }, "required": ["path", "content"]}}},
    {"type": "function", "function": {
        "name": "run_work",
        "description": "Run a shell command in the SimPEG WORK container (cwd=task dir, your files at outputs/). "
                       "Use to test/debug and to generate results.json, e.g. 'python outputs/run_synthetic.py'. "
                       "Heavy inversions are slow under emulation — set a generous timeout.",
        "parameters": {"type": "object", "properties": {
            "cmd": {"type": "string"},
            "timeout": {"type": "integer", "description": "seconds (default 1800)"},
        }, "required": ["cmd"]}}},
    {"type": "function", "function": {
        "name": "score",
        "description": "Run the REAL judge on your current outputs/ and get the 0-100 score with the "
                       "A-F component breakdown, per-component messages, and diagnostic flags "
                       "(is_data_space, beta_truly_updated, uses_proper_logdet). Records a submission.",
        "parameters": {"type": "object", "properties": {}}}},
]


def dispatch(name: str, args: dict, ctx: ToolCtx) -> dict:
    try:
        if name == "read_resource":
            fn = args["name"]
            text = (RESOURCES / fn).read_text(errors="replace")
            return {"content": _lines(text, args.get("offset", 0), args.get("limit"))}

        if name == "list_outputs":
            WORKSPACE.mkdir(parents=True, exist_ok=True)
            files = [str(p.relative_to(WORKSPACE)) for p in sorted(WORKSPACE.rglob("*")) if p.is_file()]
            return {"files": files or ["(empty)"]}

        if name == "read_output":
            p = _safe(WORKSPACE, args["path"])
            if not p.exists():
                return {"error": f"{args['path']} does not exist yet"}
            return {"content": _lines(p.read_text(errors="replace"), args.get("offset", 0), args.get("limit"))}

        if name == "write_output":
            p = _safe(WORKSPACE, args["path"])
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(args["content"])
            return {"ok": True, "bytes": len(args["content"]), "path": args["path"]}

        if name == "run_work":
            r = docker_env.run_in_work(args["cmd"], timeout=args.get("timeout", 1800))
            return r

        if name == "score":
            result = docker_env.run_judge()
            ctx.store.add_submission(turn=ctx.turn, result=result)
            compact = _compact_score(result)
            ctx.last_score.clear(); ctx.last_score.update(compact)
            return compact

        return {"error": f"unknown tool {name}"}
    except Exception as e:  # never crash the loop on a tool error
        return {"error": f"{type(e).__name__}: {e}"}


def _compact_score(result: dict) -> dict:
    """Trim the judge's big JSON to the signal the agent needs."""
    if "error" in result and "score" not in result:
        return result
    comps = {}
    for d in result.get("details", []):
        comps[d.get("name", "?")] = {"status": d.get("status"), "msg": (d.get("message") or "")[:400]}
    m = result.get("metrics", {})
    keep = {k: m[k] for k in (
        "tier_name", "is_data_space", "beta_truly_updated", "uses_proper_logdet", "uses_bad_det",
        "structural_penalty", "penalty_reason", "n_unique_beta_orders") if k in m}
    return {"score": result.get("score"), "summary": result.get("summary"),
            "components": comps, "metrics": keep}
