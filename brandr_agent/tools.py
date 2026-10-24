"""Tool schemas + handlers, bound to one account. Autonomy and guardrails live here, not in prompts."""
from __future__ import annotations

import json

from . import prompts
from .guardrails import check_post
from .llm import complete_json, tool
from .store import Account

WEIGHTS = {"likes": 1, "reactions": 1, "comments": 3, "shares": 5, "saved": 4, "saves": 4}
MIN_CRITIC_SCORE = 7


def engagement(m: dict) -> float:
    raw = sum(WEIGHTS.get(k, 0) * v for k, v in m.items() if isinstance(v, (int, float)))
    base = m.get("reach") or m.get("impressions") or m.get("views")
    return round(raw / base * 100, 2) if base else float(raw)


def build(acc: Account, client, phase: str):
    """Return (tools, handlers) for a phase: 'analyze' or 'plan'."""
    prof = acc.profile
    state = {"created": [], "finished": False}

    def get_profile():
        return prof

    def get_playbook():
        return acc.playbook()

    def list_posts(status: str = "", limit: int = 30):
        rows = acc.posts(status or None)[-limit:]
        return [{k: p.get(k) for k in ("id", "platform", "format", "pillar", "status", "scheduled_for",
                                       "hypothesis", "caption")} for p in rows]

    def get_performance(limit: int = 30):
        rows = [p for p in acc.posts("published") if p.get("metrics")][-limit:]
        out = [{"id": p["id"], "platform": p["platform"], "format": p.get("format"), "pillar": p.get("pillar"),
                "published_at": p.get("published_at"), "hypothesis": p.get("hypothesis"),
                "caption": p["caption"], "metrics": p["metrics"], "score": engagement(p["metrics"])}
               for p in rows]
        return sorted(out, key=lambda r: -r["score"]) or "no published posts with metrics yet"

    def update_playbook(markdown: str):
        acc.write_playbook(markdown)
        acc.log("playbook_updated", chars=len(markdown))
        return "playbook updated"

    def save_plan(plan: dict):
        (acc.dir / "plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2), "utf-8")
        acc.log("plan_saved", slots=len(plan.get("slots", [])))
        return "plan saved"

    def create_post(platform: str, format: str, pillar: str, caption: str, scheduled_for: str,
                    hypothesis: str, hashtags: list[str] | None = None, media_brief: str = "",
                    media_url: str = ""):
        post = {"platform": platform, "format": format, "pillar": pillar, "caption": caption,
                "hashtags": hashtags or [], "scheduled_for": scheduled_for, "hypothesis": hypothesis,
                "media_brief": media_brief, "media_url": media_url}
        issues = check_post(acc, post)
        if issues:
            return {"saved": False, "stage": "guardrails", "issues": issues}
        verdict = complete_json(client, prompts.CRITIC,
                                f"ACCOUNT PROFILE:\n{json.dumps(prof, ensure_ascii=False)}\n\n"
                                f"PLAYBOOK:\n{acc.playbook()}\n\nPOST:\n{json.dumps(post, ensure_ascii=False)}")
        if verdict.get("score", 0) < MIN_CRITIC_SCORE:
            return {"saved": False, "stage": "critic", **verdict}
        # autonomy is decided here, never by the model
        needs_media = platform == "instagram" and not media_url
        status = "approved" if acc.autonomy == "auto" and not needs_media else "draft"
        saved = acc.new_post(**post, status=status, critic=verdict, needs_media=needs_media)
        state["created"].append(saved["id"])
        acc.log("post_created", post=saved["id"], status=status, score=verdict.get("score"))
        return {"saved": True, "id": saved["id"], "status": status, "needs_media": needs_media,
                "critic_score": verdict.get("score")}

    def finish(summary: str):
        state["finished"] = True
        acc.log("finish", phase=phase, summary=summary)
        return "ok"

    S = {"type": "string"}
    common = [tool("get_profile", "Account brand profile: voice, audience, pillars, limits.", {}),
              tool("get_playbook", "Learned playbook for this account.", {}),
              tool("list_posts", "List posts (optionally by status: draft/approved/published/failed).",
                   {"status": S, "limit": {"type": "integer"}})]
    fin = tool("finish", "End the task with a short report.", {"summary": S}, ["summary"])
    h = {"get_profile": get_profile, "get_playbook": get_playbook, "list_posts": list_posts, "finish": finish}

    if phase == "analyze":
        tools = common + [
            tool("get_performance", "Published posts with metrics, ranked by engagement score.",
                 {"limit": {"type": "integer"}}),
            tool("update_playbook", "Replace the playbook with new full markdown.", {"markdown": S}, ["markdown"]), fin]
        h |= {"get_performance": get_performance, "update_playbook": update_playbook}
    else:
        tools = common + [
            tool("save_plan", "Save the strategic plan (goal, pillar_mix, experiment, slots[]).",
                 {"plan": {"type": "object"}}, ["plan"]),
            tool("create_post", "Create one post. Scheduled time must be ISO-8601 UTC. Reviewed by guardrails + critic.",
                 {"platform": S, "format": S, "pillar": S, "caption": S, "scheduled_for": S, "hypothesis": S,
                  "hashtags": {"type": "array", "items": S}, "media_brief": S, "media_url": S},
                 ["platform", "format", "pillar", "caption", "scheduled_for", "hypothesis"]), fin]
        h |= {"save_plan": save_plan, "create_post": create_post}
    return tools, h, state
