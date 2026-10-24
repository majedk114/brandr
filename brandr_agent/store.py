"""File-based workspace: one folder per account, everything human-readable and diffable."""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

AUTONOMY = ("draft", "approval", "auto")


def now() -> datetime:
    return datetime.now(timezone.utc)


def parse_ts(s: str) -> datetime:
    d = datetime.fromisoformat(s.replace("Z", "+00:00"))
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def home() -> Path:
    return Path(os.environ.get("BRANDR_HOME", "data"))


class Account:
    def __init__(self, slug: str, root: Path | None = None):
        self.slug = slug
        self.dir = (root or home()) / slug
        self.profile_path = self.dir / "profile.json"
        self.playbook_path = self.dir / "playbook.md"
        self.posts_dir = self.dir / "posts"
        self.log_path = self.dir / "log.jsonl"

    # ---- setup -------------------------------------------------------
    @classmethod
    def create(cls, slug: str, profile: dict, root: Path | None = None) -> "Account":
        a = cls(slug, root)
        a.posts_dir.mkdir(parents=True, exist_ok=True)
        a.profile_path.write_text(json.dumps(profile, ensure_ascii=False, indent=2), "utf-8")
        if not a.playbook_path.exists():
            a.playbook_path.write_text(
                "# Playbook\n\nما تعلّمناه عن هذا الحساب. يحدّثه الـ agent بعد كل دورة تحليل.\n\n"
                "## What works\n- (لا بيانات بعد)\n\n## What fails\n- (لا بيانات بعد)\n\n"
                "## Open experiments\n- (لا شيء)\n", "utf-8")
        return a

    @classmethod
    def all(cls, root: Path | None = None) -> list["Account"]:
        r = root or home()
        return [cls(p.parent.name, root) for p in sorted(r.glob("*/profile.json"))] if r.exists() else []

    # ---- profile / playbook -----------------------------------------
    @property
    def profile(self) -> dict:
        p = json.loads(self.profile_path.read_text("utf-8"))
        if p.get("autonomy", "draft") not in AUTONOMY:
            raise ValueError(f"autonomy must be one of {AUTONOMY}")
        return p

    @property
    def autonomy(self) -> str:
        return self.profile.get("autonomy", "draft")  # safest default

    def playbook(self) -> str:
        return self.playbook_path.read_text("utf-8") if self.playbook_path.exists() else ""

    def write_playbook(self, text: str) -> None:
        self.playbook_path.write_text(text, "utf-8")

    # ---- posts -------------------------------------------------------
    def save_post(self, post: dict) -> dict:
        self.posts_dir.mkdir(parents=True, exist_ok=True)
        (self.posts_dir / f"{post['id']}.json").write_text(
            json.dumps(post, ensure_ascii=False, indent=2), "utf-8")
        return post

    def new_post(self, **fields) -> dict:
        post = {"id": uuid.uuid4().hex[:10], "created_at": now().isoformat(),
                "status": "draft", "metrics": {}, **fields}
        return self.save_post(post)

    def get_post(self, pid: str) -> dict:
        return json.loads((self.posts_dir / f"{pid}.json").read_text("utf-8"))

    def posts(self, status: str | None = None) -> list[dict]:
        out = [json.loads(p.read_text("utf-8")) for p in sorted(self.posts_dir.glob("*.json"))]
        out = [p for p in out if status is None or p["status"] == status]
        return sorted(out, key=lambda p: p.get("scheduled_for") or p["created_at"])

    # ---- log ---------------------------------------------------------
    def log(self, event: str, **data) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": now().isoformat(), "event": event, **data}, ensure_ascii=False) + "\n")
