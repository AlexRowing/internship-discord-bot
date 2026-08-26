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

## JavaScript-heavy sites (Runway, intern-list, interninsider) — experimental

These render listings in the browser, so they need Playwright:

```bash
pip install playwright
python -m playwright install chromium
```

The bot auto-routes those domains through Playwright, but **investigation showed
they resist scraping** and are not reliably supported today:

- **Runway** (`app.joinrunway.io`) — an authenticated single-page app. The explore
  page shows *recommendations* that require a logged-in session, its job cards use
  obfuscated markup, and its tRPC API evicts response bodies. Would need a real
  logged-in browser session to scrape.
- **intern-list.com** — a front-end for **jobright.ai**; the listings come from
  jobright's private API, not the page HTML. Hitting that directly is brittle and
  ToS-gray.
- **interninsider.me** — requires a **personal token**. Keep it in `.env` as
  `INTERNINSIDER_URL`, never in code, and rotate it since it was shared in
  plaintext.

If you `/watch` one of these, the bot won't crash — it just tends to find nothing,
and `/radar` will flag it as unproductive. For real coverage, prefer the
structured GitHub feeds above. To properly support a JS site, replace the generic
extraction in `radar/sources/playwright_source.py` with per-site selectors (or an
authenticated session) — see `radar/sources/simplify.py` for the gold standard.

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
