"""حزم جاهزة للتسليم: حزمة إنتاج (prompts لـ Magnific) وحزمة نشر (ما يُنسخ للمنصة)."""
from __future__ import annotations

from .workspace import Account, now


def production_pack(acc: Account) -> str:
    posts = acc.posts("approved")
    cfg = acc.config
    out = [f"# حزمة إنتاج: {cfg['name']}", "", f"{len(posts)} منشور ينتظر الميديا. أداة الإنتاج: Magnific.", ""]
    if cfg.get("type") == "persona":
        refs = cfg.get("reference_images", [])
        if not refs:
            out += ["> ⛔ الشخصية ما عندها صور مرجعية معتمدة. أول خطوة: ولّد المراجع واعتمدها، بعدها المنشورات.", ""]
        else:
            out += ["> استخدم صور المرجع نفسها في كل توليد عشان يثبت الشكل:", *[f"> - {r}" for r in refs], ""]
        if cfg.get("character_prompt"):
            out += ["**وصف الشخصية الثابت (يبدأ به كل prompt):**", "```", cfg["character_prompt"], "```", ""]
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
        out += [f"## {p['id']} · {p.get('scheduled_for')}", f"- الميديا: {', '.join(p.get('media', []))}"]
        if p.get("ai_label"):
            out.append("- ⚠️ فعّل وسم «محتوى مولّد بالذكاء الاصطناعي» في كل منصة")
        if p.get("client"):
            out.append(f"- ⚠️ منشور عميل ({p['client']}): فعّل وسم الشراكة المدفوعة")
        for plat in p.get("platforms", []):
            v = p.get("variants", {}).get(plat, {})
            cap = v.get("caption", p.get("caption", ""))
            tags = " ".join(v.get("hashtags", p.get("hashtags", [])))
            out += ["", f"**{plat}**", "```", f"{cap}\n\n{tags}".strip(), "```"]
        out += [f"بعد النشر: `python -m genx published {acc.slug} {p['id']} instagram=<رابط> tiktok=<رابط>`", ""]
    return "\n".join(out)
