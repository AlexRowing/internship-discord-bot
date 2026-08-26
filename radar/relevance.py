"""Decide whether a listing is worth pinging about (software / AI / data roles,
matching term filter). Config-driven so you can tune it in .env.

Keywords match on WORD BOUNDARIES, so short ones like "ai"/"ml" don't
false-positive inside words ("trainer", "sustainability", "html")."""
from __future__ import annotations

import re

from .config import config
from .models import RawListing


def _build(keywords: tuple[str, ...]) -> re.Pattern | None:
    if not keywords:
        return None
    parts = [re.escape(k) for k in keywords]
    return re.compile(r"\b(?:" + "|".join(parts) + r")\b", re.IGNORECASE)


_KW_RE = _build(config.relevance_keywords)


def is_relevant(raw: RawListing) -> bool:
    haystack = f"{raw.title} {raw.category}"

    if _KW_RE is not None and not _KW_RE.search(haystack):
        return False

    terms = config.term_filter
    if terms and raw.term:
        term_l = raw.term.lower()
        if not any(t in term_l for t in terms):
            return False

    return True
