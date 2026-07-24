"""The Solar coding-agent: one improvement turn = a bounded tool-calling loop."""
from __future__ import annotations
import json

from solar import get_client, DEFAULT_MODEL
from edgelab import prompts
from edgelab.tools import TOOLS, dispatch, ToolCtx


def run_turn(*, store, turn: int, last_score: dict, lessons: str, best_score: float,
             model: str | None = None, effort: str = "high", max_steps: int = 14,
             max_tokens: int = 32000) -> dict:
    """Drive Solar through one improvement turn. Returns {scored, steps, calls}."""
    client = get_client()
    ctx = ToolCtx(store=store, turn=turn, last_score=dict(last_score))
    messages = [
        {"role": "system", "content": prompts.SYSTEM},
        {"role": "user", "content": prompts.turn_prompt(turn, last_score, lessons, best_score)},
    ]
    scored = False
    calls = 0
    for step in range(max_steps):
        resp = client.chat.completions.create(
            model=model or DEFAULT_MODEL, messages=messages, tools=TOOLS,
            temperature=0.4, max_tokens=max_tokens, reasoning_effort=effort,
        )
        choice = resp.choices[0]
        msg = choice.message
        if choice.finish_reason != "tool_calls" or not msg.tool_calls:
            # agent chose to stop talking; end the turn
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
    return {"scored": scored, "steps": step + 1, "calls": calls, "last_score": ctx.last_score}
