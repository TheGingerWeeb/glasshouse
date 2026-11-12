"""Audit every automated profile probe.

Each site is tested twice:

  * a known username (default ``torvalds``) -- expected to be found
  * a gibberish username (default ``zzqx8f3k9v0m2``) -- must not be found

A site that reports "found" for the gibberish name is a false positive and
should be marked ``soft`` or removed from ``app/data/sites.json``.

    .\\.venv\\Scripts\\python.exe scripts\\audit_sites.py
    .\\.venv\\Scripts\\python.exe scripts\\audit_sites.py --known torvalds --fake zzqx8f3k9v0m2
    .\\.venv\\Scripts\\python.exe scripts\\audit_sites.py --json audit.json

Exit code is 1 when any false positive is seen, so it can gate a commit.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.config import settings  # noqa: E402
from app.scanner import engine  # noqa: E402

DEFAULT_KNOWN = "torvalds"
DEFAULT_FAKE = "zzqx8f3k9v0m2"

VERDICT = {
    ("found", "absent"): "OK",
    ("found", "ambiguous"): "SOFT",
    ("found", "blocked"): "BLOCKED",
    ("found", "error"): "ERROR",
    ("found", "timeout"): "TIMEOUT",
    ("absent", "absent"): "both absent",
    ("absent", "ambiguous"): "unclear",
    ("ambiguous", "absent"): "unclear",
    ("ambiguous", "ambiguous"): "unclear",
    ("blocked", "absent"): "blocked",
    ("blocked", "blocked"): "blocked",
    ("error", "absent"): "error",
    ("error", "error"): "error",
    ("timeout", "absent"): "timeout",
    ("timeout", "timeout"): "timeout",
}


async def timed_probe(client: httpx.AsyncClient, sem: asyncio.Semaphore, site: dict, username: str):
    start = time.perf_counter()
    result = await engine._probe(client, sem, site, username)
    return result, time.perf_counter() - start


async def run(username: str, concurrency: int) -> dict[str, tuple[dict, float]]:
    sites = [s for s in engine.load_sites() if not s.get("manual")]
    sem = asyncio.Semaphore(concurrency)
    limits = httpx.Limits(max_connections=concurrency + 10, max_keepalive_connections=10)
    timeout = httpx.Timeout(settings.site_timeout, connect=5.0)
    headers = {
        "User-Agent": settings.user_agent,
        "Accept": "application/json, text/html;q=0.9, */*;q=0.8",
    }
    async with httpx.AsyncClient(
        follow_redirects=True, timeout=timeout, limits=limits, headers=headers, http2=False
    ) as client:
        rows = await asyncio.gather(
            *(timed_probe(client, sem, site, username) for site in sites)
        )
        results = {site["id"]: row for site, row in zip(sites, rows)}
        # Match the scanner: retry connection failures once, serially.
        retry_sem = asyncio.Semaphore(1)
        for site in sites:
            result, _ = results[site["id"]]
            if result["state"] in {"error", "timeout"}:
                results[site["id"]] = await timed_probe(client, retry_sem, site, username)
    return results


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--known", default=DEFAULT_KNOWN)
    parser.add_argument("--fake", default=DEFAULT_FAKE)
    parser.add_argument("--concurrency", type=int, default=10)
    parser.add_argument("--json", dest="json_path", help="write full results to a JSON file")
    args = parser.parse_args()

    print(f"known user : {args.known}")
    print(f"gibberish  : {args.fake}\n")

    known, fake = await asyncio.gather(
        run(args.known, args.concurrency),
        run(args.fake, args.concurrency),
    )

    header = f"{'site':<26} {'cat':<13} {'kind':<8} {'known':<10} {'fake':<10} {'verdict':<10} {'ms':>6}"
    print(header)
    print("-" * len(header))

    problems: list[str] = []
    audit: dict[str, dict] = {}

    for site_id in known:
        site = next(s for s in engine.load_sites() if s["id"] == site_id)
        known_result, known_ms = known[site_id]
        fake_result, fake_ms = fake[site_id]
        if fake_result["state"] == "found":
            verdict = "FALSE+"
        else:
            verdict = VERDICT.get((known_result["state"], fake_result["state"]), "?")
        if verdict == "FALSE+":
            problems.append(f"{site['name']}: found for the gibberish name")

        print(
            f"{site['name'][:26]:<26} {site.get('category', 'other')[:13]:<13} "
            f"{site.get('kind', 'status'):<8} {known_result['state']:<10} {fake_result['state']:<10} "
            f"{verdict:<10} {known_ms * 1000:>6.0f}"
        )
        audit[site_id] = {
            "name": site["name"],
            "category": site.get("category", "other"),
            "kind": site.get("kind", "status"),
            "known_ms": round(known_ms * 1000),
            "fake_ms": round(fake_ms * 1000),
            "known": known_result,
            "fake": fake_result,
            "verdict": verdict,
        }

    print()
    counts: dict[str, int] = {}
    for row in audit.values():
        counts[row["verdict"]] = counts.get(row["verdict"], 0) + 1
    print(", ".join(f"{key}: {value}" for key, value in sorted(counts.items())))

    if problems:
        print("\nNeeds attention:")
        for line in problems:
            print(f"  - {line}")

    if args.json_path:
        Path(args.json_path).write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
        print(f"\nwrote {args.json_path}")

    return 1 if any(row["verdict"] == "FALSE+" for row in audit.values()) else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
