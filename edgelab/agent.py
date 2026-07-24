"""The Solar coding-agent: one improvement turn = a bounded tool-calling loop.

Every turn (episode) is saved as an OpenAI chat-format trajectory: the full
messages array (system, user, assistant+tool_calls, tool results, final
assistant) exactly as the model saw it — one JSON per episode plus a JSONL
aggregate — so runs are replayable / usable as SFT/RL data.
"""
from __future__ import annotations
import json
import time
from pathlib import Path


from solar import get_client, DEFAULT_MODEL
from edgelab import prompts
from edgelab.tools import TOOLS, dispatch, ToolCtx


def _save_trajectory(traj_dir: str, turn: int, model: str, messages: list,
                     meta: dict) -> str:
    d = Path(traj_dir)
    d.mkdir(parents=True, exist_ok=True)
    record = {
        "turn": turn,
        "model": model,
        "ts": time.time(),
        **meta,                     # scored / steps / calls / final_score
        "messages": messages,       # full OpenAI chat-format trajectory
        "tools": TOOLS,
    }
    path = d / f"turn_{turn:04d}.json"
    path.write_text(json.dumps(record, ensure_ascii=False, indent=1))
    with open(d / "episodes.jsonl", "a") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return str(path)


def run_turn(*, store, turn: int, last_score: dict, lessons: str, best_score: float,
             model: str | None = None, effort: str = "high", max_steps: int = 20,
             max_tokens: int = 32000, traj_dir: str | None = "outputs/trajectories") -> dict:
    """Drive Solar through one improvement turn. Returns {scored, steps, calls, ...}."""
    client = get_client()
    model = model or DEFAULT_MODEL
    ctx = ToolCtx(store=store, turn=turn, last_score=dict(last_score))
    messages = [
        {"role": "system", "content": prompts.SYSTEM},
        {"role": "user", "content": prompts.turn_prompt(turn, last_score, lessons, best_score)},
    ]
    scored = False
    calls = 0
    for step in range(max_steps):
        resp = client.chat.completions.create(
            model=model, messages=messages, tools=TOOLS,
            temperature=0.4, max_tokens=max_tokens, reasoning_effort=effort,
        )
        choice = resp.choices[0]
        msg = choice.message
        if choice.finish_reason != "tool_calls" or not msg.tool_calls:
            # agent chose to stop talking; record the closing message and end
            messages.append({"role": "assistant", "content": msg.content or ""})
            if msg.content:
                print(f"    [agent] {msg.content.strip()[:300]}")
            break
        messages.append({"role": "assistant", "content": msg.content or "",
                         "tool_calls": [tc.model_dump() for tc in msg.tool_calls]})
        for tc in msg.tool_calls:
            calls += 1
            name = tc.function.name
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            result = dispatch(name, args, ctx)
            if name == "score":
                scored = True
                print(f"    [score] {result.get('score')}/100  {str(result.get('summary'))[:80]}")
            elif name in ("write_output", "run_work"):
                tag = result.get("path") or f"exit={result.get('exit')}"
                print(f"    [{name}] {tag}")
            messages.append({"role": "tool", "tool_call_id": tc.id,
                             "content": json.dumps(result)[:12000]})

    meta = {"scored": scored, "steps": step + 1, "calls": calls,
            "final_score": ctx.last_score.get("score")}
    if traj_dir:
        try:
            p = _save_trajectory(traj_dir, turn, model, messages, meta)
            print(f"    [traj] saved {len(messages)} msgs -> {p}")
        except Exception as e:
            print(f"    [traj] save failed: {e}")
    return {**meta, "last_score": ctx.last_score}
