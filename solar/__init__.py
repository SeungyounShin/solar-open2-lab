"""solar-cookbook — tiny shared helpers around the Upstage Solar API.

Solar is OpenAI-compatible, so we just wrap the `openai` SDK pointed at
Upstage's endpoint. `solar-open2` is a *reasoning* model: it spends
"thinking" tokens before answering, so keep `max_tokens` generous and read
`reasoning_tokens` from usage if you're curious how hard it thought.
"""

import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

DEFAULT_MODEL = os.getenv("SOLAR_MODEL", "solar-open2")
BASE_URL = os.getenv("SOLAR_BASE_URL", "https://api.upstage.ai/v1")

# Reasoning models burn tokens thinking before they answer. Too small a cap
# and you get an empty `content` (all budget spent mid-thought). Be generous.
DEFAULT_MAX_TOKENS = 16384


def get_client() -> OpenAI:
    """Build an OpenAI client pointed at Upstage. Reads UPSTAGE_API_KEY."""
    api_key = os.getenv("UPSTAGE_API_KEY")
    if not api_key:
        raise RuntimeError(
            "UPSTAGE_API_KEY is not set. Copy .env.example to .env and add your key "
            "(get one at https://console.upstage.ai/api-keys?api=chat)."
        )
    return OpenAI(api_key=api_key, base_url=BASE_URL)


def chat(messages, *, model=None, max_tokens=DEFAULT_MAX_TOKENS,
         temperature=0.7, reasoning_effort=None, tools=None, **kwargs):
    """One-shot completion. Returns the full ChatCompletion object.

    Use `.choices[0].message.content` for text, or `reasoning_tokens(resp)`
    to see how much the model thought.
    """
    client = get_client()
    params = dict(
        model=model or DEFAULT_MODEL,
        messages=messages,
        max_tokens=max_tokens,
        temperature=temperature,
        **kwargs,
    )
    if reasoning_effort is not None:
        params["reasoning_effort"] = reasoning_effort
    if tools is not None:
        params["tools"] = tools
    return client.chat.completions.create(**params)


def ask(prompt, *, system=None, **kwargs) -> str:
    """Dead-simple: send a prompt, get a string back."""
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    return chat(messages, **kwargs).choices[0].message.content


def stream_print(messages, *, model=None, max_tokens=DEFAULT_MAX_TOKENS,
                 temperature=0.7, reasoning_effort=None, **kwargs) -> str:
    """Stream a completion to stdout as it arrives; return the full text."""
    client = get_client()
    params = dict(
        model=model or DEFAULT_MODEL,
        messages=messages,
        max_tokens=max_tokens,
        temperature=temperature,
        stream=True,
        **kwargs,
    )
    if reasoning_effort is not None:
        params["reasoning_effort"] = reasoning_effort

    chunks = []
    for chunk in client.chat.completions.create(**params):
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta.content
        if delta:
            print(delta, end="", flush=True)
            chunks.append(delta)
    print()
    return "".join(chunks)


def reasoning_tokens(resp) -> int:
    """How many tokens the model spent thinking (0 if not reported)."""
    details = getattr(resp.usage, "completion_tokens_details", None)
    return getattr(details, "reasoning_tokens", 0) or 0
