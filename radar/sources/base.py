"""The Source contract. Each website type implements one of these."""
from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import RawListing

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 InternshipRadar/0.1"
)


class Source(ABC):
    #: short machine name stored in the DB (e.g. "simplify", "generic", "playwright")
    kind: str = "base"

    def __init__(self, url: str, name: str = ""):
        self.url = url
        self.name = name or self.default_name(url)

    @classmethod
    @abstractmethod
    def handles(cls, url: str) -> bool:
        """Return True if this Source knows how to scrape the given URL."""

    @staticmethod
    def default_name(url: str) -> str:
        from urllib.parse import urlparse
        host = urlparse(url).netloc.replace("www.", "")
        return host or url

    @abstractmethod
    def fetch(self) -> list[RawListing]:
        """Scrape the site and return current listings. Runs in a worker thread,
        so blocking I/O (requests, Playwright sync API) is fine here."""
