from __future__ import annotations

import argparse
import json

from secfetch import download_quarter, download_year


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="secfetch")
    sub = p.add_subparsers(dest="cmd", required=True)

    q = sub.add_parser("quarter", help="Download filings for a quarter")
    q.add_argument("--year", type=int, required=True)
    q.add_argument("--quarter", type=int, required=True, choices=[1, 2, 3, 4])
    q.add_argument("--forms", nargs="+", required=True)
    q.add_argument("--data-dir", default="data")
    q.add_argument("--file-types", nargs="+", default=[".htm", ".html", ".xml", ".xbrl", ".pdf"])
    q.add_argument("--include-amended", action="store_true")
    q.add_argument("--concurrency", type=int, default=6)
    q.add_argument("--user-agent", default=None)

    y = sub.add_parser("year", help="Download filings for a year (all quarters)")
    y.add_argument("--year", type=int, required=True)
    y.add_argument("--forms", nargs="+", required=True)
    y.add_argument("--data-dir", default="data")
    y.add_argument("--file-types", nargs="+", default=[".htm", ".html", ".xml", ".xbrl", ".pdf"])
    y.add_argument("--include-amended", action="store_true")
    y.add_argument("--concurrency", type=int, default=6)
    y.add_argument("--user-agent", default=None)

    args = p.parse_args(argv)

    if args.cmd == "quarter":
        res = download_quarter(
            year=args.year,
            quarter=args.quarter,
            forms=args.forms,
            data_dir=args.data_dir,
            file_types=args.file_types,
            include_amended=args.include_amended,
            concurrency=args.concurrency,
            user_agent=args.user_agent,
        )
    else:
        res = download_year(
            year=args.year,
            forms=args.forms,
            data_dir=args.data_dir,
            file_types=args.file_types,
            include_amended=args.include_amended,
            concurrency=args.concurrency,
            user_agent=args.user_agent,
        )

    print(json.dumps([r.__dict__ for r in res], indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

