"""
Compatibility module for the PyPI distribution name.

The PyPI package is named `secfetcher`, while the primary Python module is `secfetch`.
Importing from either works:

    from secfetch import download_year
    from secfetcher import download_year
"""

from secfetch import FilingDownloader, download_quarter, download_year

__all__ = [
    "FilingDownloader",
    "download_quarter",
    "download_year",
]

