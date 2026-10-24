from __future__ import annotations

import argparse
import json
import sys
import time

from .cycle import run_all
from .publishers import get_publisher, publish_due, sync_metrics
from .store import Account, now

TEMPLATE = {
    "brand": "اسم البراند", "about": "ماذا يبيع / يقدّم، وما الذي يميّزه",
    "audience": "من الجمهور؟ أين؟ ما ألمهم ورغباتهم؟",
    "language": "العربية - لهجة سودانية/خليجية بيضاء", "voice": ["قريب", "واثق", "بدون مبالغة"],
    "goals": ["زيادة الوعي", "رسائل واتساب"], "platforms": ["instagram", "facebook"],
    "pillars": ["تعليمي", "خلف الكواليس", "إثبات اجتماعي", "عرض"],
    "banned_words": [], "posts_per_week": 4, "queue_days": 7,
    "limits": {"max_posts_per_day": 1, "min_hours_between_posts": 8},
    "autonomy": "approval",
}


def _acc(slug: str) -> Account:
    a = Account(slug)
    if not a.profile_path.exists():
        sys.exit(f"no such account: {slug} (run `brandr init {slug}`)")
    return a


def main(argv=None):
    ap = argparse.ArgumentParser("brandr")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init").add_argument("slug")
    r = sub.add_parser("run"); r.add_argument("--account")
    d = sub.add_parser("daemon"); d.add_argument("--account"); d.add_argument("--every-minutes", type=int, default=60)
    sub.add_parser("status").add_argument("slug", nargs="?")
    for n in ("approve", "reject"):
        p = sub.add_parser(n); p.add_argument("slug"); p.add_argument("post", help="post id or 'all'")
    m = sub.add_parser("metrics"); m.add_argument("slug"); m.add_argument("file", help='JSON {"<post_id>": {"likes": 10}}')
    a = ap.parse_args(argv)

    if a.cmd == "init":
        acc = Account.create(a.slug, TEMPLATE)
        print(f"created {acc.profile_path} — edit it, then `brandr run --account {a.slug}`")
    elif a.cmd in ("run", "daemon"):
        accounts = [_acc(a.account)] if a.account else Account.all()
        if not accounts:
            sys.exit("no accounts; run `brandr init <slug>`")
        while True:
            print(json.dumps(run_all(accounts), ensure_ascii=False, indent=2))
            if a.cmd == "run":
                break
            time.sleep(a.every_minutes * 60)
    elif a.cmd == "status":
        for acc in ([_acc(a.slug)] if a.slug else Account.all()):
            ps = acc.posts()
            counts = {s: sum(p["status"] == s for p in ps) for s in ("draft", "approved", "published", "failed")}
            print(f"[{acc.slug}] autonomy={acc.autonomy} {counts}")
            for p in ps:
                if p["status"] in ("draft", "approved"):
                    flag = " (needs media)" if p.get("needs_media") else ""
                    print(f"  {p['id']} {p['status']:8} {p['scheduled_for']} {p['platform']}/{p.get('format')}{flag}\n"
                          f"     {p['caption'][:90]!r}")
    elif a.cmd in ("approve", "reject"):
        acc = _acc(a.slug)
        for p in acc.posts("draft"):
            if a.post in ("all", p["id"]):
                if a.cmd == "approve" and p.get("needs_media"):
                    print(f"skip {p['id']}: needs media_url first"); continue
                p["status"] = "approved" if a.cmd == "approve" else "rejected"
                acc.save_post(p); acc.log(a.cmd, post=p["id"]); print(f"{p['id']} -> {p['status']}")
    elif a.cmd == "metrics":
        acc = _acc(a.slug)
        for pid, mm in json.load(open(a.file)).items():
            p = acc.get_post(pid); p["metrics"] = {**p.get("metrics", {}), **mm}; acc.save_post(p)
        print("imported")


if __name__ == "__main__":
    main()
