import json
import os
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path

from genx import posts, reports
from genx.cli import main
from genx.workspace import Account, now

BASE_CFG = {"name": "تجربة", "type": "community", "platforms": ["instagram", "tiktok"], "formats": ["reel", "image"],
            "autonomy": "every_post", "ideas": {"A": "a", "B": "b"}, "banned_words": ["مضمون"],
            "limits": {"max_posts_per_day": 1, "min_hours_between_posts": 12, "max_hashtags": 5,
                       "max_client_posts_per_week": 1}}
WEEK = "2026-W45"


def when(days):
    return (now() + timedelta(days=days)).replace(hour=17, minute=0, second=0, microsecond=0).isoformat()


class Flow(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        os.environ["GENX_ROOT"] = str(self.root)

    def acc(self, slug="test-acc", **over):
        main(["new", slug, "--name", "تجربة"])
        a = Account(slug)
        a.save_config({**BASE_CFG, **over})
        return a

    def plan(self, a, status="approved"):
        a.plans_dir.mkdir(parents=True, exist_ok=True)
        a.plan_path(WEEK).write_text("<!-- status: proposed -->\n# خطة\n", "utf-8")
        if status != "proposed":
            a.set_plan_status(WEEK, status)

    def draft(self, a, **over):
        f = {"plan": WEEK, "idea": "A", "format": "reel", "platforms": ["instagram"], "hook": "خطاف",
             "caption": f"نص {over.get('day', 1)}", "hashtags": ["#x"], "scheduled_for": when(over.pop("day", 1)),
             "hypothesis": "h", "production": {"type": "image", "prompt": "p"}}
        return posts.create(a, {**f, **over})

    def test_full_lifecycle(self):
        a = self.acc(); self.plan(a)
        p = self.draft(a)
        p, issues = posts.submit(a, p["id"])
        self.assertEqual((issues, p["status"]), ([], "review"))
        posts.decide(a, p["id"], "approve")
        self.assertEqual(posts.attach_media(a, p["id"], "https://x/img.png")["status"], "ready")
        posts.mark_published(a, p["id"], {"instagram": "https://ig/p/1"})
        posts.record_metrics(a, p["id"], "instagram", {"reach": 100, "likes": 10, "comments": 2})
        self.assertEqual(reports.score(a.get_post(p["id"])["metrics"]), 16.0)
        self.assertIn("approve", a.doc("decisions.md"))
        self.assertIn(p["id"], reports.account_report(a))

    def test_unapproved_plan_blocks_submit(self):
        a = self.acc(); self.plan(a, "proposed")
        _, issues = posts.submit(a, self.draft(a)["id"])
        self.assertTrue(any("خطة" in i for i in issues))

    def test_plan_only_skips_post_review(self):
        a = self.acc(autonomy="plan_only"); self.plan(a)
        p, _ = posts.submit(a, self.draft(a)["id"])
        self.assertEqual(p["status"], "approved")

    def test_rules(self):
        a = self.acc(ai_label_required=True); self.plan(a)
        bad = self.draft(a, caption="نتيجة مضمون", platforms=["snapchat"], idea="C", client="محل")
        _, issues = posts.submit(a, bad["id"])
        text = " ".join(issues)
        for needle in ("كلمة ممنوعة", "منصات", "الفكرة", "ai_label", "إفصاح"):
            self.assertIn(needle, text)

    def test_daily_cap_and_client_weekly_cap(self):
        a = self.acc(); self.plan(a)
        self.draft(a, day=2)
        _, issues = posts.submit(a, self.draft(a, day=2, caption="آخر")["id"])
        self.assertTrue(any("الحد اليومي" in i for i in issues))
        c1 = self.draft(a, day=10, caption="c1", client="x", paid_disclosure=True)
        self.assertEqual(posts.submit(a, c1["id"])[1], [])
        _, issues = posts.submit(a, self.draft(a, day=11, caption="c2", client="y", paid_disclosure=True)["id"])
        self.assertTrue(any("العملاء" in i for i in issues))

    def test_invalid_transitions(self):
        a = self.acc(); self.plan(a)
        p = self.draft(a)
        with self.assertRaises(posts.TransitionError):
            posts.attach_media(a, p["id"], "x")
        with self.assertRaises(posts.TransitionError):
            posts.record_metrics(a, p["id"], "instagram", {"reach": 1})

    def test_isolation_and_bulk_decide(self):
        a, b = self.acc("acc-a"), self.acc("acc-b")
        for x in (a, b):
            self.plan(x); posts.submit(x, self.draft(x)["id"])
        self.assertEqual(len(reports.queue([a, b])), 2)
        main(["decide", "acc-a", "all", "approve"])
        self.assertEqual([p["status"] for p in a.posts()], ["approved"])
        self.assertEqual([p["status"] for p in b.posts()], ["review"])   # الحساب الثاني ما اتأثر
        main(["decide", "*", f"plan:{WEEK}", "changes", "غيّر"])
        self.assertEqual((a.plan_status(WEEK), b.plan_status(WEEK)), ("changes", "changes"))

    def test_path_safety(self):
        with self.assertRaises(ValueError):
            Account("../etc")
        a = self.acc()
        with self.assertRaises(ValueError):
            a.get_post("../../x")

    def test_portfolio_has_no_content(self):
        a = self.acc(); self.plan(a); self.draft(a, caption="سر الحساب")
        self.assertNotIn("سر الحساب", reports.portfolio([a]))


class RealAccounts(unittest.TestCase):
    def test_repo_accounts_load(self):
        os.environ.pop("GENX_ROOT", None)
        accs = Account.all(Path(__file__).resolve().parent.parent)
        self.assertEqual({a.slug for a in accs}, {"tob-w-dahab", "kisra-w-afia", "hammoudi"})
        for a in accs:
            self.assertIn(set(a.config["ideas"]), [{"A", "B"}])


if __name__ == "__main__":
    unittest.main()
