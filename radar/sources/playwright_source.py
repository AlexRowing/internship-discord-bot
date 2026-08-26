"""Renderer for JavaScript-heavy sites (Runway, intern-list, etc.).

These sites build their listings in the browser with JS, so plain HTTP fetching
returns an empty shell. We spin up a real headless Chromium via Playwright, let
the page render, then reuse the generic heuristic extractor on the result.

Honest caveat: generic extraction on a rendered page is still best-effort. Sites
with bot-protection may block even this. When a site really matters, replace
`fetch()` here with page-specific selectors (page.locator(...)).

Requires:  pip install playwright  &&  python -m playwright install chromium
"""
from __future__ import annotations

from .base import Source
from .generic import GenericHtmlSource
from ..models import RawListing

# Domains we know need JS rendering.
JS_DOMAINS = ("joinrunway.io", "intern-list.com", "interninsider.me")


class PlaywrightSource(Source):
    kind = "playwright"

    @classmethod
    def handles(cls, url: str) -> bool:
        u = url.lower()
        return any(d in u for d in JS_DOMAINS)

    def fetch(self) -> list[RawListing]:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as e:
            raise RuntimeError(
                "This site needs a JavaScript browser. Install it once with:\n"
                "    pip install playwright\n"
                "    python -m playwright install chromium"
            ) from e

        from bs4 import BeautifulSoup

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
            ))
            try:
                page.goto(self.url, wait_until="networkidle", timeout=60000)
                page.wait_for_timeout(2500)  # let late XHR settle
                html = page.content()
            finally:
                browser.close()

        soup = BeautifulSoup(html, "html.parser")
        return GenericHtmlSource.extract(soup, self.url)
