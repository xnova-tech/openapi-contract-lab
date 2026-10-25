"""Compare real HTTP responses with an independently authored OpenAPI file."""

import argparse
import sys
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

import httpx
from jsonschema import Draft202012Validator

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.case_mode import Case, read_case  # noqa: E402
from scripts.contract_document import ContractError, load_contract, request_contract, response_contract  # noqa: E402
from scripts.probes import BASELINE_PROBES, PREFIX_PROBE, Probe  # noqa: E402


def _check_request(document: Mapping[str, object], probe: Probe, status: int) -> None:
    if probe.body is None:
        return
    schema = request_contract(document, probe.path_template, probe.method)
    errors = sorted(Draft202012Validator(schema).iter_errors(probe.body), key=lambda error: str(error.path))
    if status == 422 and not errors:
        raise ContractError(f"{probe.label}: requestBody accepts the input, but HTTP returned 422")
    if status != 422 and errors:
        first = errors[0]
        pointer = "/" + "/".join(str(part) for part in first.absolute_path)
        raise ContractError(f"{probe.label}: requestBody rejects JSON {pointer}, but HTTP returned {status}: {first.message}")


def check_response(client: httpx.Client, document: Mapping[str, object], probe: Probe) -> object:
    operation = f"{probe.method.upper()} {probe.path_template} [{probe.label}]"
    response = client.request(probe.method.upper(), probe.path, json=probe.body, params=probe.query)
    if response.status_code != probe.status:
        raise ContractError(f"{operation}: expected HTTP {probe.status}, got {response.status_code}: {response.text}")
    _check_request(document, probe, response.status_code)
    try:
        schema = response_contract(document, probe.path_template, probe.method, response.status_code)
    except ContractError as exc:
        raise ContractError(f"{operation}: HTTP {response.status_code} observed; {exc}") from exc
    media_type = response.headers.get("content-type", "").split(";", 1)[0].lower()
    if media_type != "application/json":
        raise ContractError(f"{operation}: expected application/json, got {media_type!r}")
    try:
        payload = response.json()
    except ValueError as exc:
        raise ContractError(f"{operation}: response is not JSON") from exc
    errors = sorted(Draft202012Validator(schema).iter_errors(payload), key=lambda error: str(error.path))
    if errors:
        first = errors[0]
        pointer = "/" + "/".join(str(part) for part in first.absolute_path)
        raise ContractError(f"{operation}: JSON {pointer}: {first.message}")
    return payload


def _substitute(probe: Probe, run_id: str, order_id: int | None) -> Probe:
    if "{order_id}" in probe.path and order_id is None:
        raise ContractError("Create probe did not return an order ID")
    replacements = {"run_id": run_id, "order_id": order_id}
    body = probe.body
    if isinstance(body, dict):
        body = {key: value.format(**replacements) if isinstance(value, str) else value for key, value in body.items()}
    return replace(probe, path=probe.path.format(**replacements), body=body)


def check_contract(spec: Path, base_url: str) -> int:
    try:
        document = load_contract(spec)
        probes = (*BASELINE_PROBES, *((PREFIX_PROBE,) if read_case(spec) is Case.FINAL else ()))
        run_id = uuid4().hex[:12]
        order_id: int | None = None
        with httpx.Client(base_url=base_url, timeout=5, trust_env=False) as client:
            for probe in probes:
                payload = check_response(client, document, _substitute(probe, run_id, order_id))
                if probe.label == "create":
                    if not isinstance(payload, dict) or type(payload.get("id")) is not int:
                        raise ContractError("POST /orders: response has no integer ID")
                    order_id = payload["id"]
                print(f"PASS {probe.label}")
    except (ContractError, httpx.HTTPError) as exc:
        print(f"FAIL {exc}")
        return 1
    print(f"PASS {len(probes)} live HTTP contract checks")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--base-url", required=True)
    args = parser.parse_args()
    return check_contract(args.spec, args.base_url)


if __name__ == "__main__":
    raise SystemExit(main())
