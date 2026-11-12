from __future__ import annotations

import asyncio
import secrets
import time
from dataclasses import dataclass, field
from typing import Any

from app.config import settings


@dataclass
class Job:
    id: str
    created: float
    profile: dict[str, Any]
    regions: list[str]
    status: str = "running"  # running | done | error
    stage: str = "queued"
    done: int = 0
    total: int = 0
    accounts: list[dict] = field(default_factory=list)
    emails: list[dict] = field(default_factory=list)
    links: list[dict] = field(default_factory=list)
    manual: list[dict] = field(default_factory=list)
    tracker: dict[str, str] = field(default_factory=dict)
    brokers: dict[str, dict] = field(default_factory=dict)
    imported: bool = False
    error: str | None = None
    finished: float | None = None

    def add_tracker(self, key: str) -> None:
        self.tracker[key] = "done"

    def toggle_tracker(self, key: str) -> None:
        if key in self.tracker:
            self.tracker.pop(key, None)
        else:
            self.tracker[key] = "done"

    def set_broker(self, key: str, state: str, submitted: str, follow_up: str, notes: str) -> None:
        self.brokers[key] = {
            "state": state,
            "submitted": submitted,
            "follow_up": follow_up,
            "notes": notes[:200],
        }


class JobManager:
    def __init__(self) -> None:
        self.jobs: dict[str, Job] = {}
        self.running = 0
        self._tasks: set[asyncio.Task] = set()
        self._reaper: asyncio.Task | None = None

    def create(self, profile: dict[str, Any], regions: list[str]) -> Job:
        job = Job(
            id=secrets.token_urlsafe(12),
            created=time.time(),
            profile=profile,
            regions=regions,
        )
        self.jobs[job.id] = job
        return job

    def get(self, job_id: str) -> Job | None:
        return self.jobs.get(job_id)

    def delete(self, job_id: str) -> None:
        self.jobs.pop(job_id, None)

    def launch(self, job: Job) -> None:
        task = asyncio.create_task(self._run(job))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _run(self, job: Job) -> None:
        from app.scanner import engine

        self.running += 1
        try:
            await engine.execute(job)
            job.status = "done"
            job.stage = "complete"
        except Exception as exc:  # keep the UI honest instead of a 500
            job.status = "error"
            job.error = f"{type(exc).__name__}: {exc}"
        finally:
            job.finished = time.time()
            self.running -= 1

    def start(self) -> None:
        self._reaper = asyncio.create_task(self._reap())

    async def stop(self) -> None:
        if self._reaper:
            self._reaper.cancel()
        for task in list(self._tasks):
            task.cancel()

    async def _reap(self) -> None:
        while True:
            await asyncio.sleep(20)
            now = time.time()
            for job_id, job in list(self.jobs.items()):
                finished = job.finished or job.created
                if now - finished > settings.job_ttl_seconds:
                    self.jobs.pop(job_id, None)
