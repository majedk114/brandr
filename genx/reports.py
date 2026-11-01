"""التحليل لكل حساب على حدة، وملخص المحفظة بأرقام مجمّعة فقط (بدون نصوص أو بيانات جمهور)."""
from __future__ import annotations

from collections import defaultdict
from datetime import timedelta

from .workspace import Account, now, parse_ts

WEIGHTS = {"likes": 1, "reactions": 1, "comments": 3, "shares": 5, "saves": 4, "saved": 4, "follows": 6}


def score(metrics: dict) -> float:
    """نقاط التفاعل لكل 100 وصول، مجمّعة على كل المنصات."""
    raw = reach = 0.0
    for m in metrics.values():
        raw += sum(WEIGHTS.get(k, 0) * v for k, v in m.items() if isinstance(v, (int, float)))
        reach += m.get("reach") or m.get("views") or 0
    return round(raw / reach * 100, 2) if reach else 0.0


def _avg(xs: list[float]) -> float:
    return round(sum(xs) / len(xs), 2) if xs else 0.0


def account_report(acc: Account) -> str:
    done = [p for p in acc.posts("published") if p.get("metrics")]
    if not done:
        return f"# تقرير {acc.config['name']}\n\nما في منشورات منشورة بأرقام لسه."
    rows = sorted(done, key=lambda p: -score(p["metrics"]))
    by = {"idea": defaultdict(list), "format": defaultdict(list), "series": defaultdict(list)}
    for p in done:
        for k in by:
            by[k][p.get(k, "?")].append(score(p["metrics"]))
    reach = lambda p: sum(m.get("reach") or m.get("views") or 0 for m in p["metrics"].values())
    out = [f"# تقرير {acc.config['name']}", "", f"{len(done)} منشور بأرقام. النقاط = تفاعل موزون لكل 100 وصول.", "",
           "| المنشور | الفكرة | الصيغة | الوصول | النقاط | الخطاف |", "| --- | --- | --- | --- | --- | --- |"]
    out += [f"| {p['id']} | {p.get('idea')} | {p.get('format')} | {reach(p):.0f} | {score(p['metrics'])} | "
            f"{p.get('hook', '')[:60]} |" for p in rows]
    for k, label in (("idea", "حسب الفكرة"), ("format", "حسب الصيغة"), ("series", "حسب السلسلة")):
        out += ["", f"## {label}", "", "| القيمة | عدد | متوسط النقاط |", "| --- | --- | --- |"]
        out += [f"| {v} | {len(s)} | {_avg(s)} |" for v, s in sorted(by[k].items(), key=lambda kv: -_avg(kv[1]))]
    if len(done) < 5:
        out += ["", "⚠️ أقل من 5 منشورات: أي نمط هنا فرضية، ما نتيجة."]
    return "\n".join(out + ["", growth(acc)])


def growth(acc: Account) -> str:
    """نمو الحساب نفسه من اللقطات الأسبوعية (متابعين، زيارات، وصول)."""
    snaps = acc.rows("snapshots.jsonl")
    if not snaps:
        return "## نمو الحساب\n\nما في لقطات. سجّل بـ `snapshot` كل أسبوع."
    out = ["## نمو الحساب", "", "| التاريخ | المنصة | متابعين | التغيّر | زيارات البروفايل | وصول الحساب |", "| --- | --- | --- | --- | --- | --- |"]
    last: dict = {}
    for r in snaps:
        f = r.get("followers", 0)
        delta = f - last[r["platform"]] if r["platform"] in last else 0
        last[r["platform"]] = f
        out.append(f"| {r['at'][:10]} | {r['platform']} | {f} | {delta:+} | {r.get('profile_visits', '')} | {r.get('reach', '')} |")
    return "\n".join(out)


def revenue_total(acc: Account) -> dict:
    tot: dict = defaultdict(float)
    for r in acc.rows("revenue.jsonl"):
        tot[r.get("currency", "USD")] += float(r.get("amount", 0))
    return dict(tot)


def portfolio(accounts: list[Account]) -> str:
    week_ago = now() - timedelta(days=7)
    out = ["# ملخص المحفظة", "", f"آخر تحديث: {now():%Y-%m-%d %H:%M} UTC. أرقام مجمّعة فقط.", "",
           "| الحساب | المرحلة | مراجعة | اعتماد/ميديا | جاهز | منشور (7 أيام) | متوسط النقاط | متابعين | استفسارات مفتوحة | الدخل | خطط تنتظر |",
           "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for a in accounts:
        ps = a.posts()
        c = lambda *s: sum(p["status"] in s for p in ps)
        recent = [p for p in ps if p["status"] == "published" and p.get("published_at")
                  and parse_ts(p["published_at"]) >= week_ago]
        scored = [score(p["metrics"]) for p in ps if p["status"] == "published" and p.get("metrics")]
        pending = sum(s == "proposed" for _, s in a.plans())
        latest: dict = {}
        for r in a.rows("snapshots.jsonl"):
            latest[r["platform"]] = r.get("followers", 0)
        leads = sum(r.get("status", "open") == "open" for r in a.rows("leads.jsonl"))
        money = " ".join(f"{v:g} {k}" for k, v in revenue_total(a).items()) or "0"
        out.append(f"| {a.config['name']} | {a.config.get('phase', '-')} | {c('review')} | {c('approved')} | {c('ready')} | "
                   f"{len(recent)} | {_avg(scored)} | {sum(latest.values())} | {leads} | {money} | {pending} |")
    return "\n".join(out)


def queue(accounts: list[Account]) -> list[dict]:
    """كل ما ينتظر قرارك: خطط مقترحة ومنشورات في المراجعة."""
    items = []
    for a in accounts:
        items += [{"account": a.slug, "kind": "plan", "id": w} for w, s in a.plans() if s == "proposed"]
        items += [{"account": a.slug, "kind": "post", "id": p["id"], "when": p.get("scheduled_for"),
                   "idea": p.get("idea"), "hook": p.get("hook")} for p in a.posts("review")]
    return items
