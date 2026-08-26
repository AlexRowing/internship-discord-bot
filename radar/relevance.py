"""Decide whether a listing is worth pinging about (software / AI / data roles,
matching term filter). Config-driven so you can tune it in .env."""
from __future__ import annotations

from .config import config
from .models import RawListing


def is_relevant(raw: RawListing) -> bool:
    haystack = f"{raw.title} {raw.category}".lower()

    keywords = config.relevance_keywords
    if keywords and not any(k in haystack for k in keywords):
        return False

    terms = config.term_filter
    if terms and raw.term:
        term_l = raw.term.lower()
        if not any(t in term_l for t in terms):
            return False

    return True
