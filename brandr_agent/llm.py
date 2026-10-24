"""Thin tool-use loop over the Anthropic API. The client is injectable for tests."""
from __future__ import annotations

import json
import os
from typing import Callable

MODEL = os.environ.get("BRANDR_MODEL", "claude-opus-5-5")
THINKING_BUDGET = int(os.environ.get("BRANDR_THINKING_BUDGET", "8000"))  # 0 disables extended thinking


def default_client():
    import anthropic
    return anthropic.Anthropic()


def run_agent(client, system: str, task: str, tools: list[dict], handlers: dict[str, Callable],
              max_turns: int = 40, max_tokens: int = 16000) -> str:
    """Loop until the model stops calling tools or calls `finish`. Returns the final summary."""
    messages = [{"role": "user", "content": task}]
    kw = {}
    if THINKING_BUDGET:
        kw["thinking"] = {"type": "enabled", "budget_tokens": THINKING_BUDGET}
        max_tokens = max(max_tokens, THINKING_BUDGET + 4000)
    for _ in range(max_turns):
        resp = client.messages.create(model=MODEL, max_tokens=max_tokens, system=system,
                                      tools=tools, messages=messages, **kw)
        messages.append({"role": "assistant", "content": resp.content})
        calls = [b for b in resp.content if b.type == "tool_use"]
        if not calls:
            return "".join(b.text for b in resp.content if b.type == "text")
        results, finished = [], None
        for c in calls:
            try:
                out = handlers[c.name](**c.input)
                is_err = False
            except Exception as e:  # report to the model so it can self-correct
                out, is_err = f"ERROR: {e}", True
            if c.name == "finish" and not is_err:
                finished = c.input.get("summary", "")
            results.append({"type": "tool_result", "tool_use_id": c.id, "is_error": is_err,
                            "content": out if isinstance(out, str) else json.dumps(out, ensure_ascii=False)})
        messages.append({"role": "user", "content": results})
        if finished is not None:
            return finished
    return "stopped: max_turns reached"


def complete_json(client, system: str, user: str) -> dict:
    """One-shot call expecting a JSON object back (used by the critic)."""
    resp = client.messages.create(model=MODEL, max_tokens=2000, system=system,
                                  messages=[{"role": "user", "content": user}])
    text = "".join(b.text for b in resp.content if b.type == "text")
    return json.loads(text[text.index("{"): text.rindex("}") + 1])


def tool(name: str, description: str, properties: dict, required: list[str] | None = None) -> dict:
    return {"name": name, "description": description,
            "input_schema": {"type": "object", "properties": properties, "required": required or []}}
