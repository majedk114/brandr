"""One autonomous cycle per account: sync -> analyze/learn -> plan/create. Accounts are isolated."""
from __future__ import annotations

import traceback

from . import prompts, tools
from .llm import default_client, run_agent
from .publishers import get_publisher, publish_due, sync_metrics
from .store import Account, now, parse_ts


def run_account(acc: Account, client=None, publisher=None) -> dict:
    client = client or default_client()
    publisher = publisher or get_publisher()
    prof = acc.profile
    report: dict = {"account": acc.slug, "autonomy": acc.autonomy}

    # 1) act on the world: publish what's due, pull fresh numbers
    report["published"] = [p["id"] for p in publish_due(acc, publisher)]
    report["metrics_synced"] = sync_metrics(acc, publisher)

    # 2) learn
    if any(p.get("metrics") for p in acc.posts("published")):
        t, h, _ = tools.build(acc, client, "analyze")
        report["analysis"] = run_agent(client, prompts.ANALYST, f"Now (UTC): {now().isoformat()}. "
                                       f"Analyze performance and update the playbook.", t, h, max_turns=15)

    # 3) plan + create, only if the queue is running low
    horizon = prof.get("queue_days", 7)
    upcoming = [p for p in acc.posts() if p["status"] in ("approved", "draft") and p.get("scheduled_for")
                and 0 <= (parse_ts(p["scheduled_for"]) - now()).days < horizon]
    target = prof.get("posts_per_week", 4) * horizon // 7
    if len(upcoming) >= target:
        report["planning"] = f"skipped: queue already has {len(upcoming)}/{target} posts"
    else:
        t, h, state = tools.build(acc, client, "plan")
        report["planning"] = run_agent(
            client, prompts.PLANNER,
            f"Now (UTC): {now().isoformat()}. Horizon: next {horizon} days. Target: {target - len(upcoming)} more "
            f"posts across platforms {prof.get('platforms')}. Autonomy mode: {acc.autonomy}.", t, h, max_turns=60)
        report["created"] = state["created"]
    acc.log("cycle_done", **{k: v for k, v in report.items() if k != "account"})
    return report


def run_all(accounts: list[Account], **kw) -> list[dict]:
    out = []
    for acc in accounts:
        try:
            out.append(run_account(acc, **kw))
        except Exception as e:
            acc.log("cycle_error", error=str(e), trace=traceback.format_exc())
            out.append({"account": acc.slug, "error": str(e)})
    return out
