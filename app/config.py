from __future__ import annotations

import os
from dataclasses import dataclass


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    # How long one IP has to wait between scans, in seconds.
    scan_cooldown_seconds: int = _int("GLASSHOUSE_COOLDOWN", 180)
    # How long a finished job stays in memory before it is wiped, in seconds.
    job_ttl_seconds: int = _int("GLASSHOUSE_TTL", 600)
    # Global ceiling on simultaneous scans across all visitors.
    max_concurrent_scans: int = _int("GLASSHOUSE_MAX_SCANS", 15)
    # How many sites one scan may probe.
    max_sites: int = _int("GLASSHOUSE_MAX_SITES", 160)
    # Parallel outbound requests per scan.
    per_site_concurrency: int = _int("GLASSHOUSE_CONCURRENCY", 20)
    # Per-site timeout in seconds.
    site_timeout: float = 8.0
    user_agent: str = os.getenv(
        "GLASSHOUSE_UA",
        "Glasshouse/1.0 (consent-based self-audit tool)",
    )


settings = Settings()
