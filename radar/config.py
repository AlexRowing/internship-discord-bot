"""Configuration, loaded from environment / .env file."""
from __future__ import annotations

import os
from dataclasses import dataclass, field

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:  # dotenv is optional at import time
    pass


def _int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    try:
        return int(raw) if raw else default
    except ValueError:
        return default


def _csv(name: str, default: tuple[str, ...]) -> tuple[str, ...]:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    return tuple(part.strip().lower() for part in raw.split(",") if part.strip())


@dataclass
class Config:
    discord_token: str = field(default_factory=lambda: os.getenv("DISCORD_TOKEN", "").strip())
    guild_id: int = field(default_factory=lambda: _int("DISCORD_GUILD_ID", 0))

    channel_new: int = field(default_factory=lambda: _int("CHANNEL_NEW_INTERNSHIPS", 0))
    channel_sources: int = field(default_factory=lambda: _int("CHANNEL_NEW_SOURCES", 0))
    channel_stats: int = field(default_factory=lambda: _int("CHANNEL_RADAR_STATS", 0))

    check_interval_minutes: int = field(default_factory=lambda: _int("CHECK_INTERVAL_MINUTES", 30))
    db_path: str = field(default_factory=lambda: os.getenv("RADAR_DB_PATH", "radar.db"))

    # Ping @everyone on new listings? (set PING_EVERYONE=false to disable)
    ping_everyone: bool = field(
        default_factory=lambda: os.getenv("PING_EVERYONE", "true").strip().lower()
        not in ("0", "false", "no", "off"))

    relevance_keywords: tuple[str, ...] = field(default_factory=lambda: _csv(
        "RELEVANCE_KEYWORDS",
        ("software", "swe", "developer", "machine learning", "ml", "ai",
         "artificial intelligence", "data", "full stack", "backend",
         "frontend", "computer"),
    ))
    term_filter: tuple[str, ...] = field(default_factory=lambda: _csv("TERM_FILTER", ("2027",)))

    interninsider_url: str = field(default_factory=lambda: os.getenv("INTERNINSIDER_URL", "").strip())

    # Channels fall back to the main channel if not separately configured.
    def channel_for(self, kind: str) -> int:
        if kind == "sources":
            return self.channel_sources or self.channel_new
        if kind == "stats":
            return self.channel_stats or self.channel_new
        return self.channel_new

    def validate(self) -> list[str]:
        problems = []
        if not self.discord_token:
            problems.append("DISCORD_TOKEN is not set.")
        if not self.channel_new:
            problems.append("CHANNEL_NEW_INTERNSHIPS is not set.")
        return problems


config = Config()
