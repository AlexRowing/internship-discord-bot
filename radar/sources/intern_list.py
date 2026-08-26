"""intern-list.com.

intern-list embeds its listings from **jobright.ai** via an iframe
(`jobright.ai/minisites-jobs/intern/us/<category>?embed=true`) — the parent page
itself only shows category chips. So we render that public embed and parse its
job cards. Each card carries a stable jobright id (used for the apply link and
de-dup) plus title / work-model / location / company / salary / term.

Needs Playwright:  pip install playwright && python -m playwright install chromium
"""
from __future__ import annotations

import re
from urllib.parse import urlparse, parse_qs

from .base import Source, USER_AGENT
from ..models import RawListing

_WORK_MODELS = {"on site", "onsite", "on-site", "remote", "hybrid"}

# Returns one {id, lines} per job card in the embed.
_EXTRACT_JS = r"""els => {
  const seen = new Set(); const out = [];
  for (const a of els) {
    const href = a.getAttribute('href') || '';
    if (!href.includes('/jobs/info/')) continue;
    const id = href.split('/jobs/info/')[1].split('?')[0];
    if (seen.has(id)) continue; seen.add(id);
    let node = a;
    for (let i = 0; i < 7; i++) {
      if (node.parentElement) { node = node.parentElement;
        if ((node.innerText || '').length > 60) break; }
    }
    const lines = (node.innerText || '').split('\n').map(s => s.trim()).filter(Boolean);
    out.push({ id, lines });
  }
  return out;
}"""


class InternListSource(Source):
    kind = "intern-list"

    @classmethod
    def handles(cls, url: str) -> bool:
        return "intern-list.com" in url.lower()

    @staticmethod
    def default_name(url: str) -> str:
        return "Intern List"

    def _embed_url(self) -> str:
        # Honor the ?k=<category> filter from the intern-list URL (default swe).
        q = parse_qs(urlparse(self.url).query)
        cat = (q.get("k", ["swe"])[0] or "swe").strip().lower() or "swe"
        cat = re.sub(r"[^a-z0-9-]", "", cat)
        return f"https://jobright.ai/minisites-jobs/intern/us/{cat}?embed=true"

    def fetch(self) -> list[RawListing]:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as e:
            raise RuntimeError(
                "intern-list needs Playwright: pip install playwright && "
                "python -m playwright install chromium") from e

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(user_agent=USER_AGENT)
            try:
                page.goto(self._embed_url(), wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(6000)
                page.mouse.wheel(0, 3000)
                page.wait_for_timeout(2500)
                cards = page.eval_on_selector_all("a", _EXTRACT_JS)
            finally:
                browser.close()

        out: list[RawListing] = []
        for card in cards:
            raw = self._parse_card(card.get("id", ""), card.get("lines", []))
            if raw and raw.is_valid():
                out.append(raw)
        return out

    @staticmethod
    def _parse_card(job_id: str, lines: list[str]) -> RawListing | None:
        title = ""
        company = location = term = ""
        for ln in lines:
            parts = [x.strip() for x in ln.split("\t")]
            # Title line: "<title>\t<n> ... ago"
            if not title and len(parts) >= 2 and parts[-1].lower().endswith("ago"):
                title = parts[0]
            # Meta line: "<work model>\t<location>\t<company>\t<salary>\t<term?>"
            if len(parts) >= 3 and parts[0].lower() in _WORK_MODELS:
                location = parts[1]
                company = parts[2]
                if len(parts) >= 5 and parts[4]:
                    term = parts[4]
        if not title:
            return None
        url = f"https://jobright.ai/jobs/info/{job_id}" if job_id else ""
        return RawListing(company=company, title=title, url=url,
                          location=location, term=term, native_id=job_id).clean()
