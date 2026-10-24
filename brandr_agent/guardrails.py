"""Hard rules enforced in code. The model can't talk its way around these."""
from __future__ import annotations

from datetime import timedelta

from .store import Account, now, parse_ts

DEFAULT_LIMITS = {"max_posts_per_day": 2, "min_hours_between_posts": 4, "max_hashtags": 15}


def check_post(acc: Account, post: dict) -> list[str]:
    """Return a list of violations (empty = OK)."""
    prof = acc.profile
    limits = {**DEFAULT_LIMITS, **prof.get("limits", {})}
    issues: list[str] = []
    text = f"{post.get('caption', '')} {' '.join(post.get('hashtags', []))}".lower()

    if not post.get("caption", "").strip():
        issues.append("empty caption")
    if post.get("platform") not in prof.get("platforms", []):
        issues.append(f"platform {post.get('platform')!r} not enabled for this account")
    if len(post.get("hashtags", [])) > limits["max_hashtags"]:
        issues.append(f"too many hashtags (>{limits['max_hashtags']})")
    for word in prof.get("banned_words", []):
        if word.lower() in text:
            issues.append(f"banned word: {word}")

    try:
        when = parse_ts(post["scheduled_for"])
    except Exception:
        return issues + ["scheduled_for missing or not ISO-8601"]
    if when < now() - timedelta(minutes=5):
        issues.append("scheduled_for is in the past")

    siblings = [p for p in acc.posts()
                if p["id"] != post.get("id") and p["status"] in ("approved", "published", "draft")
                and p["platform"] == post.get("platform") and p.get("scheduled_for")]
    same_day = [p for p in siblings if parse_ts(p["scheduled_for"]).date() == when.date()]
    if len(same_day) >= limits["max_posts_per_day"]:
        issues.append(f"daily cap reached ({limits['max_posts_per_day']}/day on {post['platform']})")
    gap = timedelta(hours=limits["min_hours_between_posts"])
    if any(abs(parse_ts(p["scheduled_for"]) - when) < gap for p in siblings):
        issues.append(f"closer than {limits['min_hours_between_posts']}h to another post")
    cap = post.get("caption", "").strip().lower()
    if any(p.get("caption", "").strip().lower() == cap for p in acc.posts()
           if p["id"] != post.get("id") and p["status"] != "rejected"):
        issues.append("duplicate of an existing caption")
    return issues
