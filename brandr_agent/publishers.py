"""Publishers. DryRun is the default; Meta posts to a Facebook Page / Instagram for real."""
from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request

from .store import Account


class PublishError(Exception):
    pass


class DryRunPublisher:
    """Writes to outbox.jsonl instead of posting. Safe default."""
    name = "dryrun"

    def publish(self, acc: Account, post: dict) -> str:
        with (acc.dir / "outbox.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(post, ensure_ascii=False) + "\n")
        return f"dryrun-{post['id']}"

    def fetch_metrics(self, acc: Account, post: dict) -> dict:
        return {}  # use `brandr metrics import` to feed numbers in


class MetaPublisher:
    """Facebook Page + Instagram via Graph API. Needs per-account env vars:
    META_TOKEN_<SLUG>, META_PAGE_ID_<SLUG>, META_IG_ID_<SLUG>.  Instagram requires media_url."""
    name = "meta"
    API = "https://graph.facebook.com/v21.0"

    def _call(self, path: str, params: dict, method: str = "POST") -> dict:
        data = urllib.parse.urlencode(params).encode()
        url = f"{self.API}/{path}"
        req = urllib.request.Request(url + ("?" + data.decode() if method == "GET" else ""),
                                     data=None if method == "GET" else data, method=method)
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read())
        except Exception as e:
            raise PublishError(str(e)) from e

    def _env(self, acc: Account, key: str) -> str:
        v = os.environ.get(f"{key}_{acc.slug.upper().replace('-', '_')}")
        if not v:
            raise PublishError(f"missing env {key}_{acc.slug.upper().replace('-', '_')}")
        return v

    def publish(self, acc: Account, post: dict) -> str:
        token = self._env(acc, "META_TOKEN")
        text = post["caption"] + ("\n\n" + " ".join(post["hashtags"]) if post.get("hashtags") else "")
        if post["platform"] == "facebook":
            page = self._env(acc, "META_PAGE_ID")
            if post.get("media_url"):
                r = self._call(f"{page}/photos", {"url": post["media_url"], "caption": text, "access_token": token})
            else:
                r = self._call(f"{page}/feed", {"message": text, "access_token": token})
            return r["id"]
        if post["platform"] == "instagram":
            if not post.get("media_url"):
                raise PublishError("instagram needs media_url")
            ig = self._env(acc, "META_IG_ID")
            key = "video_url" if post.get("format") in ("reel", "video") else "image_url"
            extra = {"media_type": "REELS"} if key == "video_url" else {}
            c = self._call(f"{ig}/media", {key: post["media_url"], "caption": text, "access_token": token, **extra})
            return self._call(f"{ig}/media_publish", {"creation_id": c["id"], "access_token": token})["id"]
        raise PublishError(f"unsupported platform {post['platform']}")

    def fetch_metrics(self, acc: Account, post: dict) -> dict:
        token = self._env(acc, "META_TOKEN")
        pid = post["external_id"]
        if post["platform"] == "instagram":
            r = self._call(f"{pid}/insights", {"metric": "reach,likes,comments,shares,saved",
                                               "access_token": token}, "GET")
            return {m["name"]: m["values"][0]["value"] for m in r.get("data", [])}
        r = self._call(pid, {"fields": "reactions.summary(true),comments.summary(true),shares",
                             "access_token": token}, "GET")
        return {"reactions": r.get("reactions", {}).get("summary", {}).get("total_count", 0),
                "comments": r.get("comments", {}).get("summary", {}).get("total_count", 0),
                "shares": r.get("shares", {}).get("count", 0)}


def get_publisher(name: str | None = None):
    name = name or os.environ.get("BRANDR_PUBLISHER", "dryrun")
    return {"dryrun": DryRunPublisher, "meta": MetaPublisher}[name]()


def publish_due(acc: Account, publisher) -> list[dict]:
    """Publish approved posts whose time has come. Returns the posts touched."""
    from .store import now, parse_ts
    done = []
    for p in acc.posts("approved"):
        if parse_ts(p["scheduled_for"]) > now():
            continue
        try:
            p["external_id"] = publisher.publish(acc, p)
            p["status"], p["published_at"] = "published", now().isoformat()
            acc.log("published", post=p["id"], external_id=p["external_id"])
        except PublishError as e:
            p["status"], p["error"] = "failed", str(e)
            acc.log("publish_failed", post=p["id"], error=str(e))
        acc.save_post(p)
        done.append(p)
    return done


def sync_metrics(acc: Account, publisher) -> int:
    n = 0
    for p in acc.posts("published"):
        try:
            m = publisher.fetch_metrics(acc, p)
        except PublishError as e:
            acc.log("metrics_failed", post=p["id"], error=str(e))
            continue
        if m:
            p["metrics"] = {**p.get("metrics", {}), **m}
            acc.save_post(p)
            n += 1
    return n
