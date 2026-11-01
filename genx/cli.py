"""أوامر Genx. تُستخدم من الـ skills داخل Claude Code، أو مباشرة من الطرفية."""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from . import packs, posts, reports, research
from .rules import check
from .workspace import Account, root

TEMPLATE_CONFIG = {
    "name": "", "type": "community", "status": "pilot", "platforms": ["instagram", "tiktok", "facebook"],
    "formats": ["reel", "carousel", "image"], "audience_timezone": "+03:00", "autonomy": "every_post",
    "phase": "setup", "ideas": {"A": "", "B": ""}, "series": {}, "posts_per_week": 4, "banned_words": [], "ai_label_required": False,
    "limits": {"max_posts_per_day": 1, "min_hours_between_posts": 12, "max_hashtags": 10,
               "max_client_posts_per_week": 1},
}


def acc_or_die(slug: str) -> Account:
    a = Account(slug)
    if not a.exists:
        sys.exit(f"ما في حساب باسم {slug}. الحسابات: {[x.slug for x in Account.all()]}")
    return a


def targets(slug: str) -> list[Account]:
    return Account.all() if slug == "*" else [acc_or_die(slug)]


def kv(pairs: list[str]) -> dict:
    out = {}
    for p in pairs:
        k, _, v = p.partition("=")
        try:
            out[k] = json.loads(v)
        except json.JSONDecodeError:
            out[k] = v
    return out


def read_json(src: str) -> dict:
    return json.loads(sys.stdin.read() if src == "-" else Path(src).read_text("utf-8"))


def context(a: Account) -> str:
    """كل ما يحتاجه الـ agent عن حساب واحد، وبس هذا الحساب."""
    cfg = a.config
    parts = [f"# سياق الحساب: {cfg['name']} ({a.slug})", "",
             "قاعدة العزل: اشتغل على هذا الحساب فقط. لا تقرأ ولا تنسخ من مجلد حساب آخر.", "",
             "## الإعدادات", "```json", json.dumps(cfg, ensure_ascii=False, indent=2), "```"]
    for name, title in (("brand.md", "الهوية"), ("character.md", "دليل الشخصية"), ("ideas.md", "الأفكار"),
                        ("research/research.md", "البحث والرصد"), ("community.md", "دليل الردود"),
                        ("launch.md", "خطة الإطلاق"), ("playbook.md", "ما تعلمناه")):
        if a.doc(name):
            parts += ["", f"## {title} ({name})", a.doc(name)]
    plans = a.plans()
    parts += ["", "## الخطط", *(f"- {w}: {s}" for w, s in plans[-4:])] if plans else ["", "## الخطط", "- لا شيء"]
    recent = a.posts()[-15:]
    parts += ["", "## آخر المنشورات", "| id | الحالة | الفكرة | الموعد | الخطاف |", "| --- | --- | --- | --- | --- |"]
    parts += [f"| {p['id']} | {p['status']} | {p.get('idea')} | {str(p.get('scheduled_for'))[:16]} | "
              f"{p.get('hook', '')[:50]} |" for p in recent] or ["| - | - | - | - | - |"]
    snaps = a.rows("snapshots.jsonl")
    if snaps:
        parts += ["", "## آخر لقطة نمو", *(f"- {r['platform']}: {r.get('followers', 0)} متابع ({r['at'][:10]})"
                                          for r in {r["platform"]: r for r in snaps}.values())]
    leads = [r for r in a.rows("leads.jsonl") if r.get("status", "open") == "open"]
    if leads:
        parts += ["", "## استفسارات مفتوحة", *(f"- {r['at'][:10]} {r.get('who', '')}: {r.get('note', '')}" for r in leads)]
    if not a.doc("research/research.md"):
        parts += ["", "⚠️ ما في بحث للحساب (research/research.md). شغّل /research قبل التخطيط."]
    changes = [p for p in a.posts("changes")]
    if changes:
        parts += ["", "## تعديلات طلبها صاحب الحساب"]
        parts += [f"- {p['id']}: {p['history'][-1].get('note', '')}" for p in changes]
    return "\n".join(parts)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m genx", description="Genx Studio")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("accounts", help="قائمة الحسابات")
    s = sub.add_parser("new", help="حساب جديد"); s.add_argument("slug"); s.add_argument("--name", required=True)
    s.add_argument("--type", choices=["community", "persona"], default="community")
    s = sub.add_parser("context", help="سياق حساب واحد للـ agent"); s.add_argument("slug")
    s = sub.add_parser("post-new", help="مسودة منشور من JSON (- للقراءة من stdin)"); s.add_argument("slug"); s.add_argument("src")
    s = sub.add_parser("post-edit", help="تعديل منشور"); s.add_argument("slug"); s.add_argument("id"); s.add_argument("src")
    s = sub.add_parser("check", help="فحص القواعد"); s.add_argument("slug"); s.add_argument("id")
    s = sub.add_parser("submit", help="فحص ثم إرسال للمراجعة"); s.add_argument("slug"); s.add_argument("id")
    s = sub.add_parser("show", help="عرض منشور"); s.add_argument("slug"); s.add_argument("id")
    s = sub.add_parser("list", help="منشورات حساب"); s.add_argument("slug"); s.add_argument("--status", nargs="*", default=[])
    s = sub.add_parser("queue", help="كل ما ينتظر قرارك"); s.add_argument("--json", action="store_true")
    s = sub.add_parser("decide", help="قرار: approve/reject/changes")
    s.add_argument("slug", help="الحساب أو * لكل الحسابات")
    s.add_argument("target", help="رقم المنشور، all لكل المراجعات، أو plan:2026-W45")
    s.add_argument("decision", choices=["approve", "reject", "changes"]); s.add_argument("note", nargs="?", default="")
    s = sub.add_parser("plan-status", help="حالة خطة أسبوع"); s.add_argument("slug"); s.add_argument("week")
    s = sub.add_parser("media", help="إرفاق ميديا"); s.add_argument("slug"); s.add_argument("id"); s.add_argument("ref")
    s = sub.add_parser("production-pack", help="حزمة prompts للإنتاج"); s.add_argument("slug")
    s = sub.add_parser("publish-pack", help="حزمة نشر"); s.add_argument("slug")
    s = sub.add_parser("published", help="تسجيل النشر"); s.add_argument("slug"); s.add_argument("id"); s.add_argument("urls", nargs="+")
    s = sub.add_parser("metrics", help="تسجيل أرقام"); s.add_argument("slug"); s.add_argument("id")
    s.add_argument("platform"); s.add_argument("values", nargs="+")
    s = sub.add_parser("report", help="تقرير حساب"); s.add_argument("slug")
    s = sub.add_parser("calendar", help="المجدول للأيام القادمة"); s.add_argument("slug"); s.add_argument("--days", type=int, default=14)
    s = sub.add_parser("research-ingest", help="إضافة منشورات منافسين (JSON list)"); s.add_argument("slug"); s.add_argument("src")
    s = sub.add_parser("research", help="ملخص البحث والمنشورات المتفوقة"); s.add_argument("slug")
    s = sub.add_parser("swipe", help="إضافة خطاف لمكتبة الحساب"); s.add_argument("slug"); s.add_argument("hook")
    s.add_argument("--tag", default=""); s.add_argument("--why", default=""); s.add_argument("--url", default="")
    s = sub.add_parser("snapshot", help="لقطة نمو أسبوعية"); s.add_argument("slug"); s.add_argument("platform"); s.add_argument("values", nargs="+")
    s = sub.add_parser("lead", help="تسجيل استفسار/عميل محتمل"); s.add_argument("slug"); s.add_argument("who"); s.add_argument("note")
    s.add_argument("--platform", default="")
    s = sub.add_parser("lead-close", help="إغلاق استفسار"); s.add_argument("slug"); s.add_argument("index", type=int); s.add_argument("outcome")
    s = sub.add_parser("revenue", help="تسجيل دخل"); s.add_argument("slug"); s.add_argument("amount", type=float)
    s.add_argument("source"); s.add_argument("--currency", default="USD"); s.add_argument("--post", default="")
    sub.add_parser("portfolio", help="ملخص المحفظة")
    a = ap.parse_args(argv)

    try:
        run(a)
    except (KeyError, ValueError, posts.TransitionError) as e:
        sys.exit(f"خطأ: {e}")


def run(a):
    if a.cmd == "accounts":
        for x in Account.all():
            c = x.config
            print(f"{x.slug:16} {c['name']:18} {c['type']:10} {c.get('status', ''):8} {x.autonomy}")
    elif a.cmd == "new":
        x = Account(a.slug)
        if x.exists:
            sys.exit("الحساب موجود")
        for d in (x.posts_dir, x.plans_dir, x.media_dir):
            d.mkdir(parents=True, exist_ok=True)
        x.save_config({**TEMPLATE_CONFIG, "name": a.name, "type": a.type, "ai_label_required": a.type == "persona"})
        for f in ["brand.md", "ideas.md", "playbook.md"] + (["character.md"] if a.type == "persona" else []):
            (x.dir / f).write_text(f"# {f[:-3]}: {a.name}\n\n(مسودة: تُملأ مع صاحب الحساب)\n", "utf-8")
        print(f"اتعمل {x.dir}")
    elif a.cmd == "context":
        print(context(acc_or_die(a.slug)))
    elif a.cmd == "post-new":
        x = acc_or_die(a.slug); p = posts.create(x, read_json(a.src))
        print(json.dumps({"id": p["id"], "issues": check(x, p)}, ensure_ascii=False))
    elif a.cmd == "post-edit":
        x = acc_or_die(a.slug); p = posts.edit(x, a.id, read_json(a.src))
        print(json.dumps({"id": p["id"], "issues": check(x, p)}, ensure_ascii=False))
    elif a.cmd == "check":
        x = acc_or_die(a.slug); print("\n".join(check(x, x.get_post(a.id))) or "سليم")
    elif a.cmd == "submit":
        p, issues = posts.submit(acc_or_die(a.slug), a.id)
        print(f"مرفوض:\n- " + "\n- ".join(issues) if issues else f"{p['id']} -> {p['status']}")
        if issues:
            sys.exit(2)
    elif a.cmd == "show":
        print(json.dumps(acc_or_die(a.slug).get_post(a.id), ensure_ascii=False, indent=2))
    elif a.cmd == "list":
        for p in acc_or_die(a.slug).posts(*a.status):
            print(f"{p['id']}  {p['status']:9} {p.get('idea', '?')}  {str(p.get('scheduled_for'))[:16]}  {p.get('hook', '')[:60]}")
    elif a.cmd == "queue":
        items = reports.queue(Account.all())
        if a.json:
            print(json.dumps(items, ensure_ascii=False, indent=2))
        else:
            for i in items:
                print(f"[{i['account']}] {i['kind']} {i['id']}" + (f"  {i.get('when', '')[:16]}  {i.get('hook', '')}" if i["kind"] == "post" else ""))
            print(f"{len(items)} عنصر ينتظر قرارك" if items else "ما في شيء ينتظرك")
    elif a.cmd == "decide":
        for x in targets(a.slug):
            if a.target.startswith("plan:"):
                week = a.target[5:]
                if x.plan_status(week) is None:
                    print(f"[{x.slug}] ما في خطة {week}"); continue
                st = {"approve": "approved", "reject": "rejected", "changes": "changes"}[a.decision]
                x.set_plan_status(week, st); x.log_decision(f"خطة {week}", a.decision, a.note)
                print(f"[{x.slug}] خطة {week} -> {st}")
            else:
                ids = [p["id"] for p in x.posts("review")] if a.target == "all" else [a.target]
                for pid in ids:
                    print(f"[{x.slug}] {pid} -> {posts.decide(x, pid, a.decision, a.note)['status']}")
    elif a.cmd == "plan-status":
        print(acc_or_die(a.slug).plan_status(a.week) or "ما في خطة")
    elif a.cmd == "media":
        x = acc_or_die(a.slug); ref = a.ref; src = Path(a.ref)
        if src.is_file():
            x.media_dir.mkdir(parents=True, exist_ok=True)
            dest = x.media_dir / f"{a.id}-{len(x.get_post(a.id).get('media', [])) + 1}{src.suffix}"
            shutil.copy2(src, dest); ref = str(dest.relative_to(x.dir))
        print(f"{a.id} -> {posts.attach_media(x, a.id, ref)['status']} ({ref})")
    elif a.cmd in ("production-pack", "publish-pack"):
        x = acc_or_die(a.slug)
        text = packs.production_pack(x) if a.cmd == "production-pack" else packs.publish_pack(x)
        out = x.dir / "out" / f"{a.cmd}.md"; out.parent.mkdir(exist_ok=True); out.write_text(text, "utf-8")
        print(text); print(f"\n(محفوظ في {out.relative_to(root())})")
    elif a.cmd == "published":
        print(posts.mark_published(acc_or_die(a.slug), a.id, kv(a.urls))["status"])
    elif a.cmd == "metrics":
        posts.record_metrics(acc_or_die(a.slug), a.id, a.platform, kv(a.values)); print("اتسجل")
    elif a.cmd == "report":
        print(reports.account_report(acc_or_die(a.slug)))
    elif a.cmd == "calendar":
        from datetime import timedelta
        from .workspace import now, parse_ts
        x = acc_or_die(a.slug); end = now() + timedelta(days=a.days)
        rows = [p for p in x.posts() if p.get("scheduled_for") and p["status"] not in ("rejected", "published")
                and now() <= parse_ts(p["scheduled_for"]) <= end]
        for p in rows:
            print(f"{p['scheduled_for'][:16]}  {p['status']:9} {p.get('idea', '?')} {p.get('series') or '-':14} {p.get('hook', '')[:50]}")
        print(f"{len(rows)} منشور في {a.days} يوم (المستهدف {x.config.get('posts_per_week', 0) * a.days // 7})")
    elif a.cmd == "research-ingest":
        data = read_json(a.src)
        print(f"اتضاف {research.ingest(acc_or_die(a.slug), data if isinstance(data, list) else [data])} منشور")
    elif a.cmd == "research":
        print(research.summary(acc_or_die(a.slug)))
    elif a.cmd == "swipe":
        acc_or_die(a.slug).append(research.SWIPE, {"hook": a.hook, "tag": a.tag, "why": a.why, "url": a.url}); print("اتضاف")
    elif a.cmd == "snapshot":
        acc_or_die(a.slug).append("snapshots.jsonl", {"platform": a.platform, **kv(a.values)}); print("اتسجل")
    elif a.cmd == "lead":
        acc_or_die(a.slug).append("leads.jsonl", {"who": a.who, "note": a.note, "platform": a.platform, "status": "open"}); print("اتسجل")
    elif a.cmd == "lead-close":
        x = acc_or_die(a.slug); rows = x.rows("leads.jsonl")
        if not 0 <= a.index < len(rows):
            sys.exit(f"رقم الاستفسار من 0 إلى {len(rows) - 1}")
        rows[a.index].update(status="closed", outcome=a.outcome)
        (x.dir / "leads.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), "utf-8")
        print("اتقفل")
    elif a.cmd == "revenue":
        x = acc_or_die(a.slug)
        x.append("revenue.jsonl", {"amount": a.amount, "currency": a.currency, "source": a.source, "post": a.post})
        x.log_decision("دخل", f"{a.amount:g} {a.currency}", a.source); print("اتسجل")
    elif a.cmd == "portfolio":
        text = reports.portfolio(Account.all())
        out = root() / "portfolio" / "summary.md"; out.parent.mkdir(exist_ok=True); out.write_text(text + "\n", "utf-8")
        print(text)
