"""البحث والرصد لحساب واحد: منافسين، منشورات متفوقة (outliers)، ومكتبة خطافات.

البيانات تجي من Apify أو إدخال يدوي، بصيغة موحّدة لكل منشور:
{"source": "@handle", "platform": "instagram", "url": "...", "caption": "...", "type": "reel",
 "likes": 0, "comments": 0, "shares": 0, "saves": 0, "views": 0, "posted_at": "ISO"}
"""
from __future__ import annotations

from collections import defaultdict
from statistics import median

from .workspace import Account

POSTS = "research/posts.jsonl"
SWIPE = "research/swipe.jsonl"
FIELDS = ("source", "platform", "url", "caption", "type", "likes", "comments", "shares", "saves", "views", "posted_at")


def engagement(p: dict) -> float:
    return p.get("likes", 0) + 3 * p.get("comments", 0) + 5 * p.get("shares", 0) + 4 * p.get("saves", 0)


def ingest(acc: Account, items: list[dict]) -> int:
    """يضيف منشورات منافسين، ويتجاهل المكرر (نفس الرابط)."""
    seen = {r.get("url") for r in acc.rows(POSTS)}
    n = 0
    for it in items:
        row = {k: it.get(k) for k in FIELDS if it.get(k) is not None}
        if not row.get("source") or not row.get("url") or row["url"] in seen:
            continue
        acc.append(POSTS, row)
        seen.add(row["url"])
        n += 1
    return n


def outliers(acc: Account, factor: float = 2.0) -> list[dict]:
    """المنشورات اللي تفاعلها ≥ factor × وسيط حسابها: دي اللي تستاهل الدراسة."""
    by = defaultdict(list)
    for r in acc.rows(POSTS):
        by[r["source"]].append(r)
    out = []
    for src, rows in by.items():
        if len(rows) < 5:
            continue
        base = median(engagement(r) for r in rows) or 1
        out += [{**r, "x_baseline": round(engagement(r) / base, 1)} for r in rows if engagement(r) >= factor * base]
    return sorted(out, key=lambda r: -r["x_baseline"])


def summary(acc: Account) -> str:
    rows = acc.rows(POSTS)
    if not rows:
        return "ما في بيانات منافسين لسه. شغّل /research."
    by = defaultdict(list)
    for r in rows:
        by[r["source"]].append(r)
    out = ["| المنافس | المنصة | منشورات | وسيط التفاعل | وسيط المشاهدات |", "| --- | --- | --- | --- | --- |"]
    for src, rs in sorted(by.items()):
        out.append(f"| {src} | {rs[0].get('platform')} | {len(rs)} | {median(engagement(r) for r in rs):.0f} | "
                   f"{median(r.get('views', 0) for r in rs):.0f} |")
    top = outliers(acc)[:15]
    out += ["", f"## المنشورات المتفوقة ({len(top)})", "", "| × الوسيط | المنافس | النوع | البداية | الرابط |", "| --- | --- | --- | --- | --- |"]
    out += [f"| {r['x_baseline']} | {r['source']} | {r.get('type', '')} | {(r.get('caption') or '')[:70].replace('|', '/')} | {r['url']} |"
            for r in top] or ["| - | - | - | (يحتاج 5 منشورات على الأقل لكل منافس) | - |"]
    swipe = acc.rows(SWIPE)
    if swipe:
        out += ["", f"## مكتبة الخطافات ({len(swipe)})", ""]
        out += [f"- [{s.get('tag', '')}] {s['hook']} ← {s.get('why', '')}" for s in swipe[-20:]]
    return "\n".join(out)
