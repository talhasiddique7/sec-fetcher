from __future__ import annotations

import ast
import csv
from pathlib import Path
from typing import Dict, Optional, Sequence, Set


def _normalize_cik(value: str | int) -> str:
    s = str(value).strip()
    if not s:
        return ""
    if s.isdigit():
        return str(int(s)).zfill(10)
    return s.zfill(10)


def _load_packaged_listed_filers() -> list[dict[str, str]]:
    from importlib.resources import files

    path = files("secfetch.resources") / "listed_filer_metadata.csv"
    rows: list[dict[str, str]] = []
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows


def load_ticker_to_cik_map() -> Dict[str, Set[str]]:
    out: Dict[str, Set[str]] = {}
    for row in _load_packaged_listed_filers():
        cik = _normalize_cik(row.get("cik", ""))
        if not cik:
            continue
        raw = row.get("tickers", "")
        tickers: list[str] = []
        try:
            parsed = ast.literal_eval(raw) if raw else []
            if isinstance(parsed, list):
                tickers = [str(x).strip().upper() for x in parsed if str(x).strip()]
        except Exception:
            tickers = []
        for t in tickers:
            out.setdefault(t, set()).add(cik)
    return out


def resolve_cik_filter(
    *,
    cik: Optional[str | int | Sequence[str | int]] = None,
    ticker: Optional[str | Sequence[str]] = None,
) -> Optional[Set[str]]:
    values: set[str] = set()
    if cik is not None:
        cik_values = [cik] if isinstance(cik, (str, int)) else list(cik)
        for v in cik_values:
            norm = _normalize_cik(v)
            if norm:
                values.add(norm)

    if ticker is not None:
        ticker_values = [ticker] if isinstance(ticker, str) else list(ticker)
        mapping = load_ticker_to_cik_map()
        for t in ticker_values:
            key = str(t).strip().upper()
            if not key:
                continue
            values.update(mapping.get(key, set()))

    return values or None


def resolve_output_group_label(
    *,
    cik: Optional[str | int | Sequence[str | int]] = None,
    ticker: Optional[str | Sequence[str]] = None,
) -> Optional[str]:
    if ticker is not None:
        tickers = [ticker] if isinstance(ticker, str) else list(ticker)
        cleaned = [str(t).strip().upper() for t in tickers if str(t).strip()]
        if len(cleaned) == 1:
            return cleaned[0]
    if cik is not None:
        ciks = [cik] if isinstance(cik, (str, int)) else list(cik)
        cleaned = [_normalize_cik(v) for v in ciks if str(v).strip()]
        if len(cleaned) == 1:
            return cleaned[0]
    return None
