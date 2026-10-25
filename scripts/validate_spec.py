"""Validate OpenAPI 3.1 structure, local references, and JSON Schemas."""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.contract_document import ContractError, load_contract  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("spec", type=Path)
    args = parser.parse_args()
    try:
        load_contract(args.spec)
    except ContractError as exc:
        print(f"INVALID: {exc}")
        return 1
    print(f"VALID: {args.spec}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
