"""Inspect a probe's raw response for two usernames.

    .\\.venv\\Scripts\\python.exe scripts/inspect_probe.py pypi cratesio codechef

Prints status, title, length and the first ~300 characters of visible text for
the known and gibberish user. Used to find a reliable absent marker.
"""

from __future__ import annotations

import asyncio
import re
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.config import settings  # noqa: E402
from app.scanner import engine  # noqa: E402

KNOWN = "torvalds"
FAKE = "zzqx8f3k9v0m2"


def text_of(body: str) -> str:
    body = re.sub(r"<script.*?</script>", " ", body, flags=re.S | re.I)
    body = re.sub(r"<style.*?</style>", " ", body, flags=re.S | re.I)
    body = re.sub(r"<[^>]+>", " ", body)
    body = re.sub(r"\s+", " ", body)
    return body.strip()


async def one(client: httpx.AsyncClient, site: dict, username: str) -> None:
    url = engine._fill(site.get("check") or site["url"], username)
    try:
        resp = await client.get(url)
    except httpx.HTTPError as exc:
        print(f"  {username:<18} {type(exc).__name__}: {exc}")
        return
    title = ""
    match = re.search(r"<title[^>]*>(.*?)</title>", resp.text, flags=re.S | re.I)
    if match:
        title = re.sub(r"\s+", " ", match.group(1)).strip()[:80]
    body = text_of(resp.text)
    print(f"  {username:<18} {resp.status_code}  {len(resp.content):>7} bytes  title={title!r}")
    print(f"    {body[:300]!r}")


async def main() -> int:
    ids = sys.argv[1:]
    sites = {s["id"]: s for s in engine.load_sites()}
    async with httpx.AsyncClient(
        follow_redirects=True,
        timeout=httpx.Timeout(settings.site_timeout, connect=5.0),
        headers={"User-Agent": settings.user_agent, "Accept": "text/html,application/json;q=0.9,*/*;q=0.8"},
    ) as client:
        for site_id in ids:
            site = sites.get(site_id)
            if not site:
                print(f"unknown id: {site_id}")
                continue
            print(f"\n{site['name']} ({site_id})")
            for username in (KNOWN, FAKE):
                await one(client, site, username)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
