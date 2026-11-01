"""القواعد الثابتة لكل حساب. تُفرض بالكود قبل أي مراجعة، والـ agent ما يقدر يتجاوزها."""
from __future__ import annotations

from datetime import timedelta

from .workspace import Account, now, parse_ts

DEFAULT_LIMITS = {"max_posts_per_day": 1, "min_hours_between_posts": 12, "max_hashtags": 10,
                  "max_client_posts_per_week": 1}
REQUIRED = ("idea", "format", "hook", "caption", "scheduled_for", "hypothesis", "plan")


def check(acc: Account, post: dict) -> list[str]:
    """ترجع قائمة المخالفات. قائمة فاضية = المنشور سليم."""
    cfg = acc.config
    limits = {**DEFAULT_LIMITS, **cfg.get("limits", {})}
    issues = [f"حقل ناقص: {k}" for k in REQUIRED if not str(post.get(k, "")).strip()]

    ideas = cfg.get("ideas", {})
    if ideas and post.get("idea") not in ideas:
        issues.append(f"الفكرة {post.get('idea')!r} مش من أفكار الحساب {list(ideas)}")
    if post.get("format") and post["format"] not in cfg.get("formats", [post["format"]]):
        issues.append(f"الصيغة {post['format']!r} غير مفعلة للحساب {cfg.get('formats')}")
    bad = set(post.get("platforms", [])) - set(cfg.get("platforms", []))
    if bad or not post.get("platforms"):
        issues.append(f"منصات غير مفعلة أو فاضية: {sorted(bad) or '[]'}")
    if len(post.get("hashtags", [])) > limits["max_hashtags"]:
        issues.append(f"هاشتاقات أكثر من {limits['max_hashtags']}")

    text = " ".join([post.get("hook", ""), post.get("caption", ""), " ".join(post.get("hashtags", []))]).lower()
    for w in cfg.get("banned_words", []):
        if w.lower() in text:
            issues.append(f"كلمة ممنوعة: {w}")

    if cfg.get("ai_label_required") and not post.get("ai_label"):
        issues.append("الحساب شخصية AI: لازم ai_label=true (وسم المحتوى المولّد في المنصة)")
    if post.get("client"):
        if not post.get("paid_disclosure"):
            issues.append("منشور عميل بدون إفصاح إعلاني (paid_disclosure)")

    # التوقيت
    try:
        when = parse_ts(post["scheduled_for"])
    except Exception:
        return issues + ["scheduled_for لازم يكون تاريخ ISO مع المنطقة الزمنية"]
    if when < now() - timedelta(minutes=5) and post.get("status") not in ("published",):
        issues.append("الموعد في الماضي")

    others = [p for p in acc.posts() if p["id"] != post.get("id") and p["status"] != "rejected"
              and p.get("scheduled_for")]
    same_day = [p for p in others if parse_ts(p["scheduled_for"]).date() == when.date()]
    if len(same_day) >= limits["max_posts_per_day"]:
        issues.append(f"الحد اليومي اكتمل ({limits['max_posts_per_day']} في اليوم)")
    gap = timedelta(hours=limits["min_hours_between_posts"])
    if any(abs(parse_ts(p["scheduled_for"]) - when) < gap for p in others):
        issues.append(f"أقرب من {limits['min_hours_between_posts']} ساعة لمنشور آخر")
    if post.get("client"):
        week = when.isocalendar()[:2]
        clients = [p for p in others if p.get("client") and parse_ts(p["scheduled_for"]).isocalendar()[:2] == week]
        if len(clients) >= limits["max_client_posts_per_week"]:
            issues.append(f"منشورات العملاء اكتملت هذا الأسبوع ({limits['max_client_posts_per_week']})")

    cap = post.get("caption", "").strip()
    if cap and any(p.get("caption", "").strip() == cap for p in others):
        issues.append("نص مكرر من منشور سابق")
    return issues
