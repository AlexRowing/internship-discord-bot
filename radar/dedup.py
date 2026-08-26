"""Turning a raw listing into a stable fingerprint for global de-duplication.

This is deliberately a single, well-isolated function so that a smarter matcher
(e.g. an LLM that knows "SWE Intern" == "Software Engineer Intern - Summer 2027")
can be dropped in later without touching the rest of the bot. That's the V3 upgrade.
"""
from __future__ import annotations

import re

from .models import RawListing

_COMPANY_NOISE = re.compile(
    r"\b(inc|inc\.|llc|ltd|corp|corporation|co|company|technologies|technology|"
    r"labs|the|group|systems|solutions|global)\b",
    re.IGNORECASE,
)

# Words that describe the *kind* of role but not its identity — stripped from titles.
_TITLE_NOISE = re.compile(
    r"\b(summer|fall|spring|winter|20\d{2}|intern|internship|co-?op|program|"
    r"student|early career|new grad|full[\s-]?time|part[\s-]?time|remote|hybrid|"
    r"onsite|us|usa|u\.s\.)\b",
    re.IGNORECASE,
)

_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def _slug(text: str) -> str:
    text = text.lower()
    text = _NON_ALNUM.sub(" ", text)
    return " ".join(text.split())


def norm_company(company: str) -> str:
    c = _COMPANY_NOISE.sub(" ", company or "")
    return _slug(c)


def norm_title(title: str) -> str:
    t = _TITLE_NOISE.sub(" ", title or "")
    t = _slug(t)
    # Common abbreviation folding so "SWE" and "software engineer" collide.
    t = re.sub(r"\bswe\b", "software engineer", t)
    t = re.sub(r"\bml\b", "machine learning", t)
    t = re.sub(r"\bai\b", "artificial intelligence", t)
    return t.strip()


def fingerprint(raw: RawListing) -> str:
    """A deterministic key. Same company + same core role => same fingerprint."""
    company = norm_company(raw.company)
    title = norm_title(raw.title)
    if not company and not title:
        # Fall back to the URL so we never produce an empty key.
        return "url:" + _slug(raw.url)
    return f"{company}::{title}"
