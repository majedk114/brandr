"""حزم جاهزة للتسليم: حزمة إنتاج (prompts لـ Magnific) وحزمة نشر (ما يُنسخ للمنصة)."""
from __future__ import annotations

from .workspace import Account, now


def production_pack(acc: Account) -> str:
    posts = acc.posts("approved")
    cfg = acc.config
    out = [f"# حزمة إنتاج: {cfg['name']}", "", f"{len(posts)} منشور ينتظر الميديا. أداة الإنتاج: Magnific.", ""]
    if acc.doc("character.md"):
        out += ["> الشخصية لها character bible: استخدم صور المرجع نفسها في كل توليد عشان يثبت الشكل.", ""]
    for p in posts:
        pr = p.get("production", {})
        out += [f"## {p['id']} · {p.get('format')} · {p.get('scheduled_for', '')[:16]}",
                f"- النوع: {pr.get('type', '?')} · المقاس: {pr.get('aspect', '?')}",
                f"- الخطاف: {p.get('hook')}", "", "```", pr.get("prompt", "(ما في prompt)"), "```"]
        if pr.get("notes"):
            out.append(f"ملاحظات: {pr['notes']}")
        out += ["", f"بعد التوليد: `python -m genx media {acc.slug} {p['id']} <مسار أو رابط>`", ""]
    return "\n".join(out)


def publish_pack(acc: Account) -> str:
    posts = acc.posts("ready")
    cfg = acc.config
    out = [f"# حزمة نشر: {cfg['name']}", "", f"أُعدّت {now():%Y-%m-%d}. {len(posts)} منشور جاهز.", ""]
    for p in posts:
        tags = " ".join(p.get("hashtags", []))
        out += [f"## {p['id']} · {p.get('scheduled_for')}", f"- المنصات: {', '.join(p.get('platforms', []))}",
                f"- الميديا: {', '.join(p.get('media', []))}"]
        if p.get("ai_label"):
            out.append("- ⚠️ فعّل وسم «محتوى مولّد بالذكاء الاصطناعي» في كل منصة")
        if p.get("client"):
            out.append(f"- ⚠️ منشور عميل ({p['client']}): فعّل وسم الشراكة المدفوعة")
        out += ["", "```", f"{p.get('caption', '')}\n\n{tags}".strip(), "```",
                f"بعد النشر: `python -m genx published {acc.slug} {p['id']} instagram=<رابط> tiktok=<رابط>`", ""]
    return "\n".join(out)
