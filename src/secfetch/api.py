from __future__ import annotations

import asyncio
from pathlib import Path
from typing import List, Optional, Sequence

from secfetch.downloader import DownloadResult, FilingDownloader


async def _run_with_downloader(
    *,
    runner,
    forms: Sequence[str],
    data_dir: str | Path,
    file_types: Sequence[str],
    include_amended: bool,
    concurrency: int,
    user_agent: Optional[str],
    manifest_path: Optional[str | Path],
) -> List[DownloadResult]:
    dl = FilingDownloader(
        forms=forms,
        data_dir=data_dir,
        file_types=file_types,
        include_amended=include_amended,
        concurrency=concurrency,
        user_agent=user_agent,
        manifest_path=manifest_path,
    )
    try:
        return await runner(dl)
    finally:
        await dl.aclose()


def download_quarter(
    *,
    year: int,
    quarter: int,
    forms: Sequence[str],
    data_dir: str | Path = "data",
    file_types: Sequence[str] = (".htm", ".html", ".xml", ".xbrl", ".pdf"),
    include_amended: bool = False,
    concurrency: int = 6,
    user_agent: Optional[str] = None,
    manifest_path: Optional[str | Path] = None,
) -> List[DownloadResult]:
    async def _run() -> List[DownloadResult]:
        return await _run_with_downloader(
            runner=lambda dl: dl.download_quarter(year=year, quarter=quarter),
            forms=forms,
            data_dir=data_dir,
            file_types=file_types,
            include_amended=include_amended,
            concurrency=concurrency,
            user_agent=user_agent,
            manifest_path=manifest_path,
        )

    return asyncio.run(_run())


def download_year(
    *,
    year: int,
    forms: Sequence[str],
    data_dir: str | Path = "data",
    file_types: Sequence[str] = (".htm", ".html", ".xml", ".xbrl", ".pdf"),
    include_amended: bool = False,
    concurrency: int = 6,
    user_agent: Optional[str] = None,
    manifest_path: Optional[str | Path] = None,
    quarters: Sequence[int] = (1, 2, 3, 4),
) -> List[DownloadResult]:
    async def _run() -> List[DownloadResult]:
        return await _run_with_downloader(
            runner=lambda dl: dl.download_year(year=year, quarters=quarters),
            forms=forms,
            data_dir=data_dir,
            file_types=file_types,
            include_amended=include_amended,
            concurrency=concurrency,
            user_agent=user_agent,
            manifest_path=manifest_path,
        )

    return asyncio.run(_run())

