from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Iterable, List

from secfetch.exceptions import MasterIndexParseError
from secfetch.network.client import SecClient


@dataclass(frozen=True)
class MasterIndexRow:
    cik: str
    company_name: str
    form_type: str
    date_filed: date
    filename: str  # edgar path under /Archives/

    @property
    def accession(self) -> str:
        # filename is typically: edgar/data/{cik}/{accession_no_dash}/{accession}.txt
        name = Path(self.filename).name
        return name.removesuffix(".txt").removesuffix(".idx")

    @property
    def accession_no_dash(self) -> str:
        return self.accession.replace("-", "")


def master_index_url(*, year: int, quarter: int) -> str:
    return f"https://www.sec.gov/Archives/edgar/full-index/{year}/QTR{quarter}/master.idx"


def master_index_cache_path(*, data_dir: Path, year: int, quarter: int) -> Path:
    return data_dir / "index" / "master" / str(year) / f"QTR{quarter}" / "master.idx"


async def download_master_index(
    client: SecClient,
    *,
    data_dir: Path,
    year: int,
    quarter: int,
    force: bool = False,
) -> Path:
    """
    Download and cache master.idx for a given year/quarter.
    Returns the path to the cached file.
    """
    cache_path = master_index_cache_path(data_dir=data_dir, year=year, quarter=quarter)
    if cache_path.exists() and not force:
        return cache_path

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    content = await client.get_bytes(master_index_url(year=year, quarter=quarter))
    cache_path.write_bytes(content)
    return cache_path


def parse_master_index(lines: Iterable[str]) -> List[MasterIndexRow]:
    """
    Parse SEC master.idx into structured rows.
    """
    saw_header = False
    in_data = False
    rows: List[MasterIndexRow] = []

    for raw in lines:
        line = raw.rstrip("\n")
        if not in_data:
            if line.startswith("CIK|Company Name|Form Type|Date Filed|Filename"):
                saw_header = True
                continue
            # Data starts after the delimiter line of dashes that follows the header.
            if saw_header and line.strip().startswith("----"):
                in_data = True
            continue

        if not line.strip():
            continue

        parts = line.split("|")
        if len(parts) != 5:
            raise MasterIndexParseError(f"Unexpected master.idx row format: {line!r}")

        cik, company_name, form_type, date_filed_str, filename = parts
        try:
            yyyy, mm, dd = (int(x) for x in date_filed_str.split("-"))
            dt = date(yyyy, mm, dd)
        except Exception as e:
            raise MasterIndexParseError(
                f"Invalid date in master.idx row: {date_filed_str!r}"
            ) from e

        rows.append(
            MasterIndexRow(
                cik=cik.strip(),
                company_name=company_name.strip(),
                form_type=form_type.strip(),
                date_filed=dt,
                filename=filename.strip(),
            )
        )

    if not rows:
        raise MasterIndexParseError("No rows parsed from master.idx (header not found?)")
    return rows


def load_master_index(path: Path) -> List[MasterIndexRow]:
    text = path.read_text(errors="replace")
    return parse_master_index(text.splitlines())


def iter_unique_accessions(rows: Iterable[MasterIndexRow]) -> Iterable[MasterIndexRow]:
    seen: set[str] = set()
    for row in rows:
        if row.accession in seen:
            continue
        seen.add(row.accession)
        yield row

