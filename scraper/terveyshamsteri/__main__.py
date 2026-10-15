"""Command line entry point.

  python -m terveyshamsteri regions                 # JSON list of enabled region ids (CI matrix)
  python -m terveyshamsteri scrape pirkanmaa --data ../data [--max-meetings 5]
  python -m terveyshamsteri index --data ../data     # write regions.json + status.json
  python -m terveyshamsteri reextract --data ../data # re-derive decisions and votes of stored meetings
  python -m terveyshamsteri elections --data ../data [--region kainuu] [--refresh]
  python -m terveyshamsteri finances --data ../data [--region kainuu]
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from .config import load_regions
from .elections import fetch_elections
from .finances import fetch_finances, fetch_population
from .index import build_index
from .run import reextract_votes, scrape_region


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="terveyshamsteri")
    ap.add_argument("--regions-dir", type=Path, default=Path(__file__).resolve().parents[2] / "regions")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("regions", help="print enabled region ids as JSON")

    sc = sub.add_parser("scrape", help="scrape one region")
    sc.add_argument("region")
    sc.add_argument("--data", type=Path, required=True)
    sc.add_argument("--since")
    sc.add_argument("--max-meetings", type=int)
    sc.add_argument("--max-minutes", type=float)
    sc.add_argument("--refresh", action="store_true", help="refetch every meeting")
    sc.add_argument("--delay", type=float, default=1.0, help="seconds between requests per host")

    ix = sub.add_parser("index", help="write regions.json and status.json")
    ix.add_argument("--data", type=Path, required=True)

    rx = sub.add_parser("reextract", help="re-derive decisions and votes of stored meetings")
    rx.add_argument("--data", type=Path, required=True)

    el = sub.add_parser("elections", help="fetch 2025 regional election results")
    el.add_argument("--data", type=Path, required=True)
    el.add_argument("--region", action="append", help="only these regions (repeatable)")
    el.add_argument("--refresh", action="store_true", help="refetch counties already on disk")

    fi = sub.add_parser("finances", help="fetch county finances from the State Treasury")
    fi.add_argument("--data", type=Path, required=True)
    fi.add_argument("--region", action="append", help="only these regions (repeatable)")

    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    regions = load_regions(args.regions_dir)

    if args.cmd == "regions":
        print(json.dumps([r["id"] for r in regions.values() if r.get("enabled")]))
        return 0
    if args.cmd == "scrape":
        status = scrape_region(regions[args.region], args.data, since=args.since,
                               max_meetings=args.max_meetings, max_minutes=args.max_minutes,
                               refresh=args.refresh, delay=args.delay)
        print(json.dumps(status, ensure_ascii=False, indent=1))
        return 0 if status["result"] in ("ok", "partial", "blocked", "not-implemented") else 1
    if args.cmd == "reextract":
        print(json.dumps(reextract_votes(args.data, regions)))
        return 0
    if args.cmd == "elections":
        results = fetch_elections(args.data, regions=args.region, refresh=args.refresh)
        print(json.dumps(results, ensure_ascii=False, indent=1))
        return 0 if any(not v.startswith("error") for v in results.values()) else 1
    if args.cmd == "finances":
        results = fetch_finances(args.data, regions=args.region)
        try:
            pop = fetch_population(args.data)
            results["population"] = f"ok ({len(pop['regions'])} counties)"
        except Exception as e:  # noqa: BLE001 - population is optional context
            logging.exception("population failed")
            results["population"] = f"error: {e!r}"
        print(json.dumps(results, ensure_ascii=False, indent=1))
        return 0 if any(not v.startswith("error") for v in results.values()) else 1
    if args.cmd == "index":
        build_index(regions, args.data)
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
