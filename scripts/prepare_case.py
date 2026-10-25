"""Create an isolated, deliberately broken practice copy."""

import argparse
import shutil
from enum import StrEnum
from pathlib import Path
from typing import cast

import yaml

ROOT = Path(__file__).resolve().parents[1]


class Case(StrEnum):
    STATUS = "status"
    TYPE = "type"
    REQUIRED = "required"
    CONFLICT = "conflict"
    FINAL = "final"


def _object(value: object) -> dict[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ValueError("Unexpected OpenAPI structure")
    return cast(dict[str, object], value)


def _at(value: object, *path: str) -> dict[str, object]:
    current = _object(value)
    for part in path:
        current = _object(current[part])
    return current


def _break_contract(document: dict[str, object], case: Case) -> None:
    schemas = _at(document, "components", "schemas")
    order = _at(schemas, "Order")
    if case is Case.STATUS:
        responses = _at(document, "paths", "/orders", "post", "responses")
        responses["200"] = responses.pop("201")
    elif case is Case.TYPE:
        _at(order, "properties", "quantity")["type"] = "string"
    elif case is Case.REQUIRED:
        order["required"] = ["id", "external_id", "quantity", "status", "warehouse"]
    elif case is Case.CONFLICT:
        _at(document, "paths", "/orders", "post", "responses", "409")["description"] = "Duplicate external ID was accepted"
    elif case is Case.FINAL:
        _at(schemas, "CreateOrder", "properties", "external_id")["pattern"] = "^ORD-"
        order["required"] = ["id", "external_id", "quantity", "status", "warehouse"]


def prepare(case: Case, destination: Path) -> Path:
    if destination.exists():
        raise FileExistsError(f"{destination} exists; choose a new directory")
    shutil.copytree(
        ROOT,
        destination,
        ignore=shutil.ignore_patterns(".git", ".venv", ".work", ".pytest_cache", ".mypy_cache", ".ruff_cache", "__pycache__"),
    )
    spec = destination / "spec" / "openapi.yaml"
    with spec.open(encoding="utf-8") as source:
        document = _object(yaml.safe_load(source))
    _break_contract(document, case)
    spec.write_text(yaml.safe_dump(document, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return destination


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case", choices=[case.value for case in Case])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    case = Case(args.case)
    destination = args.output or ROOT / ".work" / case.value
    try:
        prepare(case, destination)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(f"Practice copy: {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
