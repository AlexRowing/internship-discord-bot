# 🛰️ Internship Radar

A Discord bot that watches internship websites and pings you the moment a
**genuinely new** software / AI / data opportunity appears — with **global
de-duplication** so the same job posted on two sites only pings you once.

```
╭──────────────────────────────────────╮
│ 🚨 NEW INTERNSHIP                     │
│ Software Engineer Intern              │
│ Acme Robotics                         │
│ 📍 Remote      🗓️ Summer 2027         │
│ 🔎 Found on: SimplifyJobs             │
│ 🕐 First detected: 11:32 AM           │
│ [ ✅ APPLY ]  [ 🌐 SOURCE ]           │
╰──────────────────────────────────────╯
```

## What works today (V1 + V2)

- **`/watch <url>`** — start watching a site. The first read saves everything
  currently there as a *baseline*, so you are **never** spammed with old jobs.
- **Change detection** — every 30 min (configurable) it re-reads each site and
  pings you only for listings that appeared *after* you started watching.
- **Global de-dup** — `"SWE Intern"` and `"Software Engineer Intern – Summer 2027"`
  from the same company collapse to one opportunity. Seen it before on any site?
  No second ping — it just notes the extra source.
- **`/radar`** — shows which sources actually produce *unique* opportunities, and
  flags dead weight worth un-watching.
- Reliable **SimplifyJobs** feed built in, generic scraping for static sites, and
  optional **Playwright** rendering for JavaScript-heavy sites.

Commands: `/watch` · `/unwatch` · `/list` · `/check` · `/radar` · `/status`

## Setup (about 10 minutes)

### 1. Create the Discord bot (only you can do this)
1. Go to <https://discord.com/developers/applications> → **New Application**.
2. **Bot** tab → **Reset Token** → **Copy**. This is your `DISCORD_TOKEN`.
3. Still on the Bot tab, scroll to **Privileged Gateway Intents** — none are
   required, leave them off.
4. **OAuth2 → URL Generator**: tick **`bot`** and **`applications.commands`**
   scopes, then under Bot Permissions tick **Send Messages** and **Embed Links**.
   Open the generated URL and invite the bot to your server.

### 2. Get your IDs
In Discord: **Settings → Advanced → Developer Mode = ON**. Then right-click your
server → **Copy Server ID**, and right-click your target channel → **Copy Channel ID**.

### 3. Configure
```bash
cp .env.example .env
```
Open `.env` and paste in `DISCORD_TOKEN`, `DISCORD_GUILD_ID`, and
`CHANNEL_NEW_INTERNSHIPS`. (Optional channels and tuning are documented in the file.)

### 4. Install & run
```bash
python -m venv .venv
.venv\Scripts\activate            # Windows
pip install -r requirements.txt
python run.py
```

You should see `✅ Logged in as … Watching 0 source(s).` Then in Discord:

```
/watch https://github.com/SimplifyJobs/Summer2027-Internships
/check
```

## Verify scraping without Discord

Prove a site is readable before wiring up the bot:

```bash
python -m radar.selftest simplify          # the reliable SimplifyJobs feed
python -m radar.selftest https://any-site  # test /watch handling for any URL
```

## Recommended sources (reliable, structured — just `/watch` them)

These GitHub-maintained lists all publish the same clean `listings.json`, so they
scrape reliably and global de-dup merges their overlap:

```
/watch https://github.com/SimplifyJobs/Summer2027-Internships
/watch https://github.com/vanshb03/Summer2027-Internships
/watch https://github.com/SimplifyJobs/New-Grad-Positions
```

## JavaScript-heavy sites (need Playwright)

```bash
pip install playwright
python -m playwright install chromium
```

### ✅ Intern Insider (interninsider.me) — supported
Its feed is gated by a **personal token**. Put the full token URL in `.env`:

```
INTERNINSIDER_URL=https://interninsider.me/internships/new?mcp_token=YOUR_TOKEN
```

Then watch the plain domain (the scraper swaps in the token URL for the fetch, so
your token never lands in Discord or the database):

```
/watch https://interninsider.me/internships/new
```

The token **expires** every few weeks — when Intern Insider stops returning
results, refresh `INTERNINSIDER_URL` in `.env` and restart.

### ✅ intern-list.com — supported
intern-list embeds its listings from a public **jobright.ai** iframe
(`jobright.ai/minisites-jobs/intern/us/<category>?embed=true`). The scraper
renders that embed and parses the job cards. Just watch it:

```
/watch https://www.intern-list.com/          # defaults to the SWE category
/watch https://www.intern-list.com/?k=swe    # or pick a category via ?k=
```

### ❌ Runway (app.joinrunway.io) — not supported
An authenticated SPA. The explore page shows *recommendations* that require a
logged-in session, job cards use obfuscated markup, and its tRPC API rejects
requests without a logged-in session's exact internal payload
(`BAD_REQUEST: Required`). Would need to log in as you and reconstruct a private
API — brittle and against their terms.

To add another JS site yourself, copy the pattern in
`radar/sources/interninsider.py` or `radar/sources/intern_list.py`.

## How it's built

```
radar/
  config.py       env / .env settings
  db.py           SQLite: sources, listings (global dedup), sightings
  dedup.py        listing → stable fingerprint  ← swap in an LLM here for V3
  relevance.py    is this a SWE/AI/data role for the right term?
  engine.py       scrape() [threaded] + fold() [DB] pipeline
  bot.py          discord.py commands, embed cards, 30-min check loop
  sources/
    simplify.py   SimplifyJobs listings.json (reliable, structured)
    generic.py    best-effort static HTML
    playwright_source.py   JS rendering (optional)
```

## Roadmap

- **V1** Ping me when my sites change ✅
- **V2** Don't send duplicates ✅
- **V3** LLM matcher for fuzzy same-job detection (drop into `dedup.py`)
- **V4** `/discover` — find sites you *aren't* watching
- **V5** Surface opportunities unique to a newly-found site
