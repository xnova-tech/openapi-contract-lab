"""Live contract checks and independent negative controls."""

from pathlib import Path

import pytest

from scripts.contract_document import ContractError, load_contract
from scripts.prepare_case import Case, prepare

ROOT = Path(__file__).resolve().parents[1]


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


@pytest.mark.parametrize("case", list(Case))
def test_broken_cases_are_red_against_real_http(case: Case, live_url: str, tmp_path: Path) -> None:
    copy = prepare(case, tmp_path / case.value)
    spec = copy / "spec" / "openapi.yaml"
    load_contract(spec)
    code, output = _run_checker(spec, live_url)
    assert code != 0, f"{case} unexpectedly passed: {output}"
    assert "FAIL" in output


def test_missing_local_reference_is_rejected(tmp_path: Path) -> None:
    source = (ROOT / "spec" / "openapi.yaml").read_text(encoding="utf-8")
    broken = tmp_path / "broken.yaml"
    broken.write_text(
        source.replace("#/components/schemas/Health", "#/components/schemas/Absent"),
        encoding="utf-8",
    )
    with pytest.raises(ContractError, match="Absent"):
        load_contract(broken)
