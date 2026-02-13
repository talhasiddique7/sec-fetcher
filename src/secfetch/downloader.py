from __future__ import annotations

import asyncio
import io
import json
import shutil
import tarfile
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Callable, List, Optional, Sequence

from secfetch.entities import resolve_cik_filter, resolve_output_group_label
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


def _filing_tar_path(*, data_dir: Path, form_type: str, cik: str, accession: str) -> Path:
    return data_dir / "filings_tar" / form_type / cik.zfill(10) / f"{accession}.tar"


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
        cik: Optional[str | int | Sequence[str | int]] = None,
        ticker: Optional[str | Sequence[str]] = None,
        concurrency: int = 6,
        user_agent: Optional[str] = None,
        manifest_path: Optional[str | Path] = None,
        output_format: str = "files",
        on_progress: Optional[Callable[[int, int, Optional["DownloadResult"], int], None]] = None,
    ) -> None:
        self.data_dir = Path(data_dir)
        self.file_types = _normalize_file_types(file_types)
        self.include_amended = include_amended
        self.cik_set = resolve_cik_filter(cik=cik, ticker=ticker)
        self.output_group_label = resolve_output_group_label(cik=cik, ticker=ticker)
        self.concurrency = max(1, int(concurrency))
        self._on_progress = on_progress
        if output_format not in ("files", "tar"):
            raise ValueError("output_format must be 'files' or 'tar'")
        self.output_format = output_format

        accepted = load_accepted_form_types(data_dir=self.data_dir)
        self.forms = validate_forms(forms=forms, accepted=accepted)

        self._client = SecClient.from_env(user_agent=user_agent, data_dir=self.data_dir)
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
        if self.cik_set is not None:
            matched = [r for r in matched if r.cik.zfill(10) in self.cik_set]
        total = len(matched)

        if self._on_progress is not None and total > 0:
            self._on_progress(0, total, None, 0)

        sem = asyncio.Semaphore(self.concurrency)
        completed = 0
        in_progress = 0
        progress_lock = asyncio.Lock()

        async def with_progress(row: MasterIndexRow):
            nonlocal completed, in_progress
            async with sem:
                async with progress_lock:
                    in_progress += 1
                    if self._on_progress is not None:
                        self._on_progress(completed, total, None, in_progress)
                try:
                    result = await self._download_one(row=row)
                finally:
                    async with progress_lock:
                        in_progress -= 1
                        completed += 1
                        if self._on_progress is not None:
                            self._on_progress(completed, total, result, in_progress)
            return result

        tasks = [with_progress(row) for row in matched]
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

    async def _download_one(self, *, row: MasterIndexRow) -> DownloadResult:
        accession = row.accession
        out_dir = filing_dir(
            data_dir=self.data_dir,
            form_type=row.form_type,
            cik=row.cik,
            accession=accession,
            group_label=self.output_group_label,
        )
        tar_path = _filing_tar_path(
            data_dir=self.data_dir,
            form_type=row.form_type,
            cik=row.cik,
            accession=accession,
        )
        entry = self._manifest.get(accession)
        if entry is not None:
            if self.output_format == "files":
                if entry.strategy == "index" and out_dir.exists():
                    return DownloadResult(
                        accession=accession,
                        cik=row.cik,
                        form_type=row.form_type,
                        date_filed=row.date_filed,
                        status="skipped",
                    )
            else:
                if entry.strategy == "index_tar" and tar_path.exists():
                    return DownloadResult(
                        accession=accession,
                        cik=row.cik,
                        form_type=row.form_type,
                        date_filed=row.date_filed,
                        status="skipped",
                        output_dir=str(tar_path),
                    )

        tmp_dir = out_dir.with_name(out_dir.name + ".tmp")
        tmp_tar = tar_path.with_suffix(".tmp")
        try:
            if tmp_dir.exists():
                shutil.rmtree(tmp_dir)
            if tmp_tar.exists():
                tmp_tar.unlink()
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

            if self.output_format == "files":
                # Commit atomically-ish: replace whole folder only after success.
                out_dir.parent.mkdir(parents=True, exist_ok=True)
                if out_dir.exists():
                    shutil.rmtree(out_dir)
                tmp_dir.replace(out_dir)
                output_path = str(out_dir)
                strategy = "index"
            else:
                tmp_tar.parent.mkdir(parents=True, exist_ok=True)
                with tarfile.open(tmp_tar, mode="w") as tf:
                    metadata = {
                        "accession": accession,
                        "cik": row.cik.zfill(10),
                        "form_type": row.form_type,
                        "date_filed": row.date_filed.isoformat(),
                        "files": [f["name"] for f in selected],
                    }
                    metadata_bytes = json.dumps(metadata).encode("utf-8")
                    meta_info = tarfile.TarInfo(name="metadata.json")
                    meta_info.size = len(metadata_bytes)
                    tf.addfile(meta_info, io.BytesIO(metadata_bytes))
                    for f in selected:
                        content = (tmp_dir / f["name"]).read_bytes()
                        info = tarfile.TarInfo(name=f["name"])
                        info.size = len(content)
                        tf.addfile(info, io.BytesIO(content))

                if tar_path.exists():
                    tar_path.unlink()
                tmp_tar.replace(tar_path)
                shutil.rmtree(tmp_dir)
                output_path = str(tar_path)
                strategy = "index_tar"

            self._manifest.upsert(
                ManifestEntry(
                    accession=accession,
                    form_type=row.form_type,
                    cik=row.cik.zfill(10),
                    date_filed=row.date_filed.isoformat(),
                    strategy=strategy,
                )
            )

            return DownloadResult(
                accession=accession,
                cik=row.cik,
                form_type=row.form_type,
                date_filed=row.date_filed,
                status="downloaded",
                output_dir=output_path,
            )
        except Exception as e:
            # Cleanup partials
            try:
                if tmp_dir.exists():
                    shutil.rmtree(tmp_dir)
                if tmp_tar.exists():
                    tmp_tar.unlink()
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
