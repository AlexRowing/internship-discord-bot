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
        if "listings.json" in u:
            return True
        # Any GitHub repo that looks like a community internship / new-grad list
        # publishes the same listings.json format (SimplifyJobs, vanshb03, cvrve, …).
        if "github.com/" in u and any(
            k in u for k in ("intern", "new-grad", "newgrad", "simplifyjobs")
        ):
            return True
        return False

    def _feed_urls(self) -> list[str]:
        """Candidate raw-JSON URLs to try, in order (repos use dev or main)."""
        if "listings.json" in self.url and "raw.githubusercontent" in self.url:
            return [self.url]
        m = _GITHUB_RE.search(self.url)
        if m:
            owner, repo = m.group(1), m.group(2).replace(".git", "")
            base = f"https://raw.githubusercontent.com/{owner}/{repo}"
            return [f"{base}/dev/.github/scripts/listings.json",
                    f"{base}/main/.github/scripts/listings.json"]
        return [DEFAULT_FEED]

    def fetch(self) -> list[RawListing]:
        data = None
        last_exc: Exception | None = None
        for feed in self._feed_urls():
            try:
                resp = requests.get(feed, headers={"User-Agent": USER_AGENT}, timeout=45)
                if resp.status_code == 404:
                    continue
                resp.raise_for_status()
                data = resp.json()
                break
            except Exception as e:  # noqa: BLE001 — try the next candidate branch
                last_exc = e
        if data is None:
            raise last_exc or RuntimeError("No listings.json found (tried dev and main)")

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
