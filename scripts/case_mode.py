"""Keep exercise mode separate from the student-editable OpenAPI document."""

from enum import StrEnum
from pathlib import Path

from scripts.contract_document import ContractError

CASE_MARKER = ".exercise-case"


class Case(StrEnum):
    BASELINE = "baseline"
    STATUS = "status"
    TYPE = "type"
    REQUIRED = "required"
    CONFLICT = "conflict"
    FINAL = "final"


def read_case(spec: Path) -> Case:
    marker = spec.resolve().parent.parent / CASE_MARKER
    try:
        return Case(marker.read_text(encoding="utf-8").strip())
    except (OSError, ValueError) as exc:
        raise ContractError(f"Invalid exercise case marker {marker}: {exc}") from exc
