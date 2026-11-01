"""مساحة عمل الحساب: كل حساب مجلد مستقل تحت accounts/. لا شيء هنا يقرأ مجلد حساب آخر."""
from __future__ import annotations

import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

AUTONOMY = ("every_post", "plan_only", "auto")
SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{1,40}$")
PLAN_STATUS = re.compile(r"<!--\s*status:\s*(\w+)\s*-->")


def now() -> datetime:
    return datetime.now(timezone.utc)


def parse_ts(s: str) -> datetime:
    d = datetime.fromisoformat(s.replace("Z", "+00:00"))
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def root() -> Path:
    return Path(os.environ.get("GENX_ROOT", Path(__file__).resolve().parent.parent))


class Account:
    def __init__(self, slug: str, base: Path | None = None):
        if not SLUG.match(slug):
            raise ValueError(f"اسم حساب غير صالح: {slug!r} (حروف إنجليزية صغيرة وأرقام و-)")
        self.slug = slug
        self.dir = (base or root()) / "accounts" / slug
        self.posts_dir = self.dir / "posts"
        self.plans_dir = self.dir / "plans"
        self.media_dir = self.dir / "media"

    @property
    def exists(self) -> bool:
        return (self.dir / "config.json").exists()

    @classmethod
    def all(cls, base: Path | None = None) -> list["Account"]:
        d = (base or root()) / "accounts"
        return [cls(p.parent.name, base) for p in sorted(d.glob("*/config.json"))] if d.exists() else []

    # ---- config / docs ----------------------------------------------
    @property
    def config(self) -> dict:
        c = json.loads((self.dir / "config.json").read_text("utf-8"))
        if c.get("autonomy", "every_post") not in AUTONOMY:
            raise ValueError(f"[{self.slug}] autonomy يجب أن يكون واحد من {AUTONOMY}")
        return c

    def save_config(self, c: dict) -> None:
        (self.dir / "config.json").write_text(json.dumps(c, ensure_ascii=False, indent=2) + "\n", "utf-8")

    @property
    def autonomy(self) -> str:
        return self.config.get("autonomy", "every_post")

    def doc(self, name: str) -> str:
        p = self.dir / name
        return p.read_text("utf-8") if p.exists() else ""

    # ---- plans --------------------------------------------------------
    def plan_path(self, week: str) -> Path:
        if not re.match(r"^\d{4}-W\d{2}$", week):
            raise ValueError(f"الأسبوع بصيغة 2026-W45، وصلني {week!r}")
        return self.plans_dir / f"{week}.md"

    def plan_status(self, week: str) -> str | None:
        p = self.plan_path(week)
        if not p.exists():
            return None
        m = PLAN_STATUS.search(p.read_text("utf-8"))
        return m.group(1) if m else "proposed"

    def set_plan_status(self, week: str, status: str) -> None:
        p = self.plan_path(week)
        text = p.read_text("utf-8")
        tag = f"<!-- status: {status} -->"
        text = PLAN_STATUS.sub(tag, text, count=1) if PLAN_STATUS.search(text) else f"{tag}\n{text}"
        p.write_text(text, "utf-8")

    def plans(self) -> list[tuple[str, str]]:
        return [(p.stem, self.plan_status(p.stem)) for p in sorted(self.plans_dir.glob("*.md"))]

    # ---- posts --------------------------------------------------------
    def post_path(self, pid: str) -> Path:
        if not re.match(r"^[a-z0-9]{6,12}$", pid):
            raise ValueError(f"رقم منشور غير صالح: {pid!r}")
        return self.posts_dir / f"{pid}.json"

    def get_post(self, pid: str) -> dict:
        p = self.post_path(pid)
        if not p.exists():
            raise KeyError(f"[{self.slug}] ما في منشور {pid}")
        return json.loads(p.read_text("utf-8"))

    def save_post(self, post: dict) -> dict:
        self.posts_dir.mkdir(parents=True, exist_ok=True)
        self.post_path(post["id"]).write_text(json.dumps(post, ensure_ascii=False, indent=2) + "\n", "utf-8")
        return post

    def new_post_id(self) -> str:
        return uuid.uuid4().hex[:8]

    def posts(self, *statuses: str) -> list[dict]:
        out = [json.loads(p.read_text("utf-8")) for p in self.posts_dir.glob("*.json")]
        out = [p for p in out if not statuses or p["status"] in statuses]
        return sorted(out, key=lambda p: p.get("scheduled_for") or p["created_at"])

    # ---- سجلات JSONL (أبحاث، لقطات نمو، دخل، استفسارات) ----------------
    def append(self, name: str, row: dict) -> dict:
        path = self.dir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        row = {"at": now().isoformat(), **row}
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
        return row

    def rows(self, name: str) -> list[dict]:
        path = self.dir / name
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text("utf-8").splitlines() if line.strip()]

    # ---- decisions log ------------------------------------------------
    def log_decision(self, item: str, decision: str, note: str = "") -> None:
        path = self.dir / "decisions.md"
        if not path.exists():
            path.write_text("# سجل القرارات\n\n| التاريخ | العنصر | القرار | ملاحظة |\n| --- | --- | --- | --- |\n", "utf-8")
        note = note.replace("|", "/").replace("\n", " ")
        with path.open("a", encoding="utf-8") as f:
            f.write(f"| {now():%Y-%m-%d %H:%M} | {item} | {decision} | {note} |\n")
