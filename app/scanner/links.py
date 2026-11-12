"""Build pre-filled search links.

We never scrape search engines. Glasshouse hands the visitor a ready-made
query so they can run it themselves in the engine of their choice.

Rows come in two shapes:

  kind="query"   -- a text query with Google / Bing / DuckDuckGo links
  kind="direct"  -- one link to a site that is not a general search engine
                    (image search, archive, breach checker, code search)

Every row carries a ``group`` so the report can show headings instead of one
very long table.
"""

from __future__ import annotations

from urllib.parse import quote_plus

ENGINES = {
    "google": "https://www.google.com/search?q={q}",
    "bing": "https://www.bing.com/search?q={q}",
    "ddg": "https://duckduckgo.com/?q={q}",
}

# "First result" shortcuts. Both are ordinary links -- the browser asks the
# search engine to jump to the top hit, so nothing is read on the server.
FIRST_RESULT = {
    # Google's "I'm Feeling Lucky" button.
    "google": "https://www.google.com/search?q={q}&btnI=1",
    # DuckDuckGo's !ducky bang does the same thing.
    "ddg": "https://duckduckgo.com/?q=!ducky+{q}",
}

ARCHIVE_LIMIT = 4


def _query_row(group: str, label: str, note: str, query: str) -> dict:
    q = quote_plus(query)
    return {
        "group": group,
        "kind": "query",
        "label": label,
        "note": note,
        "query": query,
        "google": ENGINES["google"].format(q=q),
        "bing": ENGINES["bing"].format(q=q),
        "ddg": ENGINES["ddg"].format(q=q),
        "google_first": FIRST_RESULT["google"].format(q=q),
        "ddg_first": FIRST_RESULT["ddg"].format(q=q),
    }


def _direct_row(group: str, label: str, note: str, url: str) -> dict:
    return {
        "group": group,
        "kind": "direct",
        "label": label,
        "note": note,
        "query": url,
        "url": url,
    }


def build(profile: dict, found_sites: list[dict]) -> list[dict]:
    username = (profile.get("username") or "").strip()
    name = (profile.get("name") or "").strip()
    city = (profile.get("city") or "").strip()
    emails = [e for e in (profile.get("emails") or []) if e]

    rows: list[dict] = []

    # ---------------------------------------------------------------- username
    if username:
        rows.append(_query_row(
            "Username",
            "Your exact username",
            "Quoted, so search engines match the string rather than fragments.",
            f'"{username}"',
        ))
        rows.append(_query_row(
            "Username",
            "Common variations of your handle",
            "People often reuse the same handle with a number, underscore or dot added.",
            f'"{username}" OR "{username}1" OR "{username}_" OR "{username}."',
        ))
        rows.append(_query_row(
            "Username",
            "Username on profile and forum pages",
            "Catches older forums and directories that are not in the site list.",
            f'"{username}" (profile OR member OR user)',
        ))
        if emails:
            rows.append(_query_row(
                "Username",
                "Username next to your email",
                "Finds posts where the two appear together, e.g. old forums.",
                f'"{username}" "{emails[0]}"',
            ))
        rows.append(_query_row(
            "Username",
            "Username on social platforms",
            "A sweep of the platforms that block automated lookups.",
            f'"{username}" (site:x.com OR site:instagram.com OR site:tiktok.com OR site:facebook.com)',
        ))
        rows.append(_query_row(
            "Username",
            "Username on marketplaces",
            "Seller and buyer profiles often carry a photo, town or real name.",
            f'"{username}" (site:ebay.com OR site:etsy.com OR site:poshmark.com OR site:depop.com OR site:vinted.com)',
        ))
        rows.append(_query_row(
            "Username",
            "Username on forums and link sites",
            "Old posts are the most common source of forgotten personal details.",
            f'"{username}" (site:reddit.com OR site:news.ycombinator.com OR site:lobste.rs OR site:slashdot.org)',
        ))
        rows.append(_query_row(
            "Username",
            "Username on paste sites",
            "Paste dumps and notes sometimes survive long after an account is deleted.",
            f'"{username}" (site:pastebin.com OR site:rentry.co OR site:ghostbin.com)',
        ))
        rows.append(_query_row(
            "Username",
            "Username in documents",
            "PDFs, spreadsheets and word files are often indexed by accident.",
            f'"{username}" (filetype:pdf OR filetype:docx OR filetype:xlsx OR filetype:csv)',
        ))

    # ------------------------------------------------------------------ gaming
    if username:
        q = quote_plus(username)
        group = "Gaming platforms"
        rows.append(_query_row(
            group,
            "Username on gaming platforms",
            "A wide sweep of the platforms that keep public player pages.",
            f'"{username}" (site:steamcommunity.com OR site:roblox.com OR site:epicgames.com '
            f'OR site:battle.net OR site:faceit.com OR site:twitch.tv)',
        ))

        # Direct links to each platform's own player search, where it exists.
        rows.append(_direct_row(
            group,
            "Steam: player search",
            "Steam shows vanity names and old aliases. Already probed above; "
            "use this to find mentions and comments.",
            f"https://steamcommunity.com/search/users/?text={q}",
        ))
        rows.append(_direct_row(
            group,
            "Roblox: user search",
            "Roblox has its own user search. Already probed above for the exact name.",
            f"https://www.roblox.com/search/users?keyword={q}",
        ))
        rows.append(_direct_row(
            group,
            "Xbox: profile search",
            "Gamertags differ from your handle, so try common variations too.",
            f"https://www.xbox.com/en-US/search?q={q}",
        ))
        rows.append(_direct_row(
            group,
            "Minecraft: NameMC search",
            "NameMC also shows previous names and skins for a Minecraft account.",
            f"https://namemc.com/search?q={q}",
        ))
        rows.append(_direct_row(
            group,
            "Chess.com: search",
            "Already probed above. This finds clubs, games and forum posts too.",
            f"https://www.chess.com/search?q={q}",
        ))
        rows.append(_direct_row(
            group,
            "itch.io: search",
            "Already probed as a subdomain. This finds comments and collections.",
            f"https://itch.io/search?q={q}",
        ))
        rows.append(_direct_row(
            group,
            "BoardGameGeek: user search",
            "Profiles often list a real name and a town.",
            f"https://boardgamegeek.com/geeksearch.php?action=search&q={q}&objecttype=user",
        ))

        # Platforms with no stable public search page get a site: query.
        rows.append(_query_row(
            group,
            "PC launchers and stores",
            "Epic, GOG, Battle.net, EA and Ubisoft pages are indexed by search engines.",
            f'"{username}" (site:epicgames.com OR site:gog.com OR site:battle.net '
            f'OR site:ea.com OR site:ubisoft.com)',
        ))
        rows.append(_query_row(
            group,
            "Console profiles",
            "PlayStation, Nintendo and Xbox pages, including trophy and achievement sites.",
            f'"{username}" (site:playstation.com OR site:nintendo.com OR site:xbox.com '
            f'OR site:psnprofiles.com OR site:trueachievements.com)',
        ))
        rows.append(_query_row(
            group,
            "Competitive and esports",
            "FACEIT, Riot, and the big stat trackers for CS, Valorant, Apex and Overwatch.",
            f'"{username}" (site:faceit.com OR site:riotgames.com OR site:op.gg '
            f'OR site:tracker.gg OR site:overbuff.com OR site:r6.tracker.network)',
        ))
        rows.append(_query_row(
            group,
            "Speedruns and retro achievements",
            "Leaderboards are public and often keep a country or region.",
            f'"{username}" (site:speedrun.com OR site:retroachievements.org)',
        ))
        rows.append(_query_row(
            group,
            "Mods, indie games and game jams",
            "Comment sections and project credits are easy to forget.",
            f'"{username}" (site:moddb.com OR site:nexusmods.com OR site:gamejolt.com '
            f'OR site:itch.io)',
        ))
        rows.append(_query_row(
            group,
            "Gaming forums and communities",
            "Old posts often carry your real name, town or email in a quote.",
            f'"{username}" (site:reddit.com/r/gaming OR site:neogaf.com '
            f'OR site:resetera.com OR site:gamespot.com OR site:ign.com)',
        ))
        rows.append(_query_row(
            group,
            "Game trackers and backlogs",
            "Backlog and stats sites record what you played and when.",
            f'"{username}" (site:backloggd.com OR site:howlongtobeat.com '
            f'OR site:steamdb.info OR site:steamcharts.com)',
        ))
        rows.append(_query_row(
            group,
            "Streaming and Discord",
            "Twitch pages are public; Discord profiles are numeric IDs, so this only "
            "finds servers and posts that mention the name.",
            f'"{username}" (site:twitch.tv OR site:discord.com OR site:youtube.com)',
        ))

    # ------------------------------------------------------------ code & pastes
    if username:
        q = quote_plus(username)
        rows.append(_direct_row(
            "Code & pastes",
            "grep.app: code search",
            "Searches public repositories for the handle, including old commits.",
            f"https://grep.app/search?q={q}",
        ))
        rows.append(_direct_row(
            "Code & pastes",
            "searchcode: code search",
            "A second index of public source code.",
            f"https://searchcode.com/?q={q}",
        ))
        rows.append(_direct_row(
            "Code & pastes",
            "Sourcegraph: code search",
            "Finds mentions in public code and configuration files.",
            f"https://sourcegraph.com/search?q=context:global+{q}&patternType=standard",
        ))
        rows.append(_direct_row(
            "Code & pastes",
            "Pastebin: search pastes",
            "Pastebin's own search. Treat anything you find as untrusted.",
            f"https://pastebin.com/search?q={q}",
        ))

    # ------------------------------------------------------------------- name
    if name:
        rows.append(_query_row(
            "Your name",
            "Your exact name",
            "Start broad, then narrow by town or employer.",
            f'"{name}"',
        ))
        if city:
            rows.append(_query_row(
                "Your name",
                "Your name and town",
                "The combination is what makes a name match actually about you.",
                f'"{name}" "{city}"',
            ))
        rows.append(_query_row(
            "Your name",
            "Your name plus contact details",
            "Catches directory pages and old sign-up lists.",
            f'"{name}" (email OR phone OR address)',
        ))
        rows.append(_query_row(
            "Your name",
            "Your name in documents",
            "Published PDFs, council papers and conference programmes.",
            f'"{name}" (filetype:pdf OR filetype:docx)',
        ))
        rows.append(_query_row(
            "Your name",
            "Your name plus resume or CV",
            "Old CVs carry phone numbers, addresses and employer history.",
            f'"{name}" (resume OR CV OR curriculum vitae)',
        ))
        rows.append(_query_row(
            "Your name",
            "Your name on data-broker sites",
            "Useful before working through the guided removal queue below.",
            f'"{name}" (site:spokeo.com OR site:whitepages.com OR site:intelius.com OR site:beenverified.com OR site:peoplefinder.com)',
        ))

    # ------------------------------------------------------- name by platform
    if name:
        group = "Find your profile by name"
        where = f' "{city}"' if city else ""
        rows.append(_query_row(
            group,
            "All the big social platforms",
            "The same name search across Facebook, Instagram, LinkedIn, X, TikTok and Threads.",
            f'"{name}"{where} (site:facebook.com OR site:instagram.com OR site:linkedin.com '
            f'OR site:x.com OR site:tiktok.com OR site:threads.net)',
        ))

        platforms = [
            (
                "Facebook",
                "facebook.com",
                "Facebook shows a login wall to scripts. Use First result, then open the About tab.",
            ),
            (
                "Instagram",
                "instagram.com",
                "Public profiles stay in the search index even when the site asks you to log in.",
            ),
            (
                "LinkedIn",
                "linkedin.com",
                "Public profiles are indexed. Add your employer if the name is common.",
            ),
            (
                "X (Twitter)",
                "x.com",
                "X renders profiles with JavaScript. The index keeps older public posts.",
            ),
            (
                "TikTok",
                "tiktok.com",
                "Profile pages are indexed with both the handle and the display name.",
            ),
            (
                "Threads",
                "threads.net",
                "Try the name with and without the @, and with your town if it is common.",
            ),
        ]
        for label, host, note in platforms:
            rows.append(_query_row(
                group,
                f"Your name on {label}",
                f"{note} First result jumps straight to the top hit.",
                f'"{name}"{where} site:{host}',
            ))

    # ------------------------------------------------------------------ email
    for email in emails:
        rows.append(_query_row(
            "Email",
            f"Search for {email}",
            "Exact-string search. Paste the email if prompted by a paywall.",
            f'"{email}"',
        ))
        rows.append(_query_row(
            "Email",
            f"{email} in text and data files",
            "Leaked lists and scraped directories are often plain text or CSV.",
            f'"{email}" (filetype:txt OR filetype:csv OR filetype:json)',
        ))
        rows.append(_query_row(
            "Email",
            f"{email} on paste sites",
            "Paste dumps are a common place for email lists to surface.",
            f'"{email}" (site:pastebin.com OR site:rentry.co OR site:ghostbin.com)',
        ))

    # ----------------------------------------------------------------- images
    who = username or name
    if who:
        q = quote_plus(who)
        rows.append(_direct_row(
            "Images",
            "Google Images",
            "Look for your photo or handle on pages you do not recognise.",
            f"https://www.google.com/search?tbm=isch&q={q}",
        ))
        rows.append(_direct_row(
            "Images",
            "Bing Images",
            "A different index, so it often finds different copies.",
            f"https://www.bing.com/images/search?q={q}",
        ))
        rows.append(_direct_row(
            "Images",
            "Yandex Images",
            "Strong at matching faces and reposted photos.",
            f"https://yandex.com/images/search?text={q}",
        ))
        rows.append(_direct_row(
            "Images",
            "Have I Been Trained?",
            "Checks whether your images appear in AI training datasets.",
            f"https://haveibeentrained.com/?search={q}",
        ))
        rows.append(_direct_row(
            "Images",
            "TinEye",
            "Upload a photo to find exact copies elsewhere.",
            "https://tineye.com/",
        ))

    # --------------------------------------------------------------- archives
    for site in found_sites[:ARCHIVE_LIMIT]:
        url = site.get("url")
        if not url:
            continue
        rows.append(_direct_row(
            "Archives",
            f"Wayback Machine: {site['name']}",
            "Archived copies can survive after you delete the account.",
            f"https://web.archive.org/web/*/{url}",
        ))
        rows.append(_direct_row(
            "Archives",
            f"archive.today: {site['name']}",
            "A second archive. If a copy exists, you can ask them to remove it.",
            f"https://archive.ph/newest/{url}",
        ))

    # ---------------------------------------------------------------- breaches
    rows.append(_direct_row(
        "Breach checks",
        "HaveIBeenPwned",
        "The standard free breach checker. Paste each email address.",
        "https://haveibeenpwned.com/",
    ))
    rows.append(_direct_row(
        "Breach checks",
        "Firefox Monitor",
        "Mozilla's breach checker, powered by HaveIBeenPwned.",
        "https://monitor.mozilla.org/",
    ))
    rows.append(_direct_row(
        "Breach checks",
        "LeakCheck",
        "A second breach index. Free searches show which breaches, not full records.",
        "https://leakcheck.io/",
    ))

    # De-duplicate by (group, query), keep order.
    seen: set[tuple[str, str]] = set()
    unique = []
    for row in rows:
        key = (row["group"], row["query"])
        if key in seen:
            continue
        seen.add(key)
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
