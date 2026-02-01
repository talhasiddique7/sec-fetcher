from __future__ import annotations

SEC_ARCHIVES_BASE = "https://www.sec.gov/Archives/"


def accession_no_dash(accession: str) -> str:
    return accession.replace("-", "")


def filing_folder_url(*, cik: str, accession: str) -> str:
    # Folder: /Archives/edgar/data/{CIK}/{ACCESSION_NO_DASH}/
    return f"{SEC_ARCHIVES_BASE}edgar/data/{int(cik)}/{accession_no_dash(accession)}/"


def filing_index_json_url(*, cik: str, accession: str) -> str:
    # Folder listing JSON: /Archives/edgar/data/{CIK}/{ACCESSION_NO_DASH}/index.json
    return filing_folder_url(cik=cik, accession=accession) + "index.json"
