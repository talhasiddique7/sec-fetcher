from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Sequence

from secfetch.exceptions import SecFetchError


class FormTypeValidationError(SecFetchError):
    pass


@dataclass(frozen=True)
class FormTypesConfig:
    accepted_form_types: List[str]


def _load_packaged_form_types() -> FormTypesConfig:
    # Standard-library resource loading (no runtime deps).
    from importlib.resources import files

    raw = (files("secfetch.resources") / "form_types.json").read_text(encoding="utf-8")
    payload = json.loads(raw)
    accepted = payload.get("accepted_form_types")
    if not isinstance(accepted, list) or not all(isinstance(x, str) for x in accepted):
        raise FormTypeValidationError("Invalid packaged form_types.json format")
    return FormTypesConfig(accepted_form_types=sorted(set(accepted)))


def ensure_form_types_json(
    *, data_dir: Path, target_rel_path: Path = Path("config/form_types.json")
) -> Path:
    """
    Ensure a user-editable form types JSON exists under the data directory.
    Returns its path.
    """
    out_path = data_dir / target_rel_path
    if out_path.exists():
        return out_path

    cfg = _load_packaged_form_types()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps({"accepted_form_types": cfg.accepted_form_types}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return out_path


def load_accepted_form_types(*, data_dir: Optional[Path] = None) -> List[str]:
    """
    Load accepted form types from:
    - data_dir/config/form_types.json (if data_dir provided), else
    - packaged secfetch/resources/form_types.json
    """
    if data_dir is None:
        return _load_packaged_form_types().accepted_form_types

    json_path = ensure_form_types_json(data_dir=data_dir)
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    accepted = payload.get("accepted_form_types")
    if not isinstance(accepted, list) or not all(isinstance(x, str) for x in accepted):
        raise FormTypeValidationError(f"Invalid form types file: {json_path}")
    return sorted(set(x.strip() for x in accepted if x.strip()))


def validate_forms(*, forms: Sequence[str], accepted: Iterable[str]) -> List[str]:
    accepted_set = {x.strip() for x in accepted}
    requested = [f.strip() for f in forms if f and f.strip()]
    if not requested:
        raise FormTypeValidationError("forms must be a non-empty list of SEC form types")

    unknown = sorted({f for f in requested if f not in accepted_set})
    if unknown:
        sample = ", ".join(sorted(list(accepted_set))[:12])
        raise FormTypeValidationError(
            "Unknown/unsupported form types: "
            + ", ".join(unknown)
            + f". Allowed forms come from form_types.json (e.g. {sample}, ...)."
        )
    return requested

