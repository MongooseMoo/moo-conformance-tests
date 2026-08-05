"""Trusted inventory comparison for immutable candidate conformance data."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .execution_ledger import ExecutionLedgerError, validate_candidate_inventory


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-root", required=True, type=Path)
    parser.add_argument("--candidate-tests", required=True, type=Path)
    parser.add_argument("--candidate-db", required=True, type=Path)
    parser.add_argument("--candidate-db-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)

    try:
        inventory = validate_candidate_inventory(
            args.candidate_root,
            args.candidate_tests,
            candidate_db_path=args.candidate_db,
            candidate_db_dir=args.candidate_db_dir,
        )
    except ExecutionLedgerError as exc:
        parser.error(str(exc))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(inventory, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        "Trusted controller validated "
        f"{len(inventory['trusted_case_ids'])} trusted identities within "
        f"{len(inventory['candidate_case_ids'])} candidate identities"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
