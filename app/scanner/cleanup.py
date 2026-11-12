from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus, urlparse

DATA = Path(__file__).resolve().parent.parent / "data"

REGION_ORDER = ["US", "UK", "EU", "CA", "AU"]

BROKER_STATES = {
    "todo": "To do",
    "submitted": "Submitted",
    "waiting": "Waiting on them",
    "removed": "Removed",
    "refused": "Refused / gave up",
}
HANDLED_STATES = {"submitted", "waiting", "removed", "refused"}


def fallback_url(optout_url: str) -> str:
    """Site-scoped search, used when a deep link moves or looks wrong."""
    host = urlparse(optout_url).netloc
    return "https://duckduckgo.com/?q=" + quote_plus(f"site:{host} remove my personal information")


def load_regions() -> dict[str, Any]:
    payload = json.loads((DATA / "brokers.json").read_text(encoding="utf-8"))
    return payload.get("regions", {})


def region_choices() -> list[tuple[str, str]]:
    regions = load_regions()
    return [(code, regions[code]["label"]) for code in REGION_ORDER if code in regions]


GENERAL_TASKS = [
    {
        "id": "alias-email",
        "label": "Stop using one email everywhere",
        "why": "Your email is the reset key for every account. Aliases mean one leak can't unlock the rest.",
        "link": "https://simplelogin.io/",
        "link_label": "Email aliasing (SimpleLogin)",
    },
    {
        "id": "unique-handles",
        "label": "Use different usernames per context",
        "why": "One handle links your gaming, work and anonymous lives together in a single search.",
        "link": "",
        "link_label": "",
    },
    {
        "id": "passkeys",
        "label": "Turn on passkeys or app-based 2FA",
        "why": "This is the single biggest defence against someone getting in with a leaked password.",
        "link": "https://passkeys.dev/",
        "link_label": "What passkeys are",
    },
    {
        "id": "lock-profiles",
        "label": "Check what a logged-out stranger can see",
        "why": "Open each profile in a private window. If you can see it, so can anyone else.",
        "link": "",
        "link_label": "",
    },
    {
        "id": "remove-old",
        "label": "Delete accounts you no longer use",
        "why": "Old forums and dead apps are the most common source of leaked passwords.",
        "link": "https://justdelete.me/",
        "link_label": "Deletion links per service",
    },
    {
        "id": "strip-metadata",
        "label": "Strip photo metadata before posting",
        "why": "Phone photos can carry GPS coordinates and timestamps.",
        "link": "https://exiftool.org/",
        "link_label": "ExifTool",
    },
    {
        "id": "breach-alerts",
        "label": "Get breach alerts for your email",
        "why": "You can't fix a leak you don't know about.",
        "link": "https://haveibeenpwned.com/",
        "link_label": "HaveIBeenPwned",
    },
]

EARLIER_STEPS = [
    {
        "label": "Google: Results about you",
        "url": "https://myactivity.google.com/results-about-you",
        "note": "Ask Google to remove pages that expose your phone, email or address.",
    },
    {
        "label": "Bing: request removal",
        "url": "https://www.bing.com/webmasters/tools/contentremoval",
        "note": "Same idea, for Bing's index.",
    },
    {
        "label": "Wayback Machine removal request",
        "url": "https://help.archive.org/help/how-do-i-request-to-remove-something-from-archive-org/",
        "note": "Archived copies survive account deletion. This is how you ask.",
    },
]


def removal_email(region: str, broker: str, profile: dict[str, Any]) -> dict[str, str]:
    regions = load_regions()
    law = regions.get(region, {}).get("law", "applicable data protection law")
    name = profile.get("name") or "[your full name]"
    emails = profile.get("emails") or []
    email = emails[0] if emails else "[your email]"

    subject = f"Data erasure request — {name}"
    body = (
        f"To {broker} Privacy Team,\n\n"
        f"I am writing to request the erasure of personal data relating to me that you process "
        f"and publish, under {law}.\n\n"
        f"Name: {name}\n"
        f"Email: {email}\n\n"
        "Please:\n"
        "1. Remove my personal information from your website and search results.\n"
        "2. Confirm in writing which records were deleted and which (if any) you retain, and why.\n"
        "3. Confirm that you have passed the request to any third parties you shared the data with.\n\n"
        f"If you need to verify my identity, tell me what you need and I will provide it. "
        f"Please respond within the timeframe set by {law}.\n\n"
        "Regards,\n"
        f"{name}\n"
    )
    return {"subject": subject, "body": body}
