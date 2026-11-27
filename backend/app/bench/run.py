"""CLI runner for the Tripwire bench harness (make bench)."""

from __future__ import annotations

import argparse
import json

from app.bench.harness import run_bench


def main() -> None:
    parser = argparse.ArgumentParser(description="Tripwire bench harness runner.")
    parser.add_argument("--case", type=int, default=1, choices=[1, 2, 3], help="Seed case number")
    parser.add_argument("--n", type=int, default=30, help="Number of benchmark iterations")
    args = parser.parse_args()

    result = run_bench(case_num=args.case, n=args.n)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
