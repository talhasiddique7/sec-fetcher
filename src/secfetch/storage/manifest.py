from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, Optional


@dataclass(frozen=True)
class ManifestEntry:
    accession: str
    form_type: str
    cik: str
    date_filed: str
    strategy: str


class Manifest:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._data: Dict[str, ManifestEntry] = {}

    @property
    def path(self) -> Path:
        return self._path

    def load(self) -> None:
        if not self._path.exists():
            self._data = {}
            return
        raw = json.loads(self._path.read_text())
        out: Dict[str, ManifestEntry] = {}
        for accession, payload in raw.items():
            out[accession] = ManifestEntry(
                accession=accession,
                form_type=payload["form_type"],
                cik=payload["cik"],
                date_filed=payload["date_filed"],
                strategy=payload.get("strategy", "index"),
            )
        self._data = out

    def has(self, accession: str) -> bool:
        return accession in self._data

    def get(self, accession: str) -> Optional[ManifestEntry]:
        return self._data.get(accession)

    def upsert(self, entry: ManifestEntry) -> None:
        self._data[entry.accession] = entry

    def save_atomic(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(self._path.suffix + ".tmp")
        payload = {acc: asdict(ent) for acc, ent in self._data.items()}
        tmp.write_text(json.dumps(payload, indent=2, sort_keys=True))
        tmp.replace(self._path)

