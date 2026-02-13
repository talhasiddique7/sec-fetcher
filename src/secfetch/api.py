from __future__ import annotations

import asyncio
import os
import sys
import tarfile
import shutil
from datetime import date
from pathlib import Path
from typing import Callable, List, Optional, Sequence

import httpx

from secfetch.downloader import DownloadResult, FilingDownloader
from secfetch.entities import resolve_cik_filter, resolve_output_group_label
from secfetch.forms import load_accepted_form_types, validate_forms
from secfetch.index.filter import FilingFilter, filter_master_rows
from secfetch.index.master import MasterIndexRow, download_master_index, load_master_index
from secfetch.network.client import SecClient
from secfetch.storage.layout import filing_dir


def _progress_bar(stage: str, current: int, total: int, extra: str = "") -> None:
    total = max(total, 1)
    current = max(0, min(current, total))
    width = 30
    filled = int(width * current / total)
    bar = "=" * filled + "." * (width - filled)
    cyan = "\033[36m"
    magenta = "\033[35m"
    reset = "\033[0m"
    extra_part = f" {extra}" if extra else ""
    sys.stderr.write(f"\r{magenta}: {stage}{reset} [{cyan}{bar}{reset}] {current}/{total}{extra_part}")
    if current >= total:
        sys.stderr.write("\n")
    sys.stderr.flush()


def _step_done(text: str) -> None:
    green = "\033[32m"
    reset = "\033[0m"
    sys.stderr.write(f"{green}[ok]{reset} {text}\n")
    sys.stderr.flush()


def _step_info(text: str) -> None:
    cyan = "\033[36m"
    reset = "\033[0m"
    sys.stderr.write(f"{cyan}[start]{reset} {text}\n")
    sys.stderr.flush()


def _render_filter_label(
    *,
    forms: Sequence[str],
    cik: Optional[str | int | Sequence[str | int]],
    ticker: Optional[str | Sequence[str]],
) -> str:
    form_text = ",".join(forms)
    if ticker is not None:
        vals = [ticker] if isinstance(ticker, str) else list(ticker)
        clean = [str(v).strip().upper() for v in vals if str(v).strip()]
        if clean:
            return f"forms={form_text} ticker={','.join(clean)}"
    if cik is not None:
        vals = [cik] if isinstance(cik, (str, int)) else list(cik)
        clean = [str(v).strip() for v in vals if str(v).strip()]
        if clean:
            return f"forms={form_text} cik={','.join(clean)}"
    return f"forms={form_text}"


def _default_progress_callback(current: int, total: int, result: Optional[DownloadResult], in_progress: int = 0) -> None:
    if total == 0:
        return
    _progress_bar("downloading filings", current, total, "")


async def _run_with_downloader(
    *,
    runner,
    forms: Sequence[str],
    data_dir: str | Path,
    file_types: Sequence[str],
    include_amended: bool,
    cik: Optional[str | int | Sequence[str | int]],
    ticker: Optional[str | Sequence[str]],
    concurrency: int,
    user_agent: Optional[str],
    manifest_path: Optional[str | Path],
    output_format: str = "files",
    on_progress: Optional[Callable[[int, int, Optional[DownloadResult], int], None]] = None,
) -> List[DownloadResult]:
    dl = FilingDownloader(
        forms=forms,
        data_dir=data_dir,
        file_types=file_types,
        include_amended=include_amended,
        cik=cik,
        ticker=ticker,
        concurrency=concurrency,
        user_agent=user_agent,
        manifest_path=manifest_path,
        output_format=output_format,
        on_progress=on_progress,
    )
    try:
        return await runner(dl)
    finally:
        await dl.aclose()


async def _collect_matched_rows_for_quarter(
    *,
    year: int,
    quarter: int,
    forms: Sequence[str],
    data_dir: Path,
    include_amended: bool,
    cik: Optional[str | int | Sequence[str | int]],
    ticker: Optional[str | Sequence[str]],
    user_agent: Optional[str],
) -> tuple[List[MasterIndexRow], Path]:
    accepted = load_accepted_form_types(data_dir=data_dir)
    valid_forms = validate_forms(forms=forms, accepted=accepted)
    client = SecClient.from_env(user_agent=user_agent, data_dir=data_dir)
    try:
        master_path = await download_master_index(client, data_dir=data_dir, year=year, quarter=quarter)
        rows = load_master_index(master_path)
        flt = FilingFilter(forms=valid_forms, include_amended=include_amended)
        matched = filter_master_rows(rows, flt)
        cik_set = resolve_cik_filter(cik=cik, ticker=ticker)
        if cik_set is not None:
            matched = [r for r in matched if r.cik.zfill(10) in cik_set]
        return matched, master_path
    finally:
        await client.aclose()


async def _collect_latest_row_for_company(
    *,
    cik: str,
    user_agent: Optional[str],
    data_dir: Path,
) -> Optional[MasterIndexRow]:
    client = SecClient.from_env(user_agent=user_agent, data_dir=data_dir)
    try:
        cik10 = str(int(str(cik).strip())).zfill(10)
        payload = await client.get_json(f"https://data.sec.gov/submissions/CIK{cik10}.json")
        filings = payload.get("filings", {})
        recent = filings.get("recent", {}) if isinstance(filings, dict) else {}
        acc = recent.get("accessionNumber", [])
        forms = recent.get("form", [])
        dates = recent.get("filingDate", [])
        if not isinstance(acc, list) or not acc:
            return None
        accession = str(acc[0]).strip()
        form = str(forms[0]).strip() if isinstance(forms, list) and forms else ""
        filed = str(dates[0]).strip() if isinstance(dates, list) and dates else ""
        try:
            filed_dt = date.fromisoformat(filed)
        except Exception:
            filed_dt = date.today()
        filename = f"edgar/data/{int(cik10)}/{accession.replace('-', '')}/{accession}.txt"
        return MasterIndexRow(
            cik=cik10,
            company_name=str(payload.get("name", "")).strip(),
            form_type=form or "UNKNOWN",
            date_filed=filed_dt,
            filename=filename,
        )
    finally:
        await client.aclose()


async def _download_datamule_tars_async(
    *,
    rows: Sequence[MasterIndexRow],
    out_dir: Path,
    api_key: Optional[str],
    show_progress: bool,
    concurrency: int,
) -> List[DownloadResult]:
    base_url = "https://sec-library.tar.datamule.xyz/"
    out_dir.mkdir(parents=True, exist_ok=True)
    key = api_key or os.getenv("DATAMULE_API_KEY")
    headers = {"Connection": "keep-alive", "Accept-Encoding": "gzip, deflate, br"}
    if key:
        headers["Authorization"] = f"Bearer {key}"

    total = len(rows)
    sem = asyncio.Semaphore(max(1, int(concurrency)))
    progress_lock = asyncio.Lock()
    done = 0
    downloaded = 0
    skipped = 0
    errors = 0
    active = 0
    started_at = asyncio.get_event_loop().time()

    def _render_progress(current_acc: str) -> None:
        _progress_bar("downloading tar files", done, total, f"{current_acc[:18]}")

    async def one(r: MasterIndexRow) -> DownloadResult:
        nonlocal done, downloaded, skipped, errors, active
        acc_no_dash = r.accession.replace("-", "").zfill(18)
        tar_name = f"{acc_no_dash}.tar"
        tar_path = out_dir / tar_name
        if tar_path.exists():
            async with progress_lock:
                skipped += 1
                done += 1
                if show_progress:
                    _render_progress(r.accession)
            return DownloadResult(
                accession=r.accession,
                cik=r.cik,
                form_type=r.form_type,
                date_filed=r.date_filed,
                status="skipped",
                output_dir=str(tar_path),
            )

        url = base_url + tar_name
        async with sem:
            async with progress_lock:
                active += 1
                if show_progress:
                    _render_progress(r.accession)
            try:
                async with client.stream("GET", url) as resp:
                    resp.raise_for_status()
                    with tar_path.open("wb") as f:
                        async for chunk in resp.aiter_bytes():
                            if chunk:
                                f.write(chunk)
                result = DownloadResult(
                    accession=r.accession,
                    cik=r.cik,
                    form_type=r.form_type,
                    date_filed=r.date_filed,
                    status="downloaded",
                    output_dir=str(tar_path),
                )
                async with progress_lock:
                    downloaded += 1
            except Exception as e:
                try:
                    if tar_path.exists():
                        tar_path.unlink()
                except Exception:
                    pass
                result = DownloadResult(
                    accession=r.accession,
                    cik=r.cik,
                    form_type=r.form_type,
                    date_filed=r.date_filed,
                    status="error",
                    error=str(e),
                    output_dir=str(tar_path),
                )
                async with progress_lock:
                    errors += 1
            finally:
                async with progress_lock:
                    active = max(0, active - 1)
        async with progress_lock:
            done += 1
            if show_progress:
                _render_progress(r.accession)
        return result

    async with httpx.AsyncClient(follow_redirects=True, timeout=120.0, headers=headers) as client:
        results = await asyncio.gather(*[one(r) for r in rows])

    if show_progress and total > 0:
        _progress_bar("downloading tar files", total, total, "")
        _step_done(f"downloaded={downloaded} skipped={skipped} errors={errors}")
    return results


def _safe_extract_tar_to_accession(*, tar_path: Path, target_dir: Path, accession: str) -> None:
    target_dir.mkdir(parents=True, exist_ok=True)
    with tarfile.open(tar_path, mode="r:*") as tf:
        members = tf.getmembers()
        for m in members:
            if not m.isfile():
                continue
            name = m.name.lstrip("/").replace("\\", "/")
            parts = [p for p in name.split("/") if p and p != "."]
            if not parts:
                continue
            if len(parts) > 1:
                head = parts[0]
                head_norm = head.replace("-", "")
                if head_norm.isdigit() and len(head_norm) in (18, 20):
                    parts = parts[1:]
            rel = Path(*parts)
            out_path = (target_dir / rel).resolve()
            if not str(out_path).startswith(str(target_dir.resolve())):
                continue
            out_path.parent.mkdir(parents=True, exist_ok=True)
            src = tf.extractfile(m)
            if src is None:
                continue
            with out_path.open("wb") as dst:
                shutil.copyfileobj(src, dst)


def _extract_and_cleanup_datamule_tars(
    *,
    results: List[DownloadResult],
    data_dir: Path,
    tar_dir: Path,
    show_progress: bool,
    group_label: Optional[str],
) -> List[DownloadResult]:
    updated: List[DownloadResult] = []
    candidates = [r for r in results if r.status != "error" and r.output_dir and Path(r.output_dir).suffix.lower() == ".tar"]
    total = len(candidates)
    done = 0
    for r in results:
        if r.status == "error" or not r.output_dir:
            updated.append(r)
            continue
        tar_path = Path(r.output_dir)
        if not tar_path.exists() or tar_path.suffix.lower() != ".tar":
            updated.append(r)
            continue
        dest = filing_dir(
            data_dir=data_dir,
            form_type=r.form_type,
            cik=r.cik,
            accession=r.accession,
            group_label=group_label,
        )
        try:
            if dest.exists():
                shutil.rmtree(dest)
            _safe_extract_tar_to_accession(tar_path=tar_path, target_dir=dest, accession=r.accession)
            tar_path.unlink(missing_ok=True)
            done += 1
            if show_progress and total > 0:
                _progress_bar("extracting filings", done, total, r.accession)
            updated.append(
                DownloadResult(
                    accession=r.accession,
                    cik=r.cik,
                    form_type=r.form_type,
                    date_filed=r.date_filed,
                    status=r.status,
                    error=r.error,
                    output_dir=str(dest),
                )
            )
        except Exception as e:
            done += 1
            if show_progress and total > 0:
                _progress_bar("extracting filings", done, total, r.accession)
            updated.append(
                DownloadResult(
                    accession=r.accession,
                    cik=r.cik,
                    form_type=r.form_type,
                    date_filed=r.date_filed,
                    status="error",
                    error=str(e),
                    output_dir=str(dest),
                )
            )
    shutil.rmtree(tar_dir, ignore_errors=True)
    return updated


def download_quarter(
    *,
    year: Optional[int] = None,
    quarter: Optional[int] = None,
    forms: Optional[Sequence[str]] = None,
    data_dir: str | Path = "data",
    file_types: Sequence[str] = (".htm", ".html", ".xml", ".xbrl", ".pdf"),
    include_amended: bool = False,
    cik: Optional[str | int | Sequence[str | int]] = None,
    ticker: Optional[str | Sequence[str]] = None,
    concurrency: int = 6,
    user_agent: Optional[str] = None,
    manifest_path: Optional[str | Path] = None,
    show_progress: bool = True,
    on_progress: Optional[Callable[[int, int, Optional[DownloadResult], int], None]] = None,
) -> List[DownloadResult]:
    latest_mode = year is None and quarter is None and forms is None
    if latest_mode and cik is None and ticker is None:
        raise ValueError("For latest single filing mode, provide `cik` or `ticker`.")
    if not latest_mode and (year is None or quarter is None or forms is None):
        raise ValueError("Provide `year`, `quarter`, and `forms` together, or omit all three for latest mode.")

    forms_for_log = forms if forms is not None else ["latest"]
    if show_progress:
        _step_info(
            (
                "latest single download "
                if latest_mode
                else f"quarter download year={year} q={quarter} "
            )
            + _render_filter_label(forms=forms_for_log, cik=cik, ticker=ticker)
        )

    progress_cb = on_progress if on_progress is not None else (_default_progress_callback if show_progress else None)

    if latest_mode:
        data_dir_path = Path(data_dir)
        cik_set = resolve_cik_filter(cik=cik, ticker=ticker)
        chosen_cik = sorted(cik_set)[0]
        latest_row = asyncio.run(
            _collect_latest_row_for_company(
                cik=chosen_cik,
                user_agent=user_agent,
                data_dir=data_dir_path,
            )
        )
        if latest_row is None:
            return []

        async def _run_latest() -> List[DownloadResult]:
            return await _run_with_downloader(
                runner=lambda dl: dl._download_one(row=latest_row),
                forms=[latest_row.form_type or "8-K"],
                data_dir=data_dir,
                file_types=file_types,
                include_amended=include_amended,
                cik=cik,
                ticker=ticker,
                concurrency=concurrency,
                user_agent=user_agent,
                manifest_path=manifest_path,
                on_progress=progress_cb,
            )

        return asyncio.run(_run_latest())

    async def _run() -> List[DownloadResult]:
        return await _run_with_downloader(
            runner=lambda dl: dl.download_quarter(year=int(year), quarter=int(quarter)),
            forms=forms,
            data_dir=data_dir,
            file_types=file_types,
            include_amended=include_amended,
            cik=cik,
            ticker=ticker,
            concurrency=concurrency,
            user_agent=user_agent,
            manifest_path=manifest_path,
            on_progress=progress_cb,
        )

    return asyncio.run(_run())


def download_quarter_tar(
    *,
    year: Optional[int] = None,
    quarter: Optional[int] = None,
    forms: Optional[Sequence[str]] = None,
    data_dir: str | Path = "data",
    file_types: Sequence[str] = (".htm", ".html", ".xml", ".xbrl", ".pdf"),
    include_amended: bool = False,
    cik: Optional[str | int | Sequence[str | int]] = None,
    ticker: Optional[str | Sequence[str]] = None,
    concurrency: int = 20,
    user_agent: Optional[str] = None,
    manifest_path: Optional[str | Path] = None,
    output_dir: Optional[str | Path] = None,
    datamule_api_key: Optional[str] = None,
    tar_provider: str = "datamule",
    limit: Optional[int] = None,
    extract: bool = True,
    show_progress: bool = True,
    on_progress: Optional[Callable[[int, int, Optional[DownloadResult], int], None]] = None,
) -> List[DownloadResult]:
    latest_mode = year is None and quarter is None and forms is None
    if latest_mode and cik is None and ticker is None:
        raise ValueError("For latest single filing mode, provide `cik` or `ticker`.")
    if not latest_mode and (year is None or quarter is None or forms is None):
        raise ValueError("Provide `year`, `quarter`, and `forms` together, or omit all three for latest mode.")

    forms_for_log = forms if forms is not None else ["latest"]
    if show_progress:
        _step_info(
            (
                f"latest single tar download "
                if latest_mode
                else f"quarter tar download year={year} q={quarter} "
            )
            + _render_filter_label(forms=forms_for_log, cik=cik, ticker=ticker)
        )
    if tar_provider == "local":
        if latest_mode:
            raise ValueError("latest-mode without year/quarter/forms is only supported with tar_provider='datamule'")
        if forms is None or year is None or quarter is None:
            raise ValueError("year, quarter, and forms are required for tar_provider='local'")
        progress_cb = on_progress if on_progress is not None else (_default_progress_callback if show_progress else None)

        async def _run_local() -> List[DownloadResult]:
            return await _run_with_downloader(
                runner=lambda dl: dl.download_quarter(year=int(year), quarter=int(quarter)),
                forms=forms,
                data_dir=data_dir,
                file_types=file_types,
                include_amended=include_amended,
                cik=cik,
                ticker=ticker,
                concurrency=concurrency,
                user_agent=user_agent,
                manifest_path=manifest_path,
                output_format="tar",
                on_progress=progress_cb,
            )

        return asyncio.run(_run_local())

    if tar_provider != "datamule":
        raise ValueError("tar_provider must be 'datamule' or 'local'")

    data_dir_path = Path(data_dir)
    group_label = resolve_output_group_label(cik=cik, ticker=ticker)
    out_dir = Path(output_dir) if output_dir is not None else (data_dir_path / "filings_tar")

    if latest_mode:
        cik_set = resolve_cik_filter(cik=cik, ticker=ticker)
        chosen_cik = sorted(cik_set)[0]
        latest_row = asyncio.run(
            _collect_latest_row_for_company(
                cik=chosen_cik,
                user_agent=user_agent,
                data_dir=data_dir_path,
            )
        )
        rows = [latest_row] if latest_row is not None else []
        master_path = None
    else:
        rows, master_path = asyncio.run(
            _collect_matched_rows_for_quarter(
                year=int(year),
                quarter=int(quarter),
                forms=forms,
                data_dir=data_dir_path,
                include_amended=include_amended,
                cik=cik,
                ticker=ticker,
                user_agent=user_agent,
            )
        )
    if not rows:
        return []
    if show_progress:
        _step_done(f"queued {len(rows)} filings")
    if limit is not None:
        limit = int(limit)
        if limit <= 0:
            return []
        rows = rows[:limit]

    accessions = [r.accession for r in rows]
    # Keep order and de-duplicate.
    accessions = list(dict.fromkeys(accessions))

    # Datamule mode: fetch source tar files directly from DataMule tar endpoint.
    # `file_types` filtering is not applied in this mode.
    results = asyncio.run(
        _download_datamule_tars_async(
            rows=rows,
            out_dir=out_dir,
            api_key=datamule_api_key,
            show_progress=show_progress,
            concurrency=concurrency,
        )
    )
    if extract:
        results = _extract_and_cleanup_datamule_tars(
            results=results,
            data_dir=data_dir_path,
            tar_dir=out_dir,
            show_progress=show_progress,
            group_label=group_label,
        )

    # Match existing quarter behavior: clear quarter index cache when run completes.
    if master_path is not None:
        try:
            if master_path.parent.exists():
                import shutil

                shutil.rmtree(master_path.parent)
        except Exception:
            pass

    return results


def download_year(
    *,
    year: int,
    forms: Sequence[str],
    data_dir: str | Path = "data",
    file_types: Sequence[str] = (".htm", ".html", ".xml", ".xbrl", ".pdf"),
    include_amended: bool = False,
    cik: Optional[str | int | Sequence[str | int]] = None,
    ticker: Optional[str | Sequence[str]] = None,
    concurrency: int = 6,
    user_agent: Optional[str] = None,
    manifest_path: Optional[str | Path] = None,
    quarters: Sequence[int] = (1, 2, 3, 4),
    show_progress: bool = True,
    on_progress: Optional[Callable[[int, int, Optional[DownloadResult], int], None]] = None,
) -> List[DownloadResult]:
    if show_progress:
        _step_info(
            f"year download year={year} "
            + _render_filter_label(forms=forms, cik=cik, ticker=ticker)
        )
    progress_cb = on_progress if on_progress is not None else (_default_progress_callback if show_progress else None)

    async def _run() -> List[DownloadResult]:
        return await _run_with_downloader(
            runner=lambda dl: dl.download_year(year=year, quarters=quarters),
            forms=forms,
            data_dir=data_dir,
            file_types=file_types,
            include_amended=include_amended,
            cik=cik,
            ticker=ticker,
            concurrency=concurrency,
            user_agent=user_agent,
            manifest_path=manifest_path,
            on_progress=progress_cb,
        )

    return asyncio.run(_run())


def download_year_tar(
    *,
    year: int,
    forms: Sequence[str],
    data_dir: str | Path = "data",
    file_types: Sequence[str] = (".htm", ".html", ".xml", ".xbrl", ".pdf"),
    include_amended: bool = False,
    cik: Optional[str | int | Sequence[str | int]] = None,
    ticker: Optional[str | Sequence[str]] = None,
    concurrency: int = 20,
    user_agent: Optional[str] = None,
    manifest_path: Optional[str | Path] = None,
    output_dir: Optional[str | Path] = None,
    datamule_api_key: Optional[str] = None,
    tar_provider: str = "datamule",
    limit: Optional[int] = None,
    quarters: Sequence[int] = (1, 2, 3, 4),
    extract: bool = True,
    show_progress: bool = True,
    on_progress: Optional[Callable[[int, int, Optional[DownloadResult], int], None]] = None,
) -> List[DownloadResult]:
    if show_progress:
        _step_info(
            f"year tar download year={year} "
            + _render_filter_label(forms=forms, cik=cik, ticker=ticker)
        )
    if tar_provider == "local":
        progress_cb = on_progress if on_progress is not None else (_default_progress_callback if show_progress else None)

        async def _run_local() -> List[DownloadResult]:
            return await _run_with_downloader(
                runner=lambda dl: dl.download_year(year=year, quarters=quarters),
                forms=forms,
                data_dir=data_dir,
                file_types=file_types,
                include_amended=include_amended,
                cik=cik,
                ticker=ticker,
                concurrency=concurrency,
                user_agent=user_agent,
                manifest_path=manifest_path,
                output_format="tar",
                on_progress=progress_cb,
            )

        return asyncio.run(_run_local())

    if tar_provider != "datamule":
        raise ValueError("tar_provider must be 'datamule' or 'local'")

    out: List[DownloadResult] = []
    for q in quarters:
        remaining = None if limit is None else max(0, int(limit) - len(out))
        if remaining == 0:
            break
        out.extend(
            download_quarter_tar(
                year=year,
                quarter=int(q),
                forms=forms,
                data_dir=data_dir,
                file_types=file_types,
                include_amended=include_amended,
                cik=cik,
                ticker=ticker,
                concurrency=concurrency,
                user_agent=user_agent,
                manifest_path=manifest_path,
                output_dir=output_dir,
                datamule_api_key=datamule_api_key,
                tar_provider="datamule",
                limit=remaining,
                extract=extract,
                show_progress=show_progress,
                on_progress=on_progress,
            )
        )
    return out
