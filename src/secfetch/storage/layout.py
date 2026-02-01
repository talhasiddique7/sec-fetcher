from __future__ import annotations

import re
from pathlib import Path


def form_dir_name(form_type: str) -> str:
    """
    Convert a form type into a safe directory name.
    Example: "10-Q/A" -> "10-Q_A"
    """
    s = form_type.strip()
    s = s.replace("/", "_")
    s = re.sub(r"\s+", "", s)
    return s


def filings_root(data_dir: Path) -> Path:
    return data_dir / "filings"


def filing_dir(*, data_dir: Path, form_type: str, cik: str, accession: str) -> Path:
    return filings_root(data_dir) / form_dir_name(form_type) / cik.zfill(10) / accession

