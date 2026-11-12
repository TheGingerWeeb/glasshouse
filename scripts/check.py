"""Offline checks: build a fake job, generate a report, render every template.

Run with:  .\\.venv\\Scripts\\python.exe scripts\\check.py
No network access is used, so it is safe to run anywhere.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from jinja2 import Environment, FileSystemLoader, select_autoescape  # noqa: E402

from app.config import settings  # noqa: E402
from app.jobs import Job  # noqa: E402
from app.scanner import cleanup, report  # noqa: E402


def fake_job() -> Job:
    job = Job(
        id="demo123",
        created=time.time(),
        profile={
            "username": "gingerveeb",
            "emails": ["me@example.com"],
            "name": "Alex Smith",
            "city": "Manchester",
        },
        regions=["US", "UK"],
        status="done",
        done=44,
        total=44,
    )
    job.accounts = [
        {"id": "github", "name": "GitHub", "category": "dev", "host": "github.com",
         "url": "https://github.com/gingerveeb", "state": "found", "confidence": "high", "note": ""},
        {"id": "steam", "name": "Steam", "category": "gaming", "host": "steamcommunity.com",
         "url": "https://steamcommunity.com/id/gingerveeb", "state": "found", "confidence": "high", "note": ""},
        {"id": "trello", "name": "Trello", "category": "professional", "host": "trello.com",
         "url": "https://trello.com/gingerveeb", "state": "ambiguous", "confidence": "low",
         "note": "Page loaded, but this site is known to answer 200 for missing profiles."},
        {"id": "reddit", "name": "Reddit", "category": "social", "host": "reddit.com",
         "url": "https://www.reddit.com/user/gingerveeb/", "state": "blocked", "confidence": "low",
         "note": "The site refused the lookup."},
    ]
    job.emails = [{"email": "me@example.com", "gravatar": "found",
                   "gravatar_url": "https://gravatar.com/abc123"}]
    job.manual = [{"name": "X / Twitter", "url": "https://x.com/gingerveeb",
                   "why": "Blocks automated lookups."}]
    job.links = __import__("app.scanner.links", fromlist=["build"]).build(
        job.profile, [a for a in job.accounts if a["state"] == "found"]
    )
    job.tracker = {"task:passkeys": "done", "account:github": "done"}
    job.brokers = {
        "broker:US:spokeo": {
            "state": "submitted",
            "submitted": "2026-11-12",
            "follow_up": "2027-02-10",
            "notes": "ticket 12345",
        },
        "broker:UK:192com": {
            "state": "removed",
            "submitted": "2026-11-01",
            "follow_up": "",
            "notes": "",
        },
    }
    return job


def main() -> int:
    job = fake_job()
    summary = report.build(job)
    assert summary["total_items"] > 0, "cleanup list should have items"
    assert summary["done_items"] >= 2, summary["done_items"]
    assert summary["broker_groups"], "broker regions should render"
    assert summary["broker_total"] > 0, "broker totals should count"
    assert summary["followups"], "follow-ups should render"
    assert summary["links"], "search links should render"

    env = Environment(
        loader=FileSystemLoader(str(ROOT / "app" / "templates")),
        autoescape=select_autoescape(["html"]),
    )
    base = {"settings": settings, "regions": cleanup.region_choices()}

    pages = {
        "index.html": dict(base, wiped=0, error="", cooldown=settings.scan_cooldown_seconds),
        "index.html#rate": dict(base, wiped=0, error="rate", cooldown=settings.scan_cooldown_seconds, wait=42),
        "scan.html": dict(base, job=job),
        "report.html": dict(base, job=job, summary=summary),
        "error.html": dict(base, job=job),
        "privacy.html": dict(base),
    }

    for name, context in pages.items():
        template = env.get_template(name.split("#")[0])
        html = template.render(**context)
        assert "<html" in html or "<!doctype" in html.lower()
        print(f"rendered {name}: {len(html)} bytes")

    print("OK — report and templates look healthy")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
