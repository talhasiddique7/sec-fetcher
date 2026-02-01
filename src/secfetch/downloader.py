from __future__ import annotations

import asyncio
import shutil
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import List, Optional, Sequence

from secfetch.edgar import filing_index_json_url, filing_folder_url
from secfetch.exceptions import SecFetchError
from secfetch.forms import load_accepted_form_types, validate_forms
from secfetch.index.filter import FilingFilter, filter_master_rows
from secfetch.index.master import (
    MasterIndexRow,
    download_master_index,
    load_master_index,
)
from secfetch.network.client import SecClient
from secfetch.storage.layout import filing_dir
from secfetch.storage.manifest import Manifest, ManifestEntry


class DownloadError(SecFetchError):
    pass


@dataclass(frozen=True)
class DownloadResult:
    accession: str
    cik: str
    form_type: str
    date_filed: date
    status: str  # downloaded | skipped | error
    error: Optional[str] = None
    output_dir: Optional[str] = None


def _normalize_file_types(file_types: Sequence[str]) -> List[str]:
    out: List[str] = []
    for t in file_types:
        tt = t.strip().lower()
        if not tt:
            continue
        if not tt.startswith("."):
            tt = "." + tt
        out.append(tt)
    if not out:
        raise ValueError("file_types must be non-empty (e.g. ['.xml', '.htm', '.html'])")
    return sorted(set(out))


def _default_manifest_path(data_dir: Path) -> Path:
    # keep clean: state under data/_state/
    return data_dir / "_state" / "manifest.json"


class FilingDownloader:
    """
    Index-driven downloader:
      - downloads master.idx for a quarter
      - filters by form types
      - for each accession: uses EDGAR folder `index.json` to list files
      - downloads only requested file types
      - writes a manifest for de-dup/resume
    """

    def __init__(
        self,
        *,
        forms: Sequence[str],
        data_dir: str | Path = "data",
        file_types: Sequence[str] = (".htm", ".html", ".xml", ".xbrl", ".pdf"),
        include_amended: bool = False,
        concurrency: int = 6,
        user_agent: Optional[str] = None,
        manifest_path: Optional[str | Path] = None,
    ) -> None:
        self.data_dir = Path(data_dir)
        self.file_types = _normalize_file_types(file_types)
        self.include_amended = include_amended
        self.concurrency = max(1, int(concurrency))

        accepted = load_accepted_form_types(data_dir=self.data_dir)
        self.forms = validate_forms(forms=forms, accepted=accepted)

        self._client = SecClient.from_env(user_agent=user_agent)
        self._manifest = Manifest(Path(manifest_path) if manifest_path else _default_manifest_path(self.data_dir))
        self._manifest.load()

    async def aclose(self) -> None:
        await self._client.aclose()

    async def download_quarter(self, *, year: int, quarter: int) -> List[DownloadResult]:
        # Always fetch master index first (source of truth)
        master_path = await download_master_index(self._client, data_dir=self.data_dir, year=year, quarter=quarter)
        rows = load_master_index(master_path)

        flt = FilingFilter(forms=self.forms, include_amended=self.include_amended)
        matched = filter_master_rows(rows, flt)

        sem = asyncio.Semaphore(self.concurrency)
        tasks = [self._download_one(row=row, sem=sem) for row in matched]
        results = await asyncio.gather(*tasks)
        self._manifest.save_atomic()

        # If the whole quarter completed without errors, remove cached index data for that quarter.
        # (User requested: delete index data after all files download for a quarter.)
        if all(r.status != "error" for r in results):
            try:
                if master_path.parent.exists():
                    shutil.rmtree(master_path.parent)
            except Exception:
                # Best-effort cleanup; do not fail downloads due to cleanup.
                pass
        return results

    async def download_year(self, *, year: int, quarters: Sequence[int] = (1, 2, 3, 4)) -> List[DownloadResult]:
        out: List[DownloadResult] = []
        for q in quarters:
            out.extend(await self.download_quarter(year=year, quarter=int(q)))
        return out

    async def _download_one(self, *, row: MasterIndexRow, sem: asyncio.Semaphore) -> DownloadResult:
        accession = row.accession
        if self._manifest.has(accession):
            return DownloadResult(
                accession=accession,
                cik=row.cik,
                form_type=row.form_type,
                date_filed=row.date_filed,
                status="skipped",
            )

        out_dir = filing_dir(
            data_dir=self.data_dir,
            form_type=row.form_type,
            cik=row.cik,
            accession=accession,
        )

        async with sem:
            tmp_dir = out_dir.with_name(out_dir.name + ".tmp")
            try:
                if tmp_dir.exists():
                    shutil.rmtree(tmp_dir)
                tmp_dir.mkdir(parents=True, exist_ok=True)

                index_url = filing_index_json_url(cik=row.cik, accession=accession)
                listing = await self._client.get_json(index_url)
                files = _extract_files_from_index_json(listing, base_folder_url=filing_folder_url(cik=row.cik, accession=accession))

                selected = [f for f in files if _match_file_types(f["name"], self.file_types)]
                if not selected:
                    raise DownloadError(
                        f"No files matched file_types={self.file_types} for accession {accession}"
                    )

                for f in selected:
                    content = await self._client.get_bytes(f["href"])
                    (tmp_dir / f["name"]).write_bytes(content)

                # Commit atomically-ish: replace whole folder only after success.
                out_dir.parent.mkdir(parents=True, exist_ok=True)
                if out_dir.exists():
                    shutil.rmtree(out_dir)
                tmp_dir.replace(out_dir)

                self._manifest.upsert(
                    ManifestEntry(
                        accession=accession,
                        form_type=row.form_type,
                        cik=row.cik.zfill(10),
                        date_filed=row.date_filed.isoformat(),
                        strategy="index",
                    )
                )

                return DownloadResult(
                    accession=accession,
                    cik=row.cik,
                    form_type=row.form_type,
                    date_filed=row.date_filed,
                    status="downloaded",
                    output_dir=str(out_dir),
                )
            except Exception as e:
                # Cleanup partials
                try:
                    if tmp_dir.exists():
                        shutil.rmtree(tmp_dir)
                except Exception:
                    pass
                return DownloadResult(
                    accession=accession,
                    cik=row.cik,
                    form_type=row.form_type,
                    date_filed=row.date_filed,
                    status="error",
                    error=str(e),
                )


def _match_file_types(name: str, file_types: Sequence[str]) -> bool:
    n = name.lower()
    return any(n.endswith(ext) for ext in file_types)


def _extract_files_from_index_json(payload: object, *, base_folder_url: str) -> List[dict]:
    """
    Parse SEC folder index.json response and return:
    [{ "name": "...", "href": "https://..." }, ...]
    """
    if not isinstance(payload, dict):
        raise DownloadError("index.json payload was not an object")

    directory = payload.get("directory")
    if not isinstance(directory, dict):
        raise DownloadError("index.json missing 'directory' object")

    items = directory.get("item")
    if not isinstance(items, list):
        raise DownloadError("index.json missing 'directory.item' array")

    out: List[dict] = []
    for it in items:
        if not isinstance(it, dict):
            continue
        name = it.get("name")
        if not isinstance(name, str) or not name:
            continue
        out.append({"name": name, "href": base_folder_url + name})
    return out

