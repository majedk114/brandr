"""دورة حياة المنشور. كل انتقال مسجل في history، والانتقالات غير المسموحة مرفوضة."""
from __future__ import annotations

from .rules import check
from .workspace import Account, now

STATUSES = ("draft", "review", "changes", "approved", "ready", "published", "rejected")
# من -> إلى
TRANSITIONS = {
    "draft": {"review", "approved", "rejected"},
    "review": {"approved", "changes", "rejected"},
    "changes": {"review", "approved", "rejected"},
    "approved": {"ready", "changes", "rejected"},
    "ready": {"published", "changes", "rejected"},
    "published": set(),
    "rejected": set(),
}
EDITABLE = ("plan", "idea", "series", "experiment", "variants", "pillar", "format", "platforms", "hook", "caption", "hashtags", "cta", "scheduled_for",
            "hypothesis", "production", "client", "paid_disclosure", "ai_label", "notes")


class TransitionError(Exception):
    pass


def _move(acc: Account, post: dict, to: str, by: str, note: str = "") -> dict:
    if to not in TRANSITIONS[post["status"]]:
        raise TransitionError(f"ما ينفع ننقل {post['id']} من {post['status']} إلى {to}")
    post.setdefault("history", []).append({"at": now().isoformat(), "from": post["status"], "to": to,
                                            "by": by, "note": note})
    post["status"] = to
    return acc.save_post(post)


def create(acc: Account, fields: dict) -> dict:
    post = {k: v for k, v in fields.items() if k in EDITABLE}
    post.update(id=acc.new_post_id(), status="draft", created_at=now().isoformat(), media=[],
                metrics={}, history=[])
    post.setdefault("platforms", acc.config.get("platforms", []))
    return acc.save_post(post)


def edit(acc: Account, pid: str, fields: dict) -> dict:
    post = acc.get_post(pid)
    if post["status"] in ("published", "rejected"):
        raise TransitionError(f"المنشور {pid} {post['status']}، ما ينفع يتعدل")
    post.update({k: v for k, v in fields.items() if k in EDITABLE})
    return acc.save_post(post)


def submit(acc: Account, pid: str) -> tuple[dict, list[str]]:
    """يمرر المنشور على القواعد، ثم للمراجعة أو الاعتماد المباشر حسب استقلالية الحساب."""
    post = acc.get_post(pid)
    issues = check(acc, post)
    try:
        plan_ok = acc.plan_status(post.get("plan", "")) == "approved"
    except ValueError as e:
        plan_ok = False
        issues.append(str(e))
    if acc.autonomy != "auto" and not plan_ok:
        issues.append(f"خطة الأسبوع {post.get('plan')} ما اتعتمدت لسه")
    if issues:
        return post, issues
    to = "review" if acc.autonomy == "every_post" else "approved"
    return _move(acc, post, to, "agent", "اجتاز القواعد"), []


def decide(acc: Account, pid: str, decision: str, note: str = "") -> dict:
    to = {"approve": "approved", "reject": "rejected", "changes": "changes"}[decision]
    post = _move(acc, acc.get_post(pid), to, "owner", note)
    acc.log_decision(f"منشور {pid}", decision, note)
    return post


def attach_media(acc: Account, pid: str, ref: str) -> dict:
    post = acc.get_post(pid)
    if post["status"] not in ("approved", "ready"):
        raise TransitionError(f"الميديا تتضاف بعد اعتماد النص (الحالة الآن {post['status']})")
    post.setdefault("media", []).append(ref)
    acc.save_post(post)
    return post if post["status"] == "ready" else _move(acc, post, "ready", "agent", f"ميديا: {ref}")


def mark_published(acc: Account, pid: str, urls: dict) -> dict:
    post = acc.get_post(pid)
    post["published_urls"] = {**post.get("published_urls", {}), **urls}
    post["published_at"] = now().isoformat()
    return _move(acc, post, "published", "owner", " ".join(f"{k}:{v}" for k, v in urls.items()))


def record_metrics(acc: Account, pid: str, platform: str, values: dict) -> dict:
    post = acc.get_post(pid)
    if post["status"] != "published":
        raise TransitionError("الأرقام تتسجل بعد النشر بس")
    post.setdefault("metrics", {}).setdefault(platform, {}).update(values)
    post["metrics_updated_at"] = now().isoformat()
    return acc.save_post(post)
