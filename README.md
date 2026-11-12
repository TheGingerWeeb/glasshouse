# 🪟 Glasshouse

**See what a stranger can find about you — then shrink it.**

Glasshouse is a consent-based OSINT self-audit tool. Someone types in *their own* username and
email, and gets back:

- the public profiles tied to that username,
- a plain-language risk report,
- a cleanup checklist with per-site deletion links,
- a **guided, one-broker-at-a-time removal queue** for the US, UK, EU, Canada and Australia, with the
  exact opt-out page, the clicks that follow, copy buttons for your details, a status tracker and
  calendar reminders,
- statutorily-worded removal emails per region,
- ready-made searches for mentions of their name, username and email, plus image, archive, code and
  breach-check links.

It is built for teaching opsec: run it, fix what it finds, run it again.

---

## What gets checked

- **~110 automated profile probes** across developer sites, social platforms, creative portfolios,
  gaming, professional profiles, marketplaces, forums and a few regional communities.
- **~40 manual self-check links** for sites that block automation or need an ID you would have to
  paste — X, Instagram, TikTok, Facebook, LinkedIn, Threads, marketplaces, fitness apps, payment
  handles and more.
- **~40 prepared searches**, grouped into username, name, email, code/pastes, images, archives and
  breach checks. You run them yourself; nothing is scraped.
- **Gravatar** lookup for each email address.

Some sites answer every request with a bot challenge. Those are reported as **blocked**, never as
"no account".

---

## What it deliberately does not do

- No breach-database API calls (that requires a paid key). It links you to HaveIBeenPwned instead.
- No search-engine scraping. It builds queries and hands you the links.
- No password-reset probing, login bypassing, or captcha avoidance.
- No automatic account deletion. Every deletion has to be done by the owner, logged in.
- No storage. Jobs live in memory and are wiped on request or after 10 minutes.

Sites that block automation are offered as self-check links rather than fake "not found" results.

---

## Run it locally

```powershell
cd glasshouse
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open <http://127.0.0.1:8000>.

That is the whole setup. **Docker is not required** — not for running it, and not for deploying it.
The `Dockerfile` is only there for people who already have Docker and prefer it.

---

## The broker removal queue

The report shows one broker card at a time. Each card has:

- the **exact opt-out deep link** (not a homepage guess) and a one-line description of what the
  broker holds,
- the **three or four clicks** that follow, in order,
- badges for what the form asks of you (CAPTCHA, phone call, account, ID), and minutes it takes,
- **copy buttons** for your name, email and address, so you never retype them into a form,
- **Mark submitted / Already removed / Couldn't do it** buttons. Marking one done reveals the next.
- a **follow-up date** calculated from the recheck interval, plus an **.ics** download for your calendar.

A “Show every broker” toggle turns the queue into a normal checklist. Region checkboxes switch
between US, UK, EU, Canada and Australia; completed items survive the switch.

Your name, address, phone and date of birth are stored **only in your browser** (`localStorage`,
key `glasshouse.details.v1`) and are never posted to the server. The copy buttons read from that
local box.

Because jobs expire after 10 minutes, **Download my plan (.json)** saves your ticks, notes and
follow-up dates. **Load my saved plan** on the home page restores them without re-scanning.

### Link verification

Broker URLs rot. `scripts/verify_links.py` checks each one and records a status in
`app/data/brokers.json`:

| Status | Meaning |
|---|---|
| `ok` | Page answered and mentions removal/privacy wording; `verified` holds the date |
| `unverified` | Page answered but looks like a homepage or generic shell |
| `blocked` | Site rejects automated clients (Cloudflare); a normal browser usually works |
| `broken` | 404/410 or server error — the UI offers a site-scoped search fallback |
| `error` | Connection failed |

```powershell
.\.venv\Scripts\python.exe scripts\verify_links.py          # report only
.\.venv\Scripts\python.exe scripts\verify_links.py --write  # update statuses + dates
```

Re-run it every few months.

---

## Deploy for free (Render, no Docker, no card)

Hugging Face used to be the easy free option, but in July 2026 it moved free Docker Spaces behind a
paid PRO plan. **Render's free web-service tier needs no Docker, no credit card and no licence** —
just a free account and a Git repo.

### 1. Put the code on GitHub (free)

Create a free account at <https://github.com>, then a new **empty** repository called `glasshouse`.
In this folder:

```powershell
cd C:\Users\TheGingerWeeb\glasshouse
git init
git add .
git commit -m "Glasshouse"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/glasshouse.git
git push -u origin main
```

(If Git asks for a password, GitHub wants a **personal access token**, not your account password:
Settings → Developer settings → Personal access tokens → Tokens (classic) → Generate new token,
tick `repo`, then paste the token as the password.)

### 2. Deploy on Render (free)

1. Sign up at <https://render.com> — no card required.
2. Click **New → Blueprint**.
3. Connect GitHub and pick the `glasshouse` repo. Render reads `render.yaml` automatically.
4. Click **Apply**. Choose the **Free** plan if it asks.
5. Wait for the build (a few minutes), then open the `https://glasshouse-xxxx.onrender.com` URL.

If you prefer **New → Web Service** instead of a Blueprint, use:

| Setting | Value |
|---|---|
| Language | Python |
| Build command | `pip install -r requirements.txt` |
| Start command | `uvicorn app.main:app --host 0.0.0.0 --port $PORT --no-access-log` |
| Health check path | `/healthz` |
| Plan | Free |

### What the free tier means

- It sleeps after **15 minutes** with no visitors and takes about **a minute** to wake up. The first
  visitor sees a loading page; that is normal.
- **512 MB RAM / 0.1 CPU**, one instance. The `render.yaml` lowers scan concurrency to suit it.
- Render can restart it at any time, which wipes in-memory jobs. The **Download my plan (.json)**
  button still preserves your ticks, notes and follow-up dates.
- 750 free instance-hours per month. One always-awake service is ~730 hours, so keep it to one.

---

## Configuration

| Variable | Default | Meaning |
|---|---|---|
| `GLASSHOUSE_COOLDOWN` | `180` | Seconds between scans per IP |
| `GLASSHOUSE_TTL` | `600` | Seconds a finished job stays in memory |
| `GLASSHOUSE_MAX_SCANS` | `15` | Max simultaneous scans |
| `GLASSHOUSE_MAX_SITES` | `160` | Site cap per scan |
| `GLASSHOUSE_CONCURRENCY` | `20` | Parallel outbound requests |
| `GLASSHOUSE_UA` | `Glasshouse/1.0 ...` | User-Agent sent to checked sites |

Set these in Render under **Environment** (or edit `render.yaml`). Python is pinned to 3.12 in
`.python-version`; remove that file to use Render's default.

---

## Extending the site list

`app/data/sites.json` is plain data. Each entry looks like:

```json
{
  "id": "github",
  "name": "GitHub",
  "category": "dev",
  "host": "github.com",
  "url": "https://github.com/{username}",
  "check": "https://api.github.com/users/{username}",
  "kind": "json",
  "json_path": "login"
}
```

- `kind: "json"` reads a field out of a JSON API and treats a missing/empty value as "no account".
- `kind: "text"` looks for `absent_markers` / `present_markers` in the HTML.
- `kind: "status"` treats 404/410 as absent and 200 as found. Add `"soft": true` for sites that
  answer 200 even for missing profiles — those get reported as "unclear" instead of a false positive.
- `"subdomain": true` treats a DNS failure as "no account" (for `username.example.com` sites).
- `"manual": true` skips probing and shows the profile URL as a self-check link.

The live categories are `dev`, `social`, `creative`, `gaming`, `professional`, `marketplace`,
`forums` and `regional`. Add a category to both `app/scanner/report.py` and `app/scanner/engine.py`
if you introduce a new one.

Before adding a site, prove it with the audit:

```powershell
.\.venv\Scripts\python.exe scripts\audit_sites.py
```

It probes every automated site with a known username (`torvalds`) and a gibberish one
(`zzqx8f3k9v0m2`). A site that reports "found" for the gibberish name must be marked `"soft": true`
or removed. The command exits non-zero when a false positive is present.

`scripts/inspect_probe.py SITE_ID` prints the raw status, title and visible text for both usernames,
which is the quickest way to find a reliable `absent_marker`.

Add the site's deletion/settings page under `deleteUrl` if you want an extra shortcut in the report.

Broker data lives in `app/data/brokers.json`, grouped by `US`, `UK`, `EU`, `CA`, `AU`.

---

## Detection quality

The honest version:

- **High confidence** — API-backed checks and explicit "user not found" markers.
- **Medium confidence** — a 200 response from a site that correctly 404s for missing profiles.
- **Unclear** — sites known to soft-404, rate limiting, blocked requests, timeouts.
- **Not checked** — anything private, anything not on the list, anything behind a login.

Shared hosting means one outbound IP for every visitor, so some sites will rate-limit. That is why
blocked sources are reported as blocked rather than as "not found".

---

## Checks before shipping

```powershell
# Offline: renders every template and asserts the report has content.
.\.venv\Scripts\python.exe scripts\check.py

# Quality gate: every automated probe against a known and a gibberish username.
.\.venv\Scripts\python.exe scripts\audit_sites.py

# Live: start the server in another shell with the cooldown off, then run the flow test.
$env:GLASSHOUSE_COOLDOWN="0"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
.\.venv\Scripts\python.exe scripts\e2e.py torvalds
```

`e2e.py` checks scan → report → broker status → calendar → export/import → tracker → region switch
→ wipe. `scripts/probe_urls.py URL...` prints status, redirect target and title for any link you
are considering adding.

---

## Ethics and legal notes

- The tool is a self-audit aid. The consent checkbox is not a technical control — anyone can lie to
  a public website. Don't be that person.
- Only public pages are requested, with a descriptive User-Agent and bounded concurrency.
- Removal-email templates reference GDPR Art. 17, UK GDPR, CCPA/CPRA, PIPEDA and the Australian
  Privacy Act. They are templates, not legal advice.
- Data-broker links point at each company's own request process. Verify the page before submitting
  personal details; brokers change URLs and occasionally change hands.

## License

MIT.
