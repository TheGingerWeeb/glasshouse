"""Check every broker opt-out link and record what happened.

    .\\.venv\\Scripts\\python.exe scripts\\verify_links.py
    .\\.venv\\Scripts\\python.exe scripts\\verify_links.py --write

Status meanings:
  ok         page answered and mentions removal / privacy wording
  unverified page answered but looks like a homepage or generic shell
  blocked    the site blocks automated clients (Cloudflare etc.); a browser usually works
  broken     404 / 410 / other hard failure
  error      connection failed

With --write it updates app/data/brokers.json with the status and, for "ok"
links, today's date in "verified".
"""

from __future__ import annotations

import asyncio
import json
import sys
from datetime import date
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "app" / "data" / "brokers.json"

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

KEYWORDS = ("opt out", "opt-out", "optout", "remove", "suppression", "privacy", "delete", "kontakt", "contact")
BLOCK_CODES = {401, 403, 407, 429, 503}


def classify(code: int | None, hit: bool) -> str:
    if code is None:
        return "error"
    if code in BLOCK_CODES:
        return "blocked"
    if code in (404, 410) or code >= 500:
        return "broken"
    if 200 <= code < 400:
        return "ok" if hit else "unverified"
    return "broken"


async def check(client: httpx.AsyncClient, url: str) -> tuple[int | None, str, bool]:
    try:
        resp = await client.get(url)
    except httpx.HTTPError as exc:
        return None, type(exc).__name__, False
    title = ""
    body = ""
    if "html" in resp.headers.get("content-type", ""):
        body = resp.text.lower()[:200_000]
        if "<title" in body:
            title = body.split("<title", 1)[1].split(">", 1)[-1].split("</title", 1)[0].strip()[:70]
    else:
        body = resp.text.lower()[:20_000]
    hit = any(word in body for word in KEYWORDS)
    return resp.status_code, title or "-", hit


async def main() -> int:
    write = "--write" in sys.argv
    payload = json.loads(DATA.read_text(encoding="utf-8"))
    today = date.today().isoformat()
    counts: dict[str, int] = {}

    async with httpx.AsyncClient(
        timeout=httpx.Timeout(20.0, connect=10.0),
        follow_redirects=True,
        headers={"User-Agent": UA, "Accept-Language": "en-GB,en;q=0.9"},
    ) as client:
        for code, region in payload["regions"].items():
            for broker in region["brokers"]:
                status_code, title, hit = await check(client, broker["optout_url"])
                status = classify(status_code, hit)
                counts[status] = counts.get(status, 0) + 1
                if write:
                    broker["status"] = status
                    broker["verified"] = today if status == "ok" else None
                print(f"{code:>3}  {str(status_code):>4}  {status:<10}  {broker['name']:<24} {title}")

    if write:
        DATA.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"\nupdated {DATA}")

    print("\n" + ", ".join(f"{k}: {v}" for k, v in sorted(counts.items())))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
