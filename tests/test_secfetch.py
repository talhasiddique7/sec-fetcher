from __future__ import annotations

import json
from pathlib import Path

import pytest


def _write_accepted_forms(data_dir: Path, forms: list[str]) -> None:
    p = data_dir / "config" / "form_types.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"accepted_form_types": forms}, indent=2) + "\n", encoding="utf-8")


def _master_idx_one_row(*, cik: str, form_type: str, date_filed: str, accession: str) -> str:
    # accession must have dashes for SEC format (e.g. 0001000045-24-000001)
    accession_no_dash = accession.replace("-", "")
    return "\n".join(
        [
            "Description: Master Index of EDGAR Dissemination Feed",
            "Last Data Received: 2024-01-02",
            "CIK|Company Name|Form Type|Date Filed|Filename",
            "--------------------------------------------------------------------------------",
            f"{cik}|TEST CORP|{form_type}|{date_filed}|edgar/data/{int(cik)}/{accession_no_dash}/{accession}.txt",
            "",
        ]
    )


class DummyClient:
    def __init__(self, *, master_idx_text: str, listing: dict, file_bytes: dict[str, bytes]):
        self._master_idx_text = master_idx_text
        self._listing = listing
        self._file_bytes = file_bytes

    async def aclose(self) -> None:
        return None

    async def get_bytes(self, url: str) -> bytes:
        if url.endswith("/master.idx") or url.endswith("master.idx"):
            return self._master_idx_text.encode("utf-8")
        return self._file_bytes[url]

    async def get_json(self, url: str):
        # Only used for /index.json
        assert url.endswith("index.json")
        return self._listing


def test_quarter_download_deletes_index_on_success(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    data_dir = tmp_path / "data"
    _write_accepted_forms(data_dir, ["10-Q"])

    cik = "1000045"
    accession = "0001000045-24-000001"

    master_idx = _master_idx_one_row(cik=cik, form_type="10-Q", date_filed="2024-01-02", accession=accession)
    listing = {"directory": {"item": [{"name": "doc.xml"}, {"name": "readme.txt"}]}}

    base_folder = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession.replace('-', '')}/"
    file_bytes = {base_folder + "doc.xml": b"<xml/>", base_folder + "readme.txt": b"nope"}

    from secfetch import download_quarter
    import secfetch.downloader as dl_mod

    monkeypatch.setattr(
        dl_mod.SecClient,
        "from_env",
        classmethod(lambda cls, *, user_agent=None, data_dir=None: DummyClient(master_idx_text=master_idx, listing=listing, file_bytes=file_bytes)),
    )

    res = download_quarter(
        year=2024,
        quarter=1,
        forms=["10-Q"],
        data_dir=data_dir,
        file_types=[".xml"],
        user_agent="Test test@example.com",
        concurrency=2,
    )

    assert len(res) == 1
    assert res[0].status == "downloaded"

    # Index cache for the quarter should be deleted on success
    qtr_index_dir = data_dir / "index" / "master" / "2024" / "QTR1"
    assert not qtr_index_dir.exists()

    # Downloaded file should exist
    out_file = data_dir / "filings" / "10-Q" / "0001000045" / accession / "doc.xml"
    assert out_file.exists()


def test_quarter_download_keeps_index_on_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    data_dir = tmp_path / "data"
    _write_accepted_forms(data_dir, ["10-Q"])

    cik = "1000045"
    accession = "0001000045-24-000001"
    master_idx = _master_idx_one_row(cik=cik, form_type="10-Q", date_filed="2024-01-02", accession=accession)

    # Listing contains no files matching ".xml" => triggers error
    listing = {"directory": {"item": [{"name": "readme.txt"}]}}
    base_folder = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession.replace('-', '')}/"
    file_bytes = {base_folder + "readme.txt": b"nope"}

    from secfetch import download_quarter
    import secfetch.downloader as dl_mod

    monkeypatch.setattr(
        dl_mod.SecClient,
        "from_env",
        classmethod(lambda cls, *, user_agent=None, data_dir=None: DummyClient(master_idx_text=master_idx, listing=listing, file_bytes=file_bytes)),
    )

    res = download_quarter(
        year=2024,
        quarter=1,
        forms=["10-Q"],
        data_dir=data_dir,
        file_types=[".xml"],
        user_agent="Test test@example.com",
        concurrency=1,
    )

    assert len(res) == 1
    assert res[0].status == "error"

    # Index cache should remain when there were errors
    qtr_index_dir = data_dir / "index" / "master" / "2024" / "QTR1"
    assert qtr_index_dir.exists()

