"""End-to-end HTTP check against a locally running Glasshouse.

    .\\.venv\\Scripts\\python.exe -m uvicorn app.main:app --port 8000
    .\\.venv\\Scripts\\python.exe scripts\\e2e.py torvalds
"""

from __future__ import annotations

import json
import re
import sys
import time

import httpx

BASE = "http://127.0.0.1:8000"


def main() -> int:
    username = sys.argv[1] if len(sys.argv) > 1 else "torvalds"

    with httpx.Client(base_url=BASE, follow_redirects=False, timeout=30) as client:
        home = client.get("/")
        assert home.status_code == 200, home.status_code
        assert "Load my saved plan" in home.text
        print("home ok")

        started = client.post(
            "/scan",
            data={
                "username": username,
                "emails": "someone@example.com",
                "name": "Test Person",
                "city": "Testville",
                "regions": ["US", "UK"],
                "consent": "yes",
            },
        )
        assert started.status_code == 303, started.text[:400]
        location = started.headers["location"]
        print("job started:", location)

        deadline = time.time() + 150
        while time.time() < deadline:
            page = client.get(location)
            if page.status_code == 200 and "progress-wrap" in page.text:
                time.sleep(2)
                continue
            break

        report_url = location.rstrip("/") + "/report"
        report = client.get(report_url)
        assert report.status_code == 200, report.status_code
        html = report.text
        assert "Your footprint report" in html
        assert "Open the exact opt-out page" in html
        assert "Copy name" in html
        assert "Data brokers" in html
        assert "Search for mentions of you" in html
        print(f"report ok ({len(html)} bytes)")

        # Broker status update (same path the JS uses).
        broker = client.post(
            f"{location}/broker",
            data={"key": "broker:US:spokeo", "state": "submitted", "recheck": "90", "notes": "ticket 1"},
            headers={"X-Requested-With": "fetch"},
        )
        assert broker.status_code == 204, broker.status_code
        after = client.get(report_url).text
        assert "Marked" in after and "Submitted" in after
        assert "follow up on" in after or "Follow-ups" in after
        print("broker status ok")

        calendars = client.get(f"{location}/reminders.ics")
        assert calendars.status_code == 200
        assert "BEGIN:VCALENDAR" in calendars.text
        assert "BEGIN:VEVENT" in calendars.text
        assert "Re-check Spokeo" in calendars.text
        print("calendar ok")

        # Export the plan payload out of the updated page, then re-import it.
        match = re.search(r'<script type="application/json" id="plan-data">(.*?)</script>', after, re.S)
        assert match, "plan payload missing"
        plan = json.loads(match.group(1))
        assert plan["kind"] == "glasshouse-plan"
        imported = client.post(
            "/plan/import",
            files={"file": ("plan.json", json.dumps(plan).encode(), "application/json")},
        )
        assert imported.status_code == 303, imported.text[:300]
        restored_url = imported.headers["location"]
        restored = client.get(restored_url)
        assert restored.status_code == 200
        assert "restored plan" in restored.text
        assert "Open the exact opt-out page" in restored.text
        assert "ticket 1" in restored.text
        print("export/import ok")

        toggled = client.post(f"{location}/track", data={"item": "task:passkeys", "done": "1"})
        assert toggled.status_code == 303
        switched = client.post(f"{location}/regions", data={"regions": ["CA", "AU"]})
        assert switched.status_code == 303
        switched_page = client.get(report_url)
        assert "Canada" in switched_page.text and "Australia" in switched_page.text
        print("tracker and region switch ok")

        wiped = client.post(f"{location}/wipe")
        assert wiped.status_code == 303
        gone = client.get(report_url)
        assert gone.status_code == 303
        print("wipe ok")

    print("E2E OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
