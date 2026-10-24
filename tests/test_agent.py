import json, os, tempfile, unittest
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace as NS

os.environ["BRANDR_THINKING_BUDGET"] = "0"
from brandr_agent import cycle, store
from brandr_agent.publishers import DryRunPublisher
from brandr_agent.store import Account, now

PROFILE = json.loads(Path("accounts/example/profile.json").read_text("utf-8"))


def tu(i, name, **inp):
    return NS(type="tool_use", id=f"t{i}", name=name, input=inp)


class FakeClient:
    """Scripted model: tool turns for agents, canned verdict for the critic (calls without tools)."""
    def __init__(self, turns, score=9):
        self.turns, self.score, self.messages = list(turns), score, self
    def create(self, **kw):
        if "tools" not in kw:
            return NS(content=[NS(type="text", text=json.dumps({"score": self.score, "issues": [], "fix": ""}))])
        return NS(content=self.turns.pop(0))


def when(h):
    return (now() + timedelta(hours=h)).isoformat()


class T(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        os.environ["BRANDR_HOME"] = str(self.root)

    def acc(self, **over):
        return Account.create("kcs", {**PROFILE, **over}, self.root)

    def post(self, **o):
        return {**dict(platform="facebook", format="text", pillar="عروض", caption="أهلاً", hypothesis="h",
                       scheduled_for=when(24)), **o}

    def run_plan(self, acc, posts, score=9):
        turns = [[tu(i, "create_post", **p)] for i, p in enumerate(posts)] + [[tu(99, "finish", summary="done")]]
        return cycle.run_account(acc, FakeClient(turns, score), DryRunPublisher())

    def test_approval_mode_creates_drafts_and_guardrails_block(self):
        acc = self.acc()
        r = self.run_plan(acc, [self.post(caption="الأفضل في العالم"), self.post(caption="عرض اليوم")])
        ps = acc.posts()
        self.assertEqual([p["status"] for p in ps], ["draft"])        # banned word rejected, other saved
        self.assertEqual(len(r["created"]), 1)

    def test_auto_mode_approves_but_instagram_without_media_stays_draft(self):
        acc = self.acc(autonomy="auto")
        self.run_plan(acc, [self.post(), self.post(platform="instagram", format="image",
                                                   caption="ثاني", scheduled_for=when(48))])
        by = {p["platform"]: p for p in acc.posts()}
        self.assertEqual(by["facebook"]["status"], "approved")
        self.assertEqual(by["instagram"]["status"], "draft")
        self.assertTrue(by["instagram"]["needs_media"])

    def test_critic_rejects_weak_posts(self):
        acc = self.acc()
        self.run_plan(acc, [self.post()], score=4)
        self.assertEqual(acc.posts(), [])

    def test_daily_cap_and_duplicates(self):
        acc = self.acc()
        t = when(24)
        self.run_plan(acc, [self.post(scheduled_for=t), self.post(caption="ثاني", scheduled_for=t)])
        self.assertEqual(len(acc.posts()), 1)

    def test_publish_due_then_learn_loop(self):
        acc = self.acc(autonomy="auto", posts_per_week=0)
        p = acc.new_post(platform="facebook", format="text", pillar="عروض", caption="x", hashtags=[],
                         scheduled_for=when(-1), status="approved", hypothesis="h")
        turns = [[tu(1, "get_performance")], [tu(2, "update_playbook", markdown="# P\n- عروض تنجح")],
                 [tu(3, "finish", summary="ok")]]
        # first run publishes (no metrics yet -> no analysis)
        cycle.run_account(acc, FakeClient([]), DryRunPublisher())
        self.assertEqual(acc.get_post(p["id"])["status"], "published")
        q = acc.get_post(p["id"]); q["metrics"] = {"likes": 10, "comments": 2, "reach": 100}; acc.save_post(q)
        cycle.run_account(acc, FakeClient(turns), DryRunPublisher())
        self.assertIn("عروض تنجح", acc.playbook())

    def test_one_account_failure_is_isolated(self):
        good, bad = self.acc(posts_per_week=0), Account.create("bad", {**PROFILE, "autonomy": "nope"}, self.root)
        out = cycle.run_all([bad, good], client=FakeClient([]), publisher=DryRunPublisher())
        self.assertIn("error", out[0]); self.assertNotIn("error", out[1])


if __name__ == "__main__":
    unittest.main()
