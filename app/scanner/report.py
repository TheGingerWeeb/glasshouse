from __future__ import annotations

from datetime import date, datetime, timezone

from app.jobs import Job
from app.scanner import cleanup

CATEGORY_LABELS = {
    "dev": "Developer & tech",
    "social": "Social & community",
    "creative": "Creative",
    "gaming": "Gaming",
    "professional": "Professional & publishing",
    "marketplace": "Marketplaces",
    "forums": "Forums & link sites",
    "regional": "Regional communities",
    "other": "Other",
}
CATEGORY_ORDER = [
    "dev",
    "social",
    "creative",
    "gaming",
    "professional",
    "marketplace",
    "forums",
    "regional",
    "other",
]


def _card(title: str, tone: str, label: str, why: str, fix: str) -> dict:
    return {"title": title, "tone": tone, "label": label, "why": why, "fix": fix}


def build(job: Job) -> dict:
    found = [a for a in job.accounts if a["state"] == "found"]
    ambiguous = [a for a in job.accounts if a["state"] == "ambiguous"]
    blocked = [a for a in job.accounts if a["state"] in {"blocked", "timeout", "error"}]
    checked = [a for a in job.accounts if a["state"] in {"found", "absent"}]

    groups = []
    for category in CATEGORY_ORDER:
        items = sorted(
            [a for a in found if a.get("category") == category],
            key=lambda item: item["name"].lower(),
        )
        if items:
            groups.append({"key": category, "label": CATEGORY_LABELS.get(category, category), "entries": items})

    general = [
        {
            "key": f"task:{task['id']}",
            "label": task["label"],
            "note": task["why"],
            "link": task["link"],
            "link_label": task["link_label"],
            "done": f"task:{task['id']}" in job.tracker,
        }
        for task in cleanup.GENERAL_TASKS
    ]

    regions = cleanup.load_regions()
    broker_groups = []
    broker_total = 0
    broker_done = 0
    followups = []
    today = date.today().isoformat()

    for code in job.regions:
        data = regions.get(code)
        if not data:
            continue
        entries = []
        for broker in data["brokers"]:
            key = f"broker:{code}:{broker['id']}"
            saved = job.brokers.get(key, {})
            state = saved.get("state", "todo")
            if state not in cleanup.BROKER_STATES:
                state = "todo"
            handled = state in cleanup.HANDLED_STATES
            if broker.get("recheck_days"):
                broker_total += 1
                if handled:
                    broker_done += 1

            entry = {
                "key": key,
                "label": broker["name"],
                "url": broker["optout_url"],
                "fallback": cleanup.fallback_url(broker["optout_url"]),
                "steps": broker.get("steps", []),
                "requires": broker.get("requires", []),
                "minutes": broker.get("minutes", 5),
                "note": broker.get("notes", ""),
                "status": broker.get("status") or "unverified",
                "verified": broker.get("verified"),
                "recheck_days": broker.get("recheck_days", 90),
                "state": state,
                "state_label": cleanup.BROKER_STATES[state],
                "submitted": saved.get("submitted", ""),
                "follow_up": saved.get("follow_up", ""),
                "notes": saved.get("notes", ""),
                "handled": handled,
            }
            entries.append(entry)

            if entry["follow_up"] and state in {"submitted", "waiting"}:
                followups.append(
                    {
                        "label": broker["name"],
                        "region": data["label"],
                        "date": entry["follow_up"],
                        "due": entry["follow_up"] <= today,
                        "url": broker["optout_url"],
                        "key": key,
                    }
                )

        broker_groups.append(
            {
                "code": code,
                "label": data["label"],
                "law": data["law"],
                "entries": entries,
                "letter": cleanup.removal_email(code, "[broker name]", job.profile),
            }
        )

    followups.sort(key=lambda item: item["date"])

    link_groups = []
    link_index: dict[str, dict] = {}
    for row in job.links:
        key = row.get("group", "Search")
        group = link_index.get(key)
        if group is None:
            group = {"key": key, "label": key, "rows": []}
            link_index[key] = group
            link_groups.append(group)
        group["rows"].append(row)

    account_items = [
        {
            "key": f"account:{item['id']}",
            "label": f"Delete or secure {item['name']}",
            "note": item["url"],
            "link": item["url"],
            "link_label": "Open profile",
            "done": f"account:{item['id']}" in job.tracker,
        }
        for item in sorted(found, key=lambda item: item["name"].lower())
    ]

    total_items = len(account_items) + len(general) + broker_total
    done_items = (
        sum(1 for item in account_items if item["done"])
        + sum(1 for item in general if item["done"])
        + broker_done
    )

    cards = []
    count = len(found)

    if job.profile.get("username"):
        if count >= 6:
            cards.append(_card(
                "Your username is a skeleton key",
                "bad",
                f"Reused on {count} sites",
                "One search links every one of these profiles together, and a stranger can build a timeline from them.",
                "Pick a different handle for gaming, work and anything you'd rather not connect.",
            ))
        elif count >= 3:
            cards.append(_card(
                "Your username is easy to follow",
                "warn",
                f"Found on {count} sites",
                "That's enough for someone to connect the accounts and watch for new ones.",
                "Change the handle on the accounts you don't need, and lock the rest down.",
            ))
        else:
            cards.append(_card(
                "Your username is low-profile",
                "good",
                f"Found on {count} of {len(checked)} checked sites",
                "Very few public profiles are tied to this handle.",
                "Keep it that way — don't reuse this handle on new accounts.",
            ))

        cards.append(_card(
            "Accounts you may have forgotten",
            "bad" if count >= 5 else ("warn" if count >= 2 else "good"),
            f"{count} public profile{'s' if count != 1 else ''} found",
            "Every public profile is a place where your name, photo and interests leak out.",
            "Work through the cleanup list below: keep what you use, delete what you don't.",
        ))
    else:
        cards.append(_card(
            "No username supplied",
            "muted",
            "Username checks skipped",
            "The most useful half of this audit is the username sweep, and it needs a handle to look for.",
            "Run it again with your main username — it takes one field.",
        ))

    cards.append(_card(
        "Breach exposure",
        "muted",
        "One manual check",
        "Breach databases aren't something a free tool can query for you, and reusing passwords is how leaks turn into break-ins.",
        "Open HaveIBeenPwned, paste your email, then change any reused password.",
    ))

    cards.append(_card(
        "Mentions of your name",
        "muted",
        "Search links ready",
        "Search engines only find what's indexed, so this is a starting point, not a total.",
        "Run the prepared searches and request removal for anything you didn't choose to publish.",
    ))

    cards.append(_card(
        "Photos, location and old posts",
        "muted",
        "Check by hand",
        "This tool can't read your photo library, and GPS data in images is the classic giveaway.",
        "Strip metadata before posting, and stop checking in at home or work.",
    ))

    coverage = {
        "checked": len(checked),
        "found": count,
        "ambiguous": len(ambiguous),
        "blocked": len(blocked),
        "scanned": len(job.accounts),
    }

    export = {
        "version": 2,
        "kind": "glasshouse-plan",
        "saved": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "profile": job.profile,
        "regions": job.regions,
        "tracker": job.tracker,
        "brokers": job.brokers,
        "accounts": job.accounts,
        "emails": job.emails,
        "manual": job.manual,
    }

    return {
        "cards": cards,
        "groups": groups,
        "account_items": account_items,
        "general": general,
        "broker_groups": broker_groups,
        "broker_total": broker_total,
        "broker_done": broker_done,
        "followups": followups,
        "manual": job.manual,
        "links": job.links,
        "link_groups": link_groups,
        "emails": job.emails,
        "ambiguous": ambiguous,
        "blocked": blocked,
        "coverage": coverage,
        "total_items": total_items,
        "done_items": done_items,
        "region_labels": cleanup.region_choices(),
        "earlier_steps": cleanup.EARLIER_STEPS,
        "states": cleanup.BROKER_STATES,
        "export": export,
        "imported": job.imported,
    }
