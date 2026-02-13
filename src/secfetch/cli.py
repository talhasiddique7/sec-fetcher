from __future__ import annotations

import argparse
import json
import sys

from secfetch import download_quarter, download_year
from secfetch.downloader import DownloadResult

# Spinner chars for loading style (cycle per completion)
SPINNER = "|/-\\"

# ANSI colors for progress (no-op if not a TTY)
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
MAGENTA = "\033[35m"
BOLD = "\033[1m"
RESET = "\033[0m"


def _progress_callback(
    current: int, total: int, result: DownloadResult | None, in_progress: int = 0
) -> None:
    if total == 0:
        return
    spin = "..." if result is None else SPINNER[(current - 1) % len(SPINNER)]
    # Colourful: label in cyan, count in green, spinner in yellow, in_progress in magenta
    in_progress_part = f" {MAGENTA}({in_progress} downloading){RESET}" if in_progress else ""
    msg = f"\r  {CYAN}{BOLD}Processing{RESET} {GREEN}{current}/{total}{RESET} {YELLOW}{spin}{RESET}{in_progress_part}  "
    sys.stderr.write(msg)
    sys.stderr.flush()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="secfetch")
    sub = p.add_subparsers(dest="cmd", required=True)

    q = sub.add_parser("quarter", help="Download filings for a quarter")
    q.add_argument("--year", type=int, required=True)
    q.add_argument("--quarter", type=int, required=True, choices=[1, 2, 3, 4])
    q.add_argument("--forms", nargs="+", required=True)
    q.add_argument("--cik", nargs="+", default=None)
    q.add_argument("--ticker", nargs="+", default=None)
    q.add_argument("--data-dir", default="data")
    q.add_argument("--file-types", nargs="+", default=[".htm", ".html", ".xml", ".xbrl", ".pdf"])
    q.add_argument("--include-amended", action="store_true")
    q.add_argument("--concurrency", type=int, default=6)
    q.add_argument("--user-agent", default=None)

    y = sub.add_parser("year", help="Download filings for a year (all quarters)")
    y.add_argument("--year", type=int, required=True)
    y.add_argument("--forms", nargs="+", required=True)
    y.add_argument("--cik", nargs="+", default=None)
    y.add_argument("--ticker", nargs="+", default=None)
    y.add_argument("--data-dir", default="data")
    y.add_argument("--file-types", nargs="+", default=[".htm", ".html", ".xml", ".xbrl", ".pdf"])
    y.add_argument("--include-amended", action="store_true")
    y.add_argument("--concurrency", type=int, default=6)
    y.add_argument("--user-agent", default=None)

    args = p.parse_args(argv)

    try:
        if args.cmd == "quarter":
            res = download_quarter(
                year=args.year,
                quarter=args.quarter,
                forms=args.forms,
                cik=args.cik,
                ticker=args.ticker,
                data_dir=args.data_dir,
                file_types=args.file_types,
                include_amended=args.include_amended,
                concurrency=args.concurrency,
                user_agent=args.user_agent,
                on_progress=_progress_callback,
            )
        else:
            res = download_year(
                year=args.year,
                forms=args.forms,
                cik=args.cik,
                ticker=args.ticker,
                data_dir=args.data_dir,
                file_types=args.file_types,
                include_amended=args.include_amended,
                concurrency=args.concurrency,
                user_agent=args.user_agent,
                on_progress=_progress_callback,
            )
    finally:
        # Clear progress line so JSON output starts clean
        sys.stderr.write("\r" + " " * 60 + "\r")
        sys.stderr.flush()

    print(json.dumps([r.__dict__ for r in res], indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
