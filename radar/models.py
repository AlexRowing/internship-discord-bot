"""Plain data structures passed between scrapers and the bot."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RawListing:
    """One internship as pulled off a website, before de-duplication."""
    company: str
    title: str
    url: str = ""
    location: str = ""
    term: str = ""
    category: str = ""
    # A site-native stable id (e.g. Simplify's UUID), if the source provides one.
    native_id: str = ""

    def clean(self) -> "RawListing":
        self.company = (self.company or "").strip()
        self.title = (self.title or "").strip()
        self.url = (self.url or "").strip()
        self.location = (self.location or "").strip()
        self.term = (self.term or "").strip()
        self.category = (self.category or "").strip()
        return self

    def is_valid(self) -> bool:
        # Need at least a title to be a real listing.
        return bool(self.title)


@dataclass
class Listing:
    """A de-duplicated opportunity as stored in the database."""
    id: int
    fingerprint: str
    company: str
    title: str
    location: str
    url: str
    term: str
    category: str
    first_seen_at: float
    first_source_id: int
    notified: int
    other_sources: list[str] = field(default_factory=list)
