"""Print raw probe states for one username. Useful for spotting false positives.

    .\\.venv\\Scripts\\python.exe scripts\\probe_debug.py zzqx8f3k9v0m2
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.jobs import Job
from app.scanner import engine


async def main() -> int:
    username = sys.argv[1] if len(sys.argv) > 1 else "zzqx8f3k9v0m2"
    job = Job(
        id="debug",
        created=0,
        profile={"username": username, "emails": [], "name": "", "city": ""},
        regions=["US"],
    )
    await engine.execute(job)
    order = {"found": 0, "ambiguous": 1, "blocked": 2, "timeout": 3, "error": 4, "absent": 5}
    for item in sorted(job.accounts, key=lambda a: (order.get(a["state"], 9), a["name"])):
        note = f"  ({item['note']})" if item["note"] else ""
        print(f"{item['state']:>10}  {item['confidence']:<6}  {item['name']}{note}")
    counts: dict[str, int] = {}
    for item in job.accounts:
        counts[item["state"]] = counts.get(item["state"], 0) + 1
    print("\n", counts)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
