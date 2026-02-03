#!/usr/bin/env python3
"""Run Q1 download for a recent year (uses progress callback from CLI)."""
import sys

# Unbuffered stderr so progress line updates (\r) show immediately
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(write_through=True)
    except Exception:
        pass

from secfetch import download_quarter
from secfetch.cli import _progress_callback

if __name__ == "__main__":
    sys.stderr.write("Starting Q1 2024 download...\n")
    sys.stderr.flush()

    # Q1 2024, one form to keep test small
    # User-agent from SEC_USER_AGENT env, or email.json (sec-fetcher <email>), or pass user_agent=
    results = download_quarter(
        year=2024,
        quarter=1,
        forms=["10-Q"],
        data_dir="data",
        on_progress=_progress_callback,
    )
    print(f"Done: {len(results)} filings")
