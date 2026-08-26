"""SQLite storage: the bot's long-term memory.

Three tables:
  sources   — the websites you're watching (/watch)
  listings  — the GLOBAL de-duplicated set of opportunities ever seen
  sightings — which source(s) each listing has appeared on (many-to-many)
"""
from __future__ import annotations

import sqlite3
import time
from contextlib import contextmanager

from .models import Listing, RawListing
from . import dedup

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sources (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    url           TEXT UNIQUE NOT NULL,
    name          TEXT NOT NULL,
    kind          TEXT NOT NULL,
    active        INTEGER NOT NULL DEFAULT 1,
    added_at      REAL NOT NULL,
    last_checked  REAL,
    last_ok       REAL,
    last_error    TEXT,
    check_count   INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS listings (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    fingerprint     TEXT UNIQUE NOT NULL,
    company         TEXT,
    title           TEXT,
    location        TEXT,
    url             TEXT,
    term            TEXT,
    category        TEXT,
    first_seen_at   REAL NOT NULL,
    first_source_id INTEGER,
    notified        INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS sightings (
    listing_id    INTEGER NOT NULL,
    source_id     INTEGER NOT NULL,
    first_seen_at REAL NOT NULL,
    url_on_source TEXT,
    PRIMARY KEY (listing_id, source_id)
);
"""


class Database:
    def __init__(self, path: str):
        self.path = path
        self._conn = sqlite3.connect(path)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    @contextmanager
    def _tx(self):
        try:
            yield self._conn
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise

    # ---- sources ---------------------------------------------------------

    def add_source(self, url: str, name: str, kind: str) -> int:
        with self._tx() as c:
            cur = c.execute(
                "INSERT INTO sources (url, name, kind, added_at) VALUES (?,?,?,?) "
                "ON CONFLICT(url) DO UPDATE SET active=1, name=excluded.name, kind=excluded.kind",
                (url, name, kind, time.time()),
            )
            row = c.execute("SELECT id FROM sources WHERE url=?", (url,)).fetchone()
            return row["id"]

    def deactivate_source(self, url: str) -> bool:
        with self._tx() as c:
            cur = c.execute("UPDATE sources SET active=0 WHERE url=? AND active=1", (url,))
            return cur.rowcount > 0

    def get_sources(self, active_only: bool = True) -> list[sqlite3.Row]:
        q = "SELECT * FROM sources"
        if active_only:
            q += " WHERE active=1"
        q += " ORDER BY added_at"
        return self._conn.execute(q).fetchall()

    def touch_source(self, source_id: int, ok: bool, error: str | None = None) -> None:
        now = time.time()
        with self._tx() as c:
            if ok:
                c.execute(
                    "UPDATE sources SET last_checked=?, last_ok=?, last_error=NULL, "
                    "check_count=check_count+1 WHERE id=?",
                    (now, now, source_id),
                )
            else:
                c.execute(
                    "UPDATE sources SET last_checked=?, last_error=?, "
                    "check_count=check_count+1 WHERE id=?",
                    (now, (error or "")[:500], source_id),
                )

    # ---- listings + sightings -------------------------------------------

    def record(self, raw: RawListing, source_id: int, baseline: bool) -> tuple[Listing, bool, bool]:
        """Insert/lookup a listing and record that `source_id` has seen it.

        Returns (listing, is_new_listing, is_new_sighting).
          is_new_listing   — first time this opportunity has EVER been seen anywhere.
          is_new_sighting  — first time THIS source has shown this opportunity.

        `baseline=True` marks freshly-created listings as already-notified, so the
        very first scrape of a newly-watched site never floods you with old jobs.
        """
        fp = dedup.fingerprint(raw)
        now = time.time()
        with self._tx() as c:
            existing = c.execute(
                "SELECT * FROM listings WHERE fingerprint=?", (fp,)
            ).fetchone()
            if existing is None:
                c.execute(
                    "INSERT INTO listings "
                    "(fingerprint, company, title, location, url, term, category, "
                    " first_seen_at, first_source_id, notified) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (fp, raw.company, raw.title, raw.location, raw.url, raw.term,
                     raw.category, now, source_id, 1 if baseline else 0),
                )
                listing_id = c.execute(
                    "SELECT id FROM listings WHERE fingerprint=?", (fp,)
                ).fetchone()["id"]
                is_new_listing = True
            else:
                listing_id = existing["id"]
                is_new_listing = False
                # Backfill an apply URL if we didn't have one before.
                if raw.url and not existing["url"]:
                    c.execute("UPDATE listings SET url=? WHERE id=?", (raw.url, listing_id))

            cur = c.execute(
                "INSERT OR IGNORE INTO sightings "
                "(listing_id, source_id, first_seen_at, url_on_source) VALUES (?,?,?,?)",
                (listing_id, source_id, now, raw.url),
            )
            is_new_sighting = cur.rowcount > 0

        return self.get_listing(listing_id), is_new_listing, is_new_sighting

    def mark_notified(self, listing_id: int) -> None:
        with self._tx() as c:
            c.execute("UPDATE listings SET notified=1 WHERE id=?", (listing_id,))

    def get_listing(self, listing_id: int) -> Listing:
        row = self._conn.execute("SELECT * FROM listings WHERE id=?", (listing_id,)).fetchone()
        if row is None:
            raise KeyError(f"no listing with id {listing_id}")
        others = self._conn.execute(
            "SELECT s.name FROM sightings sg JOIN sources s ON s.id=sg.source_id "
            "WHERE sg.listing_id=? ORDER BY sg.first_seen_at",
            (listing_id,),
        ).fetchall()
        return Listing(
            id=row["id"], fingerprint=row["fingerprint"], company=row["company"],
            title=row["title"], location=row["location"], url=row["url"],
            term=row["term"], category=row["category"], first_seen_at=row["first_seen_at"],
            first_source_id=row["first_source_id"], notified=row["notified"],
            other_sources=[o["name"] for o in others],
        )

    # ---- stats -----------------------------------------------------------

    def counts(self) -> dict:
        c = self._conn
        return {
            "sources": c.execute("SELECT COUNT(*) n FROM sources WHERE active=1").fetchone()["n"],
            "listings": c.execute("SELECT COUNT(*) n FROM listings").fetchone()["n"],
            "sightings": c.execute("SELECT COUNT(*) n FROM sightings").fetchone()["n"],
        }

    def radar_stats(self, since_days: int = 7) -> list[dict]:
        """Per-source: total sightings, uniques first-found here, recent uniques."""
        since = time.time() - since_days * 86400
        rows = self._conn.execute(
            """
            SELECT s.id, s.name, s.last_ok, s.last_error,
                   (SELECT COUNT(*) FROM sightings sg WHERE sg.source_id=s.id) AS sightings,
                   (SELECT COUNT(*) FROM listings l WHERE l.first_source_id=s.id) AS uniques,
                   (SELECT COUNT(*) FROM listings l WHERE l.first_source_id=s.id
                        AND l.first_seen_at >= ?) AS recent_uniques
            FROM sources s WHERE s.active=1 ORDER BY uniques DESC, sightings DESC
            """,
            (since,),
        ).fetchall()
        return [dict(r) for r in rows]
