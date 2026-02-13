"""
Compatibility module for the PyPI distribution name.

The PyPI package is named `secfetcher`, while the primary Python module is `secfetch`.
This compatibility module intentionally exposes only tar quarter download:

    from secfetcher import download_quarter_tar
"""

from secfetch import download_quarter_tar

__all__ = [
    "download_quarter_tar",
]
