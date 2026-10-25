"""Live contract checks and independent negative controls."""

from pathlib import Path
from typing import cast

import pytest
import yaml

from scripts.case_mode import CASE_MARKER, Case
from scripts.contract_document import ContractError, load_contract
from scripts.prepare_case import prepare

ROOT = Path(__file__).resolve().parents[1]


def _baseline_spec(directory: Path) -> Path:
    (directory / "spec").mkdir()
    (directory / CASE_MARKER).write_text(f"{Case.BASELINE.value}\n", encoding="utf-8")
    spec = directory / "spec" / "openapi.yaml"
    spec.write_bytes((ROOT / "spec" / "openapi.yaml").read_bytes())
    return spec


def _set_spec_field(spec: Path, path: tuple[str, ...], key: str, value: object | None) -> None:
    document: object = yaml.safe_load(spec.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise AssertionError("Expected an OpenAPI object")
    current = cast(dict[str, object], document)
    for part in path:
        child = current[part]
        if not isinstance(child, dict):
            raise AssertionError(f"Expected an object at {part}")
        current = cast(dict[str, object], child)
    if value is None:
        del current[key]
    else:
        current[key] = value
    spec.write_text(yaml.safe_dump(document, sort_keys=False, allow_unicode=True), encoding="utf-8")


def _run_checker(spec: Path, url: str) -> tuple[int, str]:
    import subprocess
    import sys

    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "check_contract.py"),
            "--spec",
            str(spec),
            "--base-url",
            url,
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    return completed.returncode, completed.stdout + completed.stderr


def test_baseline_is_green_against_real_http(live_url: str) -> None:
    code, output = _run_checker(ROOT / "spec" / "openapi.yaml", live_url)
    assert code == 0, output
    assert "live HTTP contract checks" in output
    assert "PASS duplicate" in output


@pytest.mark.parametrize(
    ("case", "marker"),
    [
        (Case.STATUS, "HTTP 201 observed"),
        (Case.TYPE, "quantity"),
        (Case.REQUIRED, "warehouse"),
        (Case.CONFLICT, "code"),
        (Case.FINAL, "warehouse"),
    ],
)
def test_broken_cases_are_red_against_real_http(case: Case, marker: str, live_url: str, tmp_path: Path) -> None:
    copy = prepare(case, tmp_path / case.value)
    spec = copy / "spec" / "openapi.yaml"
    load_contract(spec)
    code, output = _run_checker(spec, live_url)
    assert code != 0, f"{case} unexpectedly passed: {output}"
    assert "FAIL" in output
    assert marker in output


def test_missing_local_reference_is_rejected(tmp_path: Path) -> None:
    source = (ROOT / "spec" / "openapi.yaml").read_text(encoding="utf-8")
    broken = tmp_path / "broken.yaml"
    broken.write_text(
        source.replace("#/components/schemas/Health", "#/components/schemas/Absent"),
        encoding="utf-8",
    )
    with pytest.raises(ContractError, match="Absent"):
        load_contract(broken)


def test_final_stays_red_if_prefix_pattern_is_removed(live_url: str, tmp_path: Path) -> None:
    spec = prepare(Case.FINAL, tmp_path / "final") / "spec" / "openapi.yaml"
    _set_spec_field(spec, ("components", "schemas", "Order"), "required", ["id", "external_id", "quantity", "status"])
    _set_spec_field(spec, ("components", "schemas", "CreateOrder", "properties", "external_id"), "pattern", None)
    code, output = _run_checker(spec, live_url)
    assert code != 0, output
    assert "new external ID rule" in output
    assert "expected HTTP 422, got 201" in output or "requestBody accepts the input, but HTTP returned 422" in output


def test_conflict_description_can_paraphrase_message(live_url: str, tmp_path: Path) -> None:
    spec = _baseline_spec(tmp_path)
    _set_spec_field(
        spec, ("paths", "/orders", "post", "responses", "409"), "description", "An order already uses this external ID"
    )
    code, output = _run_checker(spec, live_url)
    assert code == 0, output


@pytest.mark.parametrize("minimum", [0, 2])
def test_request_minimum_must_match_http_behavior(minimum: int, live_url: str, tmp_path: Path) -> None:
    spec = _baseline_spec(tmp_path)
    _set_spec_field(spec, ("components", "schemas", "CreateOrder", "properties", "quantity"), "minimum", minimum)
    code, output = _run_checker(spec, live_url)
    assert code != 0, output
    assert "requestBody" in output
    assert "quantity" in output or "minimum quantity" in output


def test_missing_case_marker_cannot_disable_final_probe(live_url: str, tmp_path: Path) -> None:
    copy = prepare(Case.FINAL, tmp_path / "final")
    (copy / CASE_MARKER).unlink()
    code, output = _run_checker(copy / "spec" / "openapi.yaml", live_url)
    assert code != 0, output
    assert "Invalid exercise case marker" in output
