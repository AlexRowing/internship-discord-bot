"""SimplifyJobs / vanshb03-style GitHub internship lists.

These repos publish a structured `listings.json` — no fragile HTML scraping.
This is the single most reliable source in the whole bot.
"""
from __future__ import annotations

import re

import requests

from .base import Source, USER_AGENT
from ..models import RawListing

# Known good feed. The repo keeps the JSON on the `dev` branch.
DEFAULT_FEED = (
    "https://raw.githubusercontent.com/SimplifyJobs/"
    "Summer2027-Internships/dev/.github/scripts/listings.json"
)

_GITHUB_RE = re.compile(r"github\.com/([^/]+)/([^/]+)", re.IGNORECASE)


class SimplifySource(Source):
    kind = "simplify"

    @classmethod
    def handles(cls, url: str) -> bool:
        u = url.lower()
        return "github.com/simplifyjobs" in u or "listings.json" in u

    def _feed_url(self) -> str:
        # Accept the human GitHub URL and translate it to the raw JSON feed.
        if "listings.json" in self.url and "raw.githubusercontent" in self.url:
            return self.url
        m = _GITHUB_RE.search(self.url)
        if m:
            owner, repo = m.group(1), m.group(2).replace(".git", "")
            return (f"https://raw.githubusercontent.com/{owner}/{repo}/"
                    "dev/.github/scripts/listings.json")
        return DEFAULT_FEED

    def fetch(self) -> list[RawListing]:
        resp = requests.get(self._feed_url(), headers={"User-Agent": USER_AGENT}, timeout=45)
        resp.raise_for_status()
        data = resp.json()

        out: list[RawListing] = []
        for r in data:
            if not r.get("active", True) or not r.get("is_visible", True):
                continue
            locations = r.get("locations") or []
            terms = r.get("terms") or []
            out.append(RawListing(
                company=r.get("company_name", ""),
                title=r.get("title", ""),
                url=r.get("url", ""),
                location=", ".join(locations),
                term=", ".join(terms),
                category=r.get("category", ""),
                native_id=r.get("id", ""),
            ).clean())
        return [x for x in out if x.is_valid()]
