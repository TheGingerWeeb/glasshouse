"""Build pre-filled search links.

We never scrape search engines. Glasshouse hands the visitor a ready-made
query so they can run it themselves in the engine of their choice.
"""

from __future__ import annotations

from urllib.parse import quote_plus

ENGINES = {
    "google": "https://www.google.com/search?q={q}",
    "bing": "https://www.bing.com/search?q={q}",
    "ddg": "https://duckduckgo.com/?q={q}",
}


def _row(label: str, note: str, query: str) -> dict:
    q = quote_plus(query)
    return {
        "label": label,
        "note": note,
        "query": query,
        "google": ENGINES["google"].format(q=q),
        "bing": ENGINES["bing"].format(q=q),
        "ddg": ENGINES["ddg"].format(q=q),
    }


def build(profile: dict, found_sites: list[dict]) -> list[dict]:
    username = (profile.get("username") or "").strip()
    name = (profile.get("name") or "").strip()
    city = (profile.get("city") or "").strip()
    emails = profile.get("emails") or []

    rows: list[dict] = []

    if username:
        rows.append(_row(
            "Your exact username",
            "Quoted, so search engines match the string rather than fragments.",
            f'"{username}"',
        ))
        if emails:
            rows.append(_row(
                "Username next to your email",
                "Finds posts where the two appear together, e.g. old forums.",
                f'"{username}" "{emails[0]}"',
            ))
        for site in found_sites[:3]:
            host = site.get("host")
            if host:
                rows.append(_row(
                    f"Your username on {host}",
                    "Sometimes profiles are mirrored or scraped elsewhere.",
                    f'"{username}" site:{host}',
                ))
                break

    if name:
        if city:
            rows.append(_row(
                "Your name and town",
                "The combination is what makes a name match actually about you.",
                f'"{name}" "{city}"',
            ))
        rows.append(_row(
            "Your name plus contact details",
            "Catches directory pages and old sign-up lists.",
            f'"{name}" (email OR phone OR address)',
        ))
        rows.append(_row(
            "Your name on social platforms",
            "A quick sweep of the usual suspects.",
            f'"{name}" (site:facebook.com OR site:instagram.com OR site:linkedin.com)',
        ))

    for email in emails:
        rows.append(_row(
            f"Search for {email}",
            "Exact-string search. Paste the email if prompted by a paywall.",
            f'"{email}"',
        ))

    # De-duplicate by query, keep order.
    seen: set[str] = set()
    unique = []
    for row in rows:
        if row["query"] in seen:
            continue
        seen.add(row["query"])
        unique.append(row)
    return unique


BREACH_HELP = {
    "label": "Check your email against known breaches",
    "url": "https://haveibeenpwned.com/",
    "note": (
        "HaveIBeenPwned's website search is free. The tool can't query it for you "
        "because their API needs a paid key, so open the site and paste your email."
    ),
}

REMOVAL_HELP = [
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
        "label": "Wayback Machine: exclude your site",
        "url": "https://help.archive.org/help/how-do-i-request-to-remove-something-from-archive-org/",
        "note": "Archived copies survive account deletion. This is how you ask for removal.",
    },
]
