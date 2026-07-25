"""One long agentic episode: a single continuous ReAct conversation.

Unlike the old per-turn design (rebuild [system,user] every 20 steps, compress
every 6 turns), this keeps ONE growing conversation for the whole run:
reason -> act (tools) -> observe -> ... -> score -> keep going. The system
prompt stays a stable prefix (KV-cache friendly), and we only compact the middle
when the real prompt-token count approaches the context budget — not on a fixed
cadence. `score` is just another tool the agent calls when it wants feedback.
"""
from __future__ import annotations
import json
import time
from pathlib import Path

from solar import get_client, DEFAULT_MODEL, reasoning_tokens
from edgelab import prompts, checkpoint
from edgelab.tools import TOOLS, dispatch, ToolCtx, _compact_score


def _kickoff(best: float, last_score: dict, lessons: str) -> str:
    s = [f"You are resuming a long self-improving session. Best score so far: {best:.1f}/100."]
    if last_score:
        s.append("Latest judge feedback:\n" + json.dumps(
            {k: last_score.get(k) for k in ("score", "summary", "components", "metrics")},
            ensure_ascii=False)[:2500])
    if lessons:
        s.append("Lessons carried over:\n" + lessons)
    s.append("Inspect outputs/ (list_outputs) and the latest results, then keep improving the "
             "weakest scoring component. Edit -> run_work to test -> `score` after meaningful "
             "changes. Work continuously; don't stop until told.")
    return "\n\n".join(s)


def _approx_msg_text(messages) -> str:
    out = []
    for m in messages:
        out.append(str(m.get("content") or ""))
        for tc in m.get("tool_calls", []) or []:
            out.append(json.dumps(tc.get("function", {})))
    return "\n".join(out)


def _compact(messages, client, model, keep_tail=8) -> list:
    """Summarize the middle of the conversation, keep system prefix + recent tail."""
    system = messages[0]
    middle, tail = messages[1:-keep_tail], messages[-keep_tail:]
    if not middle:
        return messages
    dump = _approx_msg_text(middle)[-14000:]
    r = client.chat.completions.create(
        model=model, max_tokens=2000, reasoning_effort="low", temperature=0.2,
        messages=[{"role": "user", "content":
                   "Compress this agent work-log into a concrete state note: current best, what is "
                   "implemented in each file, which SimPEG APIs/approaches worked vs failed, and the "
                   "next concrete step. <=350 words.\n\n" + dump}])
    summary = (r.choices[0].message.content or "").strip()
    return [system, {"role": "user", "content": "[earlier context compacted]\n" + summary}, *tail]


def run_episode(store, *, minutes=30, model=None, effort="medium", max_tokens=32000,
                ctx_budget=90000, traj_dir="outputs/trajectories", nudge_after=3):
    client = get_client()
    model = model or DEFAULT_MODEL
    ctx = ToolCtx(store=store, turn=0, last_score={})

    row = store.best()
    best = row["score"] if row else 0.0
    last_score = {}
    if row:
        try:
            last_score = _compact_score(json.loads(row["result_json"]))
        except Exception:
            pass
    lessons = store.get_lessons()

    messages = [
        {"role": "system", "content": prompts.SYSTEM},
        {"role": "user", "content": _kickoff(best, last_score, lessons)},
    ]
    deadline = time.time() + minutes * 60
    ep_id = store.max_turn() + 1
    step = 0
    since_score = 0
    reason_tok = 0

    print(f"=== episode {ep_id} (model={model}, effort={effort}, budget={minutes}m, "
          f"start best={best:.1f}) ===")

    while time.time() < deadline:
        step += 1
        resp = client.chat.completions.create(
            model=model, messages=messages, tools=TOOLS,
            temperature=0.4, max_tokens=max_tokens, reasoning_effort=effort)
        reason_tok += reasoning_tokens(resp)
        usage = resp.usage
        choice = resp.choices[0]
        msg = choice.message

        if choice.finish_reason == "tool_calls" and msg.tool_calls:
            messages.append({"role": "assistant", "content": msg.content or "",
                             "tool_calls": [tc.model_dump() for tc in msg.tool_calls]})
            for tc in msg.tool_calls:
                name = tc.function.name
                try:
                    args = json.loads(tc.function.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}
                result = dispatch(name, args, ctx)
                if name == "score":
                    since_score = 0
                    r2 = store.best(); nb = r2["score"] if r2 else 0.0
                    up = ""
                    if nb > best + 1e-9:
                        best = nb; up = " ⬆"
                        try:
                            checkpoint.snapshot_best()
                        except Exception:
                            pass
                    print(f"  step {step} [score] {result.get('score')}/100  best={best:.1f}{up}")
                elif name in ("write_output", "run_work"):
                    print(f"  step {step} [{name}] {result.get('path') or 'exit='+str(result.get('exit'))}")
                messages.append({"role": "tool", "tool_call_id": tc.id,
                                 "content": json.dumps(result)[:12000]})
        else:
            messages.append({"role": "assistant", "content": msg.content or ""})
            since_score += 1
            left = int((deadline - time.time()) / 60)
            nudge = ("Call `score` now to get fresh judge feedback, then fix the weakest component."
                     if since_score >= nudge_after else
                     "Keep going — edit/test the next improvement, then score.")
            messages.append({"role": "user", "content": f"{nudge} (~{left} min left this session.)"})

        # cache-friendly compaction: only when the real prompt is near the budget
        if usage and getattr(usage, "prompt_tokens", 0) > ctx_budget:
            before = usage.prompt_tokens
            messages = _compact(messages, client, model)
            print(f"  step {step} [compact] prompt {before} tok -> summarized middle")

        _save(traj_dir, ep_id, model, messages, step, best, reason_tok)

    print(f"=== episode {ep_id} done: {step} steps, best={best:.1f}/100, "
          f"reasoning_tokens≈{reason_tok} ===")
    return best


def _save(traj_dir, ep_id, model, messages, step, best, reason_tok):
    d = Path(traj_dir); d.mkdir(parents=True, exist_ok=True)
    rec = {"episode": ep_id, "model": model, "steps": step, "best": best,
           "reasoning_tokens": reason_tok, "messages": messages}
    (d / f"episode_{ep_id:04d}.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1))
