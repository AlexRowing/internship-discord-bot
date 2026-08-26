"""The Discord bot: slash commands, embed cards, and the periodic check loop."""
from __future__ import annotations

import asyncio
import datetime as dt
import time

import discord
from discord import app_commands
from discord.ext import commands, tasks

from .config import config
from .db import Database
from .engine import build_source, scrape, fold
from .models import Listing
from .sources import pick_source

INTENTS = discord.Intents.default()
CHECK_MINUTES = max(5, config.check_interval_minutes)


# ───────────────────────────── presentation ─────────────────────────────

def listing_embed(listing: Listing, source_name: str) -> discord.Embed:
    when = dt.datetime.fromtimestamp(listing.first_seen_at).strftime("%I:%M %p, %b %d")
    embed = discord.Embed(
        title=listing.title or "Internship",
        description=f"**{listing.company}**" if listing.company else None,
        color=0x2ecc71,
        timestamp=dt.datetime.now(dt.timezone.utc),
    )
    if listing.location:
        embed.add_field(name="📍 Location", value=listing.location[:200], inline=True)
    if listing.term:
        embed.add_field(name="🗓️ Term", value=listing.term[:100], inline=True)
    if listing.category:
        embed.add_field(name="🏷️ Category", value=listing.category[:100], inline=True)

    embed.add_field(name="🔎 Found on", value=source_name, inline=True)
    embed.add_field(name="🕐 First detected", value=when, inline=True)

    others = [s for s in listing.other_sources if s != source_name]
    if others:
        embed.add_field(name="🔗 Also listed on", value=", ".join(others[:5]), inline=False)

    embed.set_footer(text="🚨 Previously unseen on your radar")
    return embed


def listing_view(listing: Listing, source_url: str = "") -> discord.ui.View | None:
    view = discord.ui.View()
    added = False
    if listing.url.startswith("http"):
        view.add_item(discord.ui.Button(label="Apply", style=discord.ButtonStyle.link,
                                         url=listing.url, emoji="✅"))
        added = True
    if source_url.startswith("http"):
        view.add_item(discord.ui.Button(label="Source", style=discord.ButtonStyle.link,
                                         url=source_url, emoji="🌐"))
        added = True
    return view if added else None


def browse_embed(heading: str, listings: list[Listing]) -> discord.Embed:
    if not listings:
        return discord.Embed(title=heading, description="_Nothing found yet._",
                             color=0x95a5a6)
    lines = []
    for l in listings:
        title = l.title[:80]
        head = f"[{title}]({l.url})" if l.url.startswith("http") else title
        bits = [b for b in (l.company, (l.location or "")[:40], (l.term or "")[:30]) if b]
        sub = " · ".join(bits)
        lines.append(f"**{head}**" + (f"\n{sub}" if sub else ""))
    return discord.Embed(title=heading, description="\n\n".join(lines)[:4000],
                         color=0x1abc9c)


# ───────────────────────────── the bot ─────────────────────────────

class RadarBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!radar ", intents=INTENTS, help_command=None)
        self.db = Database(config.db_path)
        self.started_at = time.time()

    async def setup_hook(self) -> None:
        await self.add_cog(RadarCog(self))
        try:
            if config.guild_id:
                guild = discord.Object(id=config.guild_id)
                self.tree.copy_global_to(guild=guild)
                await self.tree.sync(guild=guild)
            else:
                await self.tree.sync()
        except discord.Forbidden:
            print("⚠️  Could not register slash commands (403 Missing Access).")
            print("    The bot must be invited to your server WITH the")
            print("    'applications.commands' scope. Re-invite it via:")
            print("    Developer Portal → OAuth2 → URL Generator →")
            print("    scopes: bot + applications.commands, then restart.")
            print("    Also confirm DISCORD_GUILD_ID is the server the bot is in.")
        self.check_loop.start()

    async def on_ready(self) -> None:
        n = len(self.db.get_sources())
        print(f"✅ Logged in as {self.user}. Watching {n} source(s). "
              f"Checking every {CHECK_MINUTES} min.")

    async def channel(self, kind: str) -> discord.abc.Messageable | None:
        cid = config.channel_for(kind)
        if not cid:
            return None
        ch = self.get_channel(cid)
        if ch is None:
            try:
                ch = await self.fetch_channel(cid)
            except discord.DiscordException:
                return None
        return ch

    async def post_new_listings(self, results) -> int:
        """Send embed cards for every genuinely-new listing. Returns count posted."""
        channel = await self.channel("new")
        posted = 0
        for res in results:
            src_url = self._source_url(res.source_id)
            for listing in res.new_listings:
                if channel is not None:
                    await channel.send(embed=listing_embed(listing, res.source_name),
                                       view=listing_view(listing, src_url))
                    await asyncio.sleep(0.8)  # be gentle with rate limits
                self.db.mark_notified(listing.id)
                posted += 1
        return posted

    def _source_url(self, source_id: int) -> str:
        for row in self.db.get_sources(active_only=False):
            if row["id"] == source_id:
                return row["url"]
        return ""

    async def run_all_checks(self, announce: bool = True) -> list:
        results = []
        for row in self.db.get_sources():
            src = build_source(row)
            try:
                raws = await asyncio.to_thread(scrape, src)
            except Exception as e:  # noqa: BLE001
                self.db.touch_source(row["id"], ok=False, error=f"{type(e).__name__}: {e}")
                from .engine import CheckResult
                results.append(CheckResult(row["id"], row["name"], ok=False,
                                           error=f"{type(e).__name__}: {e}"))
                continue
            results.append(fold(self.db, row, raws, baseline=False))
        if announce:
            await self.post_new_listings(results)
        return results

    @tasks.loop(minutes=CHECK_MINUTES)
    async def check_loop(self) -> None:
        try:
            await self.run_all_checks(announce=True)
        except Exception as e:  # noqa: BLE001 — never let the loop die silently
            print(f"[check_loop] error: {type(e).__name__}: {e}")

    @check_loop.before_loop
    async def _before(self) -> None:
        await self.wait_until_ready()


# ───────────────────────────── commands ─────────────────────────────

class RadarCog(commands.Cog):
    def __init__(self, bot: RadarBot):
        self.bot = bot

    @app_commands.command(description="Start watching a website for new internships.")
    @app_commands.describe(url="The listings page URL", name="Optional friendly name")
    async def watch(self, interaction: discord.Interaction, url: str, name: str = ""):
        if not url.startswith("http"):
            await interaction.response.send_message("❌ That doesn't look like a URL.",
                                                    ephemeral=True)
            return
        await interaction.response.defer(thinking=True)
        src = pick_source(url, name)
        source_id = self.bot.db.add_source(src.url, src.name, src.kind)

        try:  # baseline scrape — saves what's there now WITHOUT pinging
            raws = await asyncio.to_thread(scrape, src)
        except Exception as e:  # noqa: BLE001
            self.bot.db.touch_source(source_id, ok=False, error=str(e))
            await interaction.followup.send(
                f"⚠️ Added **{src.name}** (`{src.kind}` scraper), but the first read failed:\n"
                f"```{type(e).__name__}: {e}```\n"
                "I'll keep retrying on the schedule. JS-heavy sites need Playwright "
                "(see the README).")
            return

        res = fold(self.bot.db, {"id": source_id, "name": src.name}, raws, baseline=True)
        await interaction.followup.send(
            f"🛰️ Now watching **{src.name}**  (`{src.kind}` scraper)\n"
            f"Saved **{res.total_seen}** current listings as the baseline — "
            f"you'll only be pinged for things that appear *after* now.")

    @app_commands.command(description="Stop watching a website.")
    async def unwatch(self, interaction: discord.Interaction, url: str):
        ok = self.bot.db.deactivate_source(url)
        msg = f"🛑 Stopped watching `{url}`." if ok else f"🤷 I wasn't watching `{url}`."
        await interaction.response.send_message(msg, ephemeral=True)

    @app_commands.command(name="list", description="Show every site you're watching.")
    async def list_sources(self, interaction: discord.Interaction):
        rows = self.bot.db.get_sources()
        if not rows:
            await interaction.response.send_message(
                "No sites yet. Add one with `/watch <url>`.", ephemeral=True)
            return
        lines = []
        for r in rows:
            if r["last_error"]:
                status = f"⚠️ {r['last_error'][:60]}"
            elif r["last_ok"]:
                status = "✅ ok"
            else:
                status = "⏳ not checked yet"
            lines.append(f"**{r['name']}**  (`{r['kind']}`) — {status}\n<{r['url']}>")
        embed = discord.Embed(title="🛰️ Watched sources", color=0x3498db,
                              description="\n\n".join(lines)[:4000])
        await interaction.response.send_message(embed=embed)

    @app_commands.command(description="Check all sites right now instead of waiting.")
    async def check(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        results = await self.bot.run_all_checks(announce=True)
        total_new = sum(len(r.new_listings) for r in results)
        ok = sum(1 for r in results if r.ok)
        fail = [r for r in results if not r.ok]
        summary = (f"🔄 Checked **{len(results)}** source(s): {ok} ok, {len(fail)} failed.\n"
                   f"Found **{total_new}** new internship(s).")
        if fail:
            summary += "\n" + "\n".join(f"⚠️ {r.source_name}: {r.error[:80]}" for r in fail)
        await interaction.followup.send(summary)

    @app_commands.command(description="Show which sources actually produce new opportunities.")
    async def radar(self, interaction: discord.Interaction):
        stats = self.bot.db.radar_stats(since_days=7)
        if not stats:
            await interaction.response.send_message("No data yet.", ephemeral=True)
            return
        header = f"{'Source':<26}{'Unique':>8}{'7d':>6}{'Seen':>7}"
        lines = [header, "-" * len(header)]
        for s in stats:
            name = (s["name"] or "")[:25]
            lines.append(f"{name:<26}{s['uniques']:>8}{s['recent_uniques']:>6}{s['sightings']:>7}")
        table = "```\n" + "\n".join(lines) + "\n```"
        # Gently flag dead weight.
        dead = [s["name"] for s in stats if s["uniques"] == 0 and s["sightings"] > 0]
        tip = ""
        if dead:
            tip = ("\n💡 " + ", ".join(dead[:3]) +
                   " haven't produced a *unique* opportunity — consider `/unwatch`.")
        await interaction.response.send_message(
            "📊 **Your internship radar** (Unique = first found here)\n" + table + tip)

    @app_commands.command(description="Show the most recently discovered listings.")
    @app_commands.describe(count="How many to show (1–20, default 10)")
    async def latest(self, interaction: discord.Interaction, count: int = 10):
        count = max(1, min(20, count))
        listings = self.bot.db.recent_listings(count)
        await interaction.response.send_message(
            embed=browse_embed(f"🆕 Latest {len(listings)} listing(s)", listings))

    @app_commands.command(description="Search saved listings by company or title keyword.")
    @app_commands.describe(query="e.g. 'machine learning', 'Nvidia', 'backend'")
    async def search(self, interaction: discord.Interaction, query: str):
        listings = self.bot.db.search_listings(query, 15)
        await interaction.response.send_message(
            embed=browse_embed(f"🔎 '{query[:50]}' — {len(listings)} match(es)", listings))

    @app_commands.command(description="Bot status & counts.")
    async def status(self, interaction: discord.Interaction):
        c = self.bot.db.counts()
        up = int(time.time() - self.bot.started_at)
        h, m = up // 3600, (up % 3600) // 60
        embed = discord.Embed(title="🛰️ Internship Radar — status", color=0x9b59b6)
        embed.add_field(name="Sources", value=str(c["sources"]))
        embed.add_field(name="Unique listings", value=str(c["listings"]))
        embed.add_field(name="Total sightings", value=str(c["sightings"]))
        embed.add_field(name="Check interval", value=f"{CHECK_MINUTES} min")
        embed.add_field(name="Uptime", value=f"{h}h {m}m")
        await interaction.response.send_message(embed=embed, ephemeral=True)


def run() -> None:
    from ._console import setup_console
    setup_console()
    problems = config.validate()
    if problems:
        print("❌ Cannot start — fix your .env:")
        for p in problems:
            print("   -", p)
        print("\nCopy .env.example to .env and fill it in. See the README.")
        raise SystemExit(1)
    RadarBot().run(config.discord_token)
