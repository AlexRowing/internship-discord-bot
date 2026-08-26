"""Source registry — maps a URL to the scraper that should handle it."""
from __future__ import annotations

from .base import Source
from .simplify import SimplifySource
from .generic import GenericHtmlSource
from .playwright_source import PlaywrightSource

# Order matters: most specific first, generic fallback last.
_REGISTRY: list[type[Source]] = [
    SimplifySource,
    PlaywrightSource,
    GenericHtmlSource,
]


def pick_source(url: str, name: str = "") -> Source:
    """Return an instantiated Source for the URL."""
    for cls in _REGISTRY:
        if cls.handles(url):
            return cls(url, name)
    return GenericHtmlSource(url, name)


def source_for_kind(kind: str, url: str, name: str = "") -> Source:
    """Rebuild a Source from a DB row's stored `kind`."""
    for cls in _REGISTRY:
        if cls.kind == kind:
            return cls(url, name)
    return pick_source(url, name)


__all__ = ["Source", "pick_source", "source_for_kind",
           "SimplifySource", "GenericHtmlSource", "PlaywrightSource"]
