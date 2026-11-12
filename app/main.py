from __future__ import annotations

import hashlib
import json
import re
import time
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import settings
from app.jobs import JobManager
from app.ratelimit import RateLimiter
from app.scanner import cleanup, links as links_mod, report

BASE = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE / "templates"))

manager = JobManager()
limiter = RateLimiter(window=settings.scan_cooldown_seconds, limit=1)

USERNAME_RE = re.compile(r"^[A-Za-z0-9_.\-]{1,64}$")
EMAIL_RE = re.compile(r"^[^@\s,;]{1,64}@[^@\s,;]{1,255}\.[A-Za-z]{2,24}$")


@asynccontextmanager
async def lifespan(_: FastAPI):
    manager.start()
    yield
    await manager.stop()


app = FastAPI(title="Glasshouse", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(BASE / "static")), name="static")


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def render(request: Request, name: str, status_code: int = 200, **context):
    context.setdefault("settings", settings)
    return templates.TemplateResponse(request, name, context, status_code=status_code)


def parse_emails(raw: str) -> tuple[list[str], list[str]]:
    chunks = [part.strip() for part in re.split(r"[\s,;]+", raw or "") if part.strip()]
    good, bad = [], []
    for chunk in chunks:
        if EMAIL_RE.match(chunk):
            if chunk.lower() not in [e.lower() for e in good]:
                good.append(chunk)
        else:
            bad.append(chunk)
    return good[:3], bad


def parse_date(value: str) -> str:
    try:
        return date.fromisoformat((value or "").strip()).isoformat()
    except (ValueError, AttributeError):
        return ""


def ics_escape(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
    )


@app.get("/", response_class=HTMLResponse)
async def index(request: Request, wiped: int = 0, error: str = ""):
    return render(
        request,
        "index.html",
        wiped=wiped,
        error=error,
        regions=cleanup.region_choices(),
        cooldown=settings.scan_cooldown_seconds,
    )


@app.post("/scan")
async def start_scan(
    request: Request,
    username: str = Form(""),
    emails: str = Form(""),
    name: str = Form(""),
    city: str = Form(""),
    regions: list[str] = Form(default=[]),
    consent: str = Form(""),
):
    if not consent:
        return RedirectResponse("/?error=consent", status_code=303)

    username = username.strip().lstrip("@")
    if username and not USERNAME_RE.match(username):
        return RedirectResponse("/?error=username", status_code=303)

    parsed_emails, bad_emails = parse_emails(emails)
    if bad_emails:
        return RedirectResponse("/?error=email", status_code=303)
    if not username and not parsed_emails:
        return RedirectResponse("/?error=empty", status_code=303)

    ip = client_ip(request)
    allowed, wait = limiter.allow(ip)
    if not allowed:
        return render(request, "index.html", status_code=429, wiped=0, error="rate",
                      regions=cleanup.region_choices(), cooldown=settings.scan_cooldown_seconds, wait=wait)

    if manager.running >= settings.max_concurrent_scans:
        return render(request, "index.html", status_code=503, wiped=0, error="busy",
                      regions=cleanup.region_choices(), cooldown=settings.scan_cooldown_seconds)

    chosen = [code for code in cleanup.REGION_ORDER if code in regions] or ["US"]
    profile = {
        "username": username,
        "emails": parsed_emails,
        "name": name.strip(),
        "city": city.strip(),
    }
    job = manager.create(profile, chosen)
    manager.launch(job)
    return RedirectResponse(f"/scan/{job.id}", status_code=303)


@app.get("/scan/{job_id}", response_class=HTMLResponse)
async def progress(request: Request, job_id: str):
    job = manager.get(job_id)
    if not job:
        return RedirectResponse("/?error=expired", status_code=303)
    return render(request, "scan.html", job=job)


@app.get("/scan/{job_id}/report", response_class=HTMLResponse)
async def report_page(request: Request, job_id: str):
    job = manager.get(job_id)
    if not job:
        return RedirectResponse("/?error=expired", status_code=303)
    if job.status == "running":
        return RedirectResponse(f"/scan/{job.id}", status_code=303)
    if job.status == "error":
        return render(request, "error.html", job=job, status_code=500)
    return render(
        request,
        "report.html",
        job=job,
        summary=report.build(job),
        regions=cleanup.region_choices(),
    )


@app.post("/scan/{job_id}/track")
async def track(job_id: str, item: str = Form(""), done: str = Form("")):
    job = manager.get(job_id)
    if not job:
        return RedirectResponse("/?error=expired", status_code=303)
    if item:
        if done:
            job.add_tracker(item)
        else:
            job.tracker.pop(item, None)
    return RedirectResponse(f"/scan/{job.id}/report#cleanup", status_code=303)


@app.post("/scan/{job_id}/regions")
async def set_regions(request: Request, job_id: str, regions: list[str] = Form(default=[])):
    job = manager.get(job_id)
    if not job:
        return RedirectResponse("/?error=expired", status_code=303)
    chosen = [code for code in cleanup.REGION_ORDER if code in regions]
    job.regions = chosen or job.regions
    return RedirectResponse(f"/scan/{job.id}/report#brokers", status_code=303)


@app.post("/scan/{job_id}/wipe")
async def wipe(job_id: str):
    manager.delete(job_id)
    return RedirectResponse("/?wiped=1", status_code=303)


@app.post("/scan/{job_id}/broker")
async def update_broker(
    request: Request,
    job_id: str,
    key: str = Form(""),
    state: str = Form("todo"),
    submitted: str = Form(""),
    notes: str = Form(""),
    recheck: int = Form(90),
):
    job = manager.get(job_id)
    if not job:
        return RedirectResponse("/?error=expired", status_code=303)
    if key.startswith("broker:"):
        if state not in cleanup.BROKER_STATES:
            state = "todo"
        if state == "todo":
            job.brokers.pop(key, None)
        else:
            sub = parse_date(submitted) or date.today().isoformat()
            days = max(0, min(int(recheck or 0), 730))
            follow = (date.fromisoformat(sub) + timedelta(days=days)).isoformat() if days else ""
            job.set_broker(key, state, sub, follow, notes)

    if request.headers.get("x-requested-with") == "fetch":
        return Response(status_code=204)
    return RedirectResponse(f"/scan/{job.id}/report?saved={quote(key)}#brokers", status_code=303)


@app.get("/scan/{job_id}/reminders.ics")
async def reminders(job_id: str):
    job = manager.get(job_id)
    if not job:
        return RedirectResponse("/?error=expired", status_code=303)
    summary = report.build(job)
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Glasshouse//Reminders//EN", "CALSCALE:GREGORIAN"]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    for item in summary["followups"]:
        try:
            start = date.fromisoformat(item["date"])
        except ValueError:
            continue
        end = start + timedelta(days=1)
        uid = hashlib.sha1(f"{item['key']}{item['date']}".encode("utf-8")).hexdigest()[:16]
        title = ics_escape(f"Re-check {item['label']} listing")
        desc = ics_escape(
            f"Check whether your information has been re-listed on {item['label']} ({item['region']}). {item['url']}"
        )
        lines += [
            "BEGIN:VEVENT",
            f"UID:{uid}@glasshouse",
            f"DTSTAMP:{stamp}",
            f"DTSTART;VALUE=DATE:{start.strftime('%Y%m%d')}",
            f"DTEND;VALUE=DATE:{end.strftime('%Y%m%d')}",
            f"SUMMARY:{title}",
            f"DESCRIPTION:{desc}",
            f"URL:{item['url']}",
            "END:VEVENT",
        ]
    lines.append("END:VCALENDAR")
    return Response(
        "\r\n".join(lines) + "\r\n",
        media_type="text/calendar",
        headers={"Content-Disposition": 'attachment; filename="glasshouse-reminders.ics"'},
    )


@app.post("/plan/import")
async def import_plan(file: UploadFile = File(...)):
    raw = await file.read()
    if len(raw) > 1_000_000:
        return RedirectResponse("/?error=import", status_code=303)
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return RedirectResponse("/?error=import", status_code=303)
    if not isinstance(data, dict) or data.get("kind") != "glasshouse-plan":
        return RedirectResponse("/?error=import", status_code=303)

    raw_profile = data.get("profile") if isinstance(data.get("profile"), dict) else {}
    profile = {
        "username": str(raw_profile.get("username") or "")[:64],
        "emails": [str(item)[:255] for item in (raw_profile.get("emails") or []) if isinstance(item, str)][:3],
        "name": str(raw_profile.get("name") or "")[:80],
        "city": str(raw_profile.get("city") or "")[:80],
    }
    regions = [code for code in cleanup.REGION_ORDER if code in (data.get("regions") or [])] or ["US"]

    job = manager.create(profile, regions)
    job.imported = True

    tracker = data.get("tracker")
    if isinstance(tracker, dict):
        job.tracker = {str(key)[:120]: "done" for key in tracker}

    brokers = data.get("brokers")
    if isinstance(brokers, dict):
        for key, value in list(brokers.items())[:200]:
            if isinstance(key, str) and key.startswith("broker:") and isinstance(value, dict):
                state = value.get("state")
                job.brokers[key] = {
                    "state": state if state in cleanup.BROKER_STATES else "todo",
                    "submitted": str(value.get("submitted") or "")[:10],
                    "follow_up": str(value.get("follow_up") or "")[:10],
                    "notes": str(value.get("notes") or "")[:200],
                }

    accounts = data.get("accounts")
    if isinstance(accounts, list):
        job.accounts = [item for item in accounts if isinstance(item, dict) and item.get("id")][:200]
    emails = data.get("emails")
    if isinstance(emails, list):
        job.emails = [item for item in emails if isinstance(item, dict)][:3]
    manual = data.get("manual")
    if isinstance(manual, list):
        job.manual = [item for item in manual if isinstance(item, dict)][:20]

    job.links = links_mod.build(profile, [item for item in job.accounts if item.get("state") == "found"])
    job.status = "done"
    job.stage = "restored"
    job.finished = time.time()
    return RedirectResponse(f"/scan/{job.id}/report", status_code=303)


@app.get("/healthz")
async def healthz():
    return {"status": "ok", "running": manager.running, "jobs": len(manager.jobs)}


@app.get("/privacy", response_class=HTMLResponse)
async def privacy(request: Request):
    return render(request, "privacy.html")
