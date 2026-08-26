"""Intern Insider (interninsider.me).

A Next.js app that renders job cards client-side, so it needs Playwright. Each
card is an <li> linking to /internships/<company-slug>/<title-slug>-<uuid>, which
gives us a stable per-job id and the company name for free.

The feed is token-gated: the URL carries a PERSONAL mcp_token. Keep that full URL
in .env as INTERNINSIDER_URL (never in code / Discord / git). Then /watch the
plain domain — this scraper swaps in the token URL from .env for the real fetch.
The token expires periodically; when it does, refresh INTERNINSIDER_URL in .env.
"""
from __future__ import annotations

import re
from urllib.parse import urljoin

from .base import Source, USER_AGENT
from ..config import config
from ..models import RawListing

BASE = "https://interninsider.me"

# Runs in the page: one record per <li> that links to a real internship.
_EXTRACT_JS = """els => els.map(li => {
    const a = li.querySelector('a[href^="/internships/"]');
    if (!a) return null;
    return { href: a.getAttribute('href'),
             text: li.innerText.replace(/\\n+/g, ' | ').slice(0, 200) };
}).filter(Boolean)"""

_HREF_RE = re.compile(r"^/internships/([^/]+)/(.+)$")


class InternInsiderSource(Source):
    kind = "interninsider"

    @classmethod
    def handles(cls, url: str) -> bool:
        return "interninsider.me" in url.lower()

    @staticmethod
    def default_name(url: str) -> str:
        return "Intern Insider"

    def _real_url(self) -> str:
        # Prefer the token-bearing URL from .env; fall back to the watched URL.
        return config.interninsider_url or self.url

    def fetch(self) -> list[RawListing]:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as e:
            raise RuntimeError(
                "Intern Insider needs Playwright: pip install playwright && "
                "python -m playwright install chromium") from e

        url = self._real_url()
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(user_agent=USER_AGENT)
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(6000)  # let cards hydrate
                data = page.eval_on_selector_all("li", _EXTRACT_JS)
            finally:
                browser.close()

        out: list[RawListing] = []
        for d in data:
            href = d.get("href") or ""
            m = _HREF_RE.match(href)
            if not m:  # skip nav / pagination links
                continue
            company = m.group(1).replace("-", " ").title()
            parts = [x.strip() for x in (d.get("text") or "").split("|")]
            title = parts[0] if parts else ""
            location = ""
            for seg in parts[1:]:
                if seg and seg.lower() not in ("new", "featured"):
                    location = seg
                    break
            native_id = href.rsplit("-", 1)[-1]  # trailing UUID
            out.append(RawListing(
                company=company, title=title, url=urljoin(BASE, href),
                location=location, native_id=native_id).clean())
        return [x for x in out if x.is_valid()]
