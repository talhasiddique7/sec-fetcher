from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Sequence

from secfetch.index.master import MasterIndexRow, iter_unique_accessions


@dataclass(frozen=True)
class FilingFilter:
    forms: Sequence[str]
    include_amended: bool = False

    def match(self, row: MasterIndexRow) -> bool:
        if row.form_type not in self.forms:
            return False
        if not self.include_amended and "/A" in row.form_type:
            return False
        return True


def filter_master_rows(rows: Iterable[MasterIndexRow], flt: FilingFilter) -> List[MasterIndexRow]:
    return [r for r in iter_unique_accessions(rows) if flt.match(r)]

