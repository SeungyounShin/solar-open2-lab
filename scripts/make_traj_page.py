"""Render a saved episode trajectory as a readable HTML page.

Usage:  python scripts/make_traj_page.py [--traj outputs/trajectories/episode_0009.json]
                                         [--out outputs/trajectory.html]

Shows, step by step, what the model actually did: its preserved chain-of-thought
(reasoning), the tool call it chose, and what came back — plus a flag when
consecutive steps repeat verbatim (a degenerate loop).
"""
import argparse
import html
import json
from pathlib import Path

CSS = """
:root{
  --paper:#EEF1F6; --surface:#FFFFFF; --edge:#D4DBE6;
  --ink:#131A26; --muted:#5A6577;
  --think:#6B4FBF; --think-bg:#F1EDFC;
  --act:#0E7C86;  --act-bg:#E6F4F5;
  --obs:#47546B;  --obs-bg:#EDF0F5;
  --warn:#B4531E; --warn-bg:#FBEDE4;
  --mono:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
  --serif:'Iowan Old Style',Georgia,'Times New Roman',serif;
  --ui:system-ui,-apple-system,'Segoe UI',sans-serif;
}
@media (prefers-color-scheme:dark){
  :root{
    --paper:#0C111A; --surface:#131B27; --edge:#26313F;
    --ink:#E4EAF2; --muted:#8A97AB;
    --think:#A48BF0; --think-bg:#1B1830;
    --act:#35BFC9;  --act-bg:#0E2226;
    --obs:#9AA8BE;  --obs-bg:#161E2A;
    --warn:#E08A4B; --warn-bg:#2A1B10;
  }
}
:root[data-theme="dark"]{
  --paper:#0C111A; --surface:#131B27; --edge:#26313F;
  --ink:#E4EAF2; --muted:#8A97AB;
  --think:#A48BF0; --think-bg:#1B1830;
  --act:#35BFC9;  --act-bg:#0E2226;
  --obs:#9AA8BE;  --obs-bg:#161E2A;
  --warn:#E08A4B; --warn-bg:#2A1B10;
}
:root[data-theme="light"]{
  --paper:#EEF1F6; --surface:#FFFFFF; --edge:#D4DBE6;
  --ink:#131A26; --muted:#5A6577;
  --think:#6B4FBF; --think-bg:#F1EDFC;
  --act:#0E7C86;  --act-bg:#E6F4F5;
  --obs:#47546B;  --obs-bg:#EDF0F5;
  --warn:#B4531E; --warn-bg:#FBEDE4;
}
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);font-family:var(--ui);line-height:1.55}
.wrap{max-width:900px;margin:0 auto;padding:0 20px 80px}

header.top{padding:44px 0 26px;border-bottom:1px solid var(--edge);margin-bottom:8px}
.eyebrow{font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:var(--muted);margin:0 0 10px}
h1{font-family:var(--serif);font-size:clamp(28px,4.4vw,42px);line-height:1.15;margin:0 0 6px;text-wrap:balance;font-weight:600}
.sub{color:var(--muted);margin:0;max-width:62ch}
.stats{display:flex;flex-wrap:wrap;gap:0;margin-top:26px;border:1px solid var(--edge);border-radius:8px;overflow:hidden;background:var(--surface)}
.stat{flex:1 1 130px;padding:12px 16px;border-right:1px solid var(--edge)}
.stat:last-child{border-right:0}
.stat b{display:block;font-family:var(--mono);font-size:19px;font-variant-numeric:tabular-nums;letter-spacing:-.01em}
.stat span{font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:var(--muted)}

.note{margin:26px 0 0;padding:14px 16px;border-left:3px solid var(--warn);background:var(--warn-bg);border-radius:0 6px 6px 0}
.note h2{font-size:14px;margin:0 0 4px;color:var(--warn);letter-spacing:.01em}
.note p{margin:0;font-size:14px;color:var(--ink)}

.timeline{margin-top:34px;display:flex;flex-direction:column;gap:18px}
.step{display:grid;grid-template-columns:52px 1fr;gap:14px;align-items:start}
.rail{position:relative;padding-top:2px;text-align:right}
.num{font-family:var(--mono);font-size:12px;color:var(--muted);font-variant-numeric:tabular-nums}
.card{background:var(--surface);border:1px solid var(--edge);border-radius:10px;overflow:hidden}
.card>.head{display:flex;align-items:center;gap:8px;padding:9px 14px;border-bottom:1px solid var(--edge)}
.tag{font-size:10.5px;letter-spacing:.1em;text-transform:uppercase;font-weight:650}
.who{font-size:12px;color:var(--muted);font-family:var(--mono)}
.body{padding:14px 16px}

.think .head{background:var(--think-bg)} .think .tag{color:var(--think)}
.think .body{font-family:var(--serif);font-size:15.5px;white-space:pre-wrap}
.act .head{background:var(--act-bg)} .act .tag{color:var(--act)}
.obs .head{background:var(--obs-bg)} .obs .tag{color:var(--obs)}
.say .head{background:transparent} .say .tag{color:var(--muted)}
.say .body{font-family:var(--serif);font-size:15.5px;white-space:pre-wrap}

code,pre{font-family:var(--mono)}
pre{margin:0;font-size:12.5px;line-height:1.5;overflow-x:auto;white-space:pre;
    background:transparent;color:var(--ink)}
.kv{font-family:var(--mono);font-size:12.5px;color:var(--muted);margin:0 0 8px}
.kv b{color:var(--ink)}
details{margin-top:10px;border-top:1px dashed var(--edge);padding-top:10px}
summary{cursor:pointer;font-size:12px;color:var(--act);letter-spacing:.02em}
summary:focus-visible{outline:2px solid var(--act);outline-offset:3px;border-radius:3px}
details pre{margin-top:10px;max-height:420px;overflow:auto;
            background:var(--obs-bg);padding:12px;border-radius:6px}
.dup{margin-left:8px;font-size:10.5px;letter-spacing:.08em;text-transform:uppercase;
     color:var(--warn);border:1px solid var(--warn);border-radius:99px;padding:1px 7px}
footer{margin-top:52px;padding-top:18px;border-top:1px solid var(--edge);
       color:var(--muted);font-size:12.5px}
@media (max-width:620px){ .step{grid-template-columns:34px 1fr;gap:9px} }
"""


def esc(s):
    return html.escape(s or "")


def short(s, n):
    s = s or ""
    return s if len(s) <= n else s[:n] + f"\n… (+{len(s)-n:,} more chars)"


def render(traj: dict) -> str:
    ms = traj.get("messages", [])
    steps = []          # (assistant_msg, [tool results])
    system = next((m for m in ms if m["role"] == "system"), None)
    kickoff = next((m for m in ms if m["role"] == "user"), None)

    i = 0
    while i < len(ms):
        m = ms[i]
        if m["role"] == "assistant":
            results = []
            j = i + 1
            while j < len(ms) and ms[j]["role"] == "tool":
                results.append(ms[j]); j += 1
            steps.append((m, results))
            i = j
        else:
            i += 1

    def sig(m):
        tc = m.get("tool_calls") or []
        return (m.get("reasoning") or "") + "|" + json.dumps(
            [t["function"] for t in tc], sort_keys=True)

    out = []
    dup_count = 0
    prev = None
    for n, (m, results) in enumerate(steps, 1):
        s = sig(m)
        is_dup = prev is not None and s == prev
        if is_dup:
            dup_count += 1
        prev = s
        block = [f'<div class="step"><div class="rail"><span class="num">{n:02d}</span></div><div>']

        if m.get("reasoning"):
            block.append(
                '<div class="card think"><div class="head">'
                '<span class="tag">Thinking</span>'
                f'<span class="who">chain-of-thought · {len(m["reasoning"]):,} chars</span>'
                + ('<span class="dup">identical to previous step</span>' if is_dup else "")
                + '</div>'
                f'<div class="body">{esc(m["reasoning"])}</div></div>')

        if m.get("content"):
            block.append(
                '<div class="card say"><div class="head"><span class="tag">Says</span></div>'
                f'<div class="body">{esc(m["content"])}</div></div>')

        for tc in (m.get("tool_calls") or []):
            fn = tc["function"]
            name = fn.get("name", "?")
            try:
                args = json.loads(fn.get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {"_raw": fn.get("arguments")}
            big = {k: v for k, v in args.items() if isinstance(v, str) and len(v) > 400}
            small = {k: v for k, v in args.items() if k not in big}
            kv = " · ".join(f"{k}=<b>{esc(str(v))[:120]}</b>" for k, v in small.items()) or "—"
            block.append(
                '<div class="card act"><div class="head">'
                f'<span class="tag">Action</span><span class="who">{esc(name)}()</span></div>'
                f'<div class="body"><p class="kv">{kv}</p>')
            for k, v in big.items():
                block.append(
                    f'<details><summary>show {esc(k)} — {len(v):,} chars written</summary>'
                    f'<pre>{esc(v)}</pre></details>')
            block.append('</div></div>')

        for r in results:
            block.append(
                '<div class="card obs"><div class="head">'
                '<span class="tag">Result</span></div>'
                f'<div class="body"><pre>{esc(short(r.get("content"), 1400))}</pre></div></div>')

        block.append('</div></div>')
        out.append("\n".join(block))

    meta = {k: traj.get(k) for k in ("episode", "model", "steps", "best", "reasoning_tokens")}
    stats = [
        (str(meta.get("episode")), "episode"),
        (str(meta.get("steps")), "steps taken"),
        (f'{meta.get("reasoning_tokens", 0):,}', "reasoning tokens"),
        (f'{(meta.get("best") or 0):.1f}', "best score /100"),
        (str(len(steps)), "turns shown"),
    ]
    stat_html = "".join(f'<div class="stat"><b>{esc(v)}</b><span>{esc(l)}</span></div>'
                        for v, l in stats)

    note = ""
    if dup_count:
        note = (f'<div class="note"><h2>Degenerate loop detected</h2><p>{dup_count} of '
                f'{len(steps)} turns repeat the previous turn <em>verbatim</em> — identical '
                f'chain-of-thought and identical tool call. The agent re-writes the same file '
                f'over and over instead of advancing, which is why the score sits at a plateau.'
                f'</p></div>')

    sys_html = ""
    if system:
        sys_html = ('<details style="margin-top:26px"><summary>show the system prompt the model '
                    f'was given — {len(system["content"]):,} chars</summary>'
                    f'<pre>{esc(system["content"])}</pre></details>')
    if kickoff:
        sys_html += ('<details><summary>show the kickoff message that opened this episode</summary>'
                     f'<pre>{esc(kickoff["content"])}</pre></details>')

    return f"""<title>Inside a solar-open2 episode</title>
<style>{CSS}</style>
<div class="wrap">
<header class="top">
  <p class="eyebrow">Agent trajectory · EdgeBench dabic_gravity_inversion</p>
  <h1>What the model was actually thinking</h1>
  <p class="sub">One full episode of <code>{esc(str(meta.get('model')))}</code> self-improving against
  EdgeBench's real judge: its preserved chain-of-thought, every tool call it chose, and what came
  back. Nothing here is paraphrased — this is the conversation as the model saw it.</p>
  <div class="stats">{stat_html}</div>
  {note}
  {sys_html}
</header>
<div class="timeline">
{''.join(out)}
</div>
<footer>Captured from <code>outputs/trajectories/episode_{meta.get('episode'):04d}.json</code>.
Long file writes and tool results are collapsed or truncated; everything else is verbatim.</footer>
</div>"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--traj", default="outputs/trajectories/episode_0009.json")
    ap.add_argument("--out", default="outputs/trajectory.html")
    a = ap.parse_args()
    traj = json.loads(Path(a.traj).read_text())
    Path(a.out).write_text(render(traj))
    print(f"wrote {a.out} from {a.traj}")


if __name__ == "__main__":
    main()
