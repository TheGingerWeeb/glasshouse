from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path
from typing import Any

import httpx

from app.config import settings
from app.jobs import Job
from app.scanner import links as links_mod

DATA = Path(__file__).resolve().parent.parent / "data"
CATEGORY_ORDER = ["dev", "social", "creative", "gaming", "professional", "other"]


def load_sites() -> list[dict]:
    payload = json.loads((DATA / "sites.json").read_text(encoding="utf-8"))
    return payload.get("sites", [])


def _resolve(obj: Any, path: str) -> Any:
    if not path:
        return obj
    current = obj
    for part in path.split("."):
        if isinstance(current, list):
            try:
                current = current[int(part)]
            except (ValueError, IndexError):
                return None
        elif isinstance(current, dict):
            current = current.get(part)
        else:
            return None
        if current is None:
            return None
    return current


def _fill(value: Any, username: str) -> Any:
    if isinstance(value, str):
        return value.replace("{username}", username)
    if isinstance(value, list):
        return [_fill(v, username) for v in value]
    if isinstance(value, dict):
        return {k: _fill(v, username) for k, v in value.items()}
    return value


def _result(site: dict, username: str, state: str, confidence: str, note: str = "") -> dict:
    return {
        "id": site["id"],
        "name": site["name"],
        "category": site.get("category", "other"),
        "host": site.get("host", ""),
        "url": _fill(site["url"], username),
        "state": state,
        "confidence": confidence,
        "note": note,
    }


async def _probe(client: httpx.AsyncClient, sem: asyncio.Semaphore, site: dict, username: str) -> dict:
    async with sem:
        url = _fill(site.get("check") or site["url"], username)
        try:
            if site.get("method", "GET").upper() == "POST":
                resp = await client.post(url, json=_fill(site.get("post_json", {}), username))
            else:
                resp = await client.get(url)
        except httpx.TimeoutException:
            return _result(site, username, "timeout", "low", "The site took too long to answer.")
        except httpx.HTTPError:
            if site.get("subdomain"):
                return _result(site, username, "absent", "medium", "No site exists at that address.")
            return _result(site, username, "error", "low", "Could not reach the site.")

    status = resp.status_code
    absent_status = set(site.get("absent_status", [404, 410]))

    if status in absent_status:
        return _result(site, username, "absent", "high", "")
    if status in (401, 403, 407, 429):
        return _result(site, username, "blocked", "low", "The site refused the lookup. Check it yourself with the link.")
    if status >= 500:
        return _result(site, username, "error", "low", "The site returned a server error.")
    if status >= 400 and status not in absent_status:
        return _result(site, username, "ambiguous", "low", f"Unusual response ({status}).")

    kind = site.get("kind", "status")

    if kind == "json":
        try:
            payload = resp.json()
        except ValueError:
            return _result(site, username, "ambiguous", "low", "Unexpected response format.")
        value = _resolve(payload, site.get("json_path", ""))
        if value in (None, "", False, [], {}):
            return _result(site, username, "absent", "high", "")
        return _result(site, username, "found", "high", "")

    if kind == "text":
        body = resp.text.lower()
        absent = [m.lower() for m in site.get("absent_markers", [])]
        if any(marker in body for marker in absent):
            return _result(site, username, "absent", "high", "")
        present = [m.lower() for m in site.get("present_markers", [])]
        if present and not any(marker in body for marker in present):
            return _result(site, username, "ambiguous", "low", "Page loaded but the profile could not be confirmed.")
        return _result(site, username, "found", "high", "")

    # kind == "status"
    if site.get("soft"):
        return _result(site, username, "ambiguous", "low", "Page loaded, but this site is known to answer 200 for missing profiles.")
    return _result(site, username, "found", "medium", "Page loaded. Open the link to confirm it is really them.")


async def _gravatar(client: httpx.AsyncClient, email: str) -> dict:
    digest = hashlib.md5(email.strip().lower().encode("utf-8")).hexdigest()
    url = f"https://www.gravatar.com/avatar/{digest}?d=404"
    state = "error"
    try:
        resp = await client.get(url)
        if resp.status_code == 200:
            state = "found"
        elif resp.status_code in (404, 410):
            state = "absent"
    except httpx.HTTPError:
        state = "error"
    return {
        "email": email,
        "gravatar": state,
        "gravatar_url": f"https://gravatar.com/{digest}",
    }


async def execute(job: Job) -> None:
    sites = load_sites()
    scanned = [s for s in sites if not s.get("manual")]
    manual = [s for s in sites if s.get("manual")]
    username = (job.profile.get("username") or "").strip()
    emails = job.profile.get("emails") or []

    job.total = (len(scanned) if username else 0) + len(emails)
    job.total = max(job.total, 1)

    if manual and username:
        job.manual = [
            {
                "name": site["name"],
                "url": _fill(site["url"], username),
                "why": site.get("why", ""),
            }
            for site in manual
        ]

    limits = httpx.Limits(max_connections=settings.per_site_concurrency + 10, max_keepalive_connections=10)
    timeout = httpx.Timeout(settings.site_timeout, connect=5.0)
    headers = {"User-Agent": settings.user_agent, "Accept": "application/json, text/html;q=0.9, */*;q=0.8"}

    async with httpx.AsyncClient(
        follow_redirects=True,
        timeout=timeout,
        limits=limits,
        headers=headers,
        http2=False,
    ) as client:
        if username:
            job.stage = "Checking public profiles"
            sem = asyncio.Semaphore(settings.per_site_concurrency)
            tasks = [asyncio.create_task(_probe(client, sem, site, username)) for site in scanned]
            for coro in asyncio.as_completed(tasks):
                result = await coro
                job.accounts.append(result)
                job.done += 1
        else:
            job.stage = "Checking email exposure"

        if emails:
            job.stage = "Checking email exposure"
            for email in emails:
                job.emails.append(await _gravatar(client, email))
                job.done += 1

    if username:
        found = [a for a in job.accounts if a["state"] == "found"]
        job.links = links_mod.build(job.profile, found)
    else:
        job.links = links_mod.build(job.profile, [])

    job.stage = "Writing your report"
    job.done = job.total
