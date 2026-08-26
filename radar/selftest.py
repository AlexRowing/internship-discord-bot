"""Scraper smoke-test — verify a site can be read WITHOUT needing Discord.

Usage:
    python -m radar.selftest                 # tests the SimplifyJobs feed
    python -m radar.selftest simplify        # same
    python -m radar.selftest <any-url>       # tests /watch handling for that URL
"""
from __future__ import annotations

import sys

from .sources import pick_source, SimplifySource
from .relevance import is_relevant


def main(argv: list[str]) -> int:
    from ._console import setup_console
    setup_console()
    arg = argv[1] if len(argv) > 1 else "simplify"

    if arg == "simplify":
        src = SimplifySource(SimplifySource.__module__)  # url ignored; uses default feed
        src.url = "https://github.com/SimplifyJobs/Summer2027-Internships"
        src.name = "SimplifyJobs Summer 2027"
    else:
        src = pick_source(arg)

    print(f"Source   : {src.name}")
    print(f"Scraper  : {src.kind}")
    print(f"URL      : {src.url}")
    print("Fetching…\n")

    try:
        raws = src.fetch()
    except Exception as e:  # noqa: BLE001
        print(f"FAILED: {type(e).__name__}: {e}")
        return 1

    relevant = [r for r in raws if is_relevant(r)]
    print(f"Total listings found : {len(raws)}")
    print(f"Relevant (SWE/AI/…)  : {len(relevant)}\n")

    for r in relevant[:8]:
        loc = f"  [{r.location}]" if r.location else ""
        term = f"  ({r.term})" if r.term else ""
        print(f"  • {r.title} @ {r.company or '—'}{loc}{term}")
    if len(relevant) > 8:
        print(f"  … and {len(relevant) - 8} more")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
