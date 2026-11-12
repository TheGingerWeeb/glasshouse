"""Probe candidate URLs and print status, final URL and title.

    .\\.venv\\Scripts\\python.exe scripts\\probe_urls.py https://a https://b
"""

from __future__ import annotations

import asyncio
import sys

import httpx

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


async def one(client: httpx.AsyncClient, url: str) -> None:
    try:
        resp = await client.get(url)
    except httpx.HTTPError as exc:
        print(f"{type(exc).__name__:>18}  {url}")
        return
    body = resp.text[:120_000].lower()
    title = ""
    if "<title" in body:
        title = body.split("<title", 1)[1].split(">", 1)[-1].split("</title", 1)[0].strip()[:70]
    words = [w for w in ("opt out", "opt-out", "remove", "suppression", "privacy", "contact", "delete") if w in body]
    print(f"{resp.status_code:>18}  {url}\n{'':>18}  -> {resp.url}\n{'':>18}  title={title!r} words={words}")


async def main() -> int:
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(20.0, connect=10.0),
        follow_redirects=True,
        headers={"User-Agent": UA, "Accept-Language": "en-GB,en;q=0.9"},
    ) as client:
        for url in sys.argv[1:]:
            await one(client, url)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
