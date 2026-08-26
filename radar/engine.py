"""The scraping/dedup pipeline, with no Discord dependencies so it can be tested
and reused independently.

Split into two halves on purpose:
  scrape()  — pure network I/O, safe to run in a worker thread.
  fold()    — all SQLite writes, MUST run on the thread that owns the DB.
This keeps SQLite happy (its connections are single-thread) while still letting
the slow network work happen off the event loop.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .db import Database
from .models import Listing, RawListing
from .relevance import is_relevant
from .sources import source_for_kind, Source


@dataclass
class CheckResult:
    source_id: int
    source_name: str
    ok: bool
    error: str = ""
    total_seen: int = 0
    new_listings: list[Listing] = field(default_factory=list)   # brand-new anywhere + relevant
    new_sightings: int = 0                                       # dup jobs newly appearing here


def build_source(source_row) -> Source:
    return source_for_kind(source_row["kind"], source_row["url"], source_row["name"])


def scrape(src: Source) -> list[RawListing]:
    """Network-only. Runs in a worker thread. May raise — caller handles it."""
    return src.fetch()


def fold(db: Database, source_row, raws: list[RawListing], baseline: bool) -> CheckResult:
    """DB-only. Runs on the main/DB thread. Reports what's genuinely new.

    `baseline=True` (first /watch) records everything as already-known so you
    don't get pinged for the site's entire pre-existing backlog.
    """
    result = CheckResult(source_id=source_row["id"], source_name=source_row["name"],
                         ok=True, total_seen=len(raws))
    for raw in raws:
        listing, is_new_listing, is_new_sighting = db.record(raw, source_row["id"], baseline)
        if is_new_sighting and not is_new_listing:
            result.new_sightings += 1
        if is_new_listing and not baseline and listing.notified == 0 and is_relevant(raw):
            result.new_listings.append(listing)
    db.touch_source(source_row["id"], ok=True)
    return result
