"""Best-effort scraper for arbitrary static (server-rendered) pages.

There is no universal way to read every site, so this uses heuristics: it looks
for anchor tags whose text looks like a job title, plus common job-card markup.
It WILL miss things and occasionally grab noise — that's the nature of generic
scraping. For sites that matter, write a dedicated Source subclass with real
selectors (see simplify.py for the gold-standard pattern).
"""
from __future__ import annotations

import re
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from .base import Source, USER_AGENT
from ..models import RawListing

# A title that looks intern-y. Used to filter the noise.
_JOBLIKE = re.compile(
    r"intern|co-?op|new grad|graduate|entry level|early career", re.IGNORECASE
)
_ROLELIKE = re.compile(
    r"engineer|developer|software|data|machine learning|ml|ai|scientist|analyst|swe",
    re.IGNORECASE,
)


class GenericHtmlSource(Source):
    kind = "generic"

    @classmethod
    def handles(cls, url: str) -> bool:
        # Lowest-priority fallback — the registry only reaches here last.
        return url.startswith("http")

    def fetch(self) -> list[RawListing]:
        resp = requests.get(self.url, headers={"User-Agent": USER_AGENT}, timeout=45)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        return self.extract(soup, self.url)

    @staticmethod
    def extract(soup: BeautifulSoup, base_url: str) -> list[RawListing]:
        seen: set[str] = set()
        out: list[RawListing] = []

        for a in soup.find_all("a"):
            text = " ".join(a.get_text(" ", strip=True).split())
            if len(text) < 6 or len(text) > 140:
                continue
            if not (_JOBLIKE.search(text) or _ROLELIKE.search(text)):
                continue
            href = a.get("href") or ""
            url = urljoin(base_url, href) if href else ""
            key = (text.lower(), url)
            if key in seen:
                continue
            seen.add(key)

            company, location = _sniff_context(a)
            out.append(RawListing(
                company=company,
                title=text,
                url=url,
                location=location,
            ).clean())

        return [x for x in out if x.is_valid()]


def _sniff_context(anchor) -> tuple[str, str]:
    """Peek at nearby markup to guess company/location. Very best-effort."""
    company = ""
    location = ""
    parent = anchor.parent
    for _ in range(3):  # walk up a few levels
        if parent is None:
            break
        for attr in ("data-company", "data-org"):
            if parent.has_attr(attr):
                company = parent[attr]
        loc_el = parent.find(attrs={"class": re.compile("location", re.I)})
        if loc_el and not location:
            location = loc_el.get_text(" ", strip=True)[:80]
        parent = parent.parent
    return company, location
