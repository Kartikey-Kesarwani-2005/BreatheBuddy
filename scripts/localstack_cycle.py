"""Run one full BreatheBuddy cycle against LocalStack (S3/DynamoDB/SNS).

    python scripts/localstack_cycle.py

Assumes scripts/localstack_bootstrap.py has been run and the env vars it prints
are exported (or set in your shell).
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))


def main() -> None:
    os.environ.setdefault("BB_USE_AWS", "true")
    from breathebuddy.service import run_cycle
    result = run_cycle()
    print("cycle complete:")
    print(f"  ingested        : {result['ingest']['ingested']}")
    print(f"  grid cells      : {result['grid_cells']}")
    print(f"  school alerts   : {len(result['school_alerts'])}")
    print(f"  subscriber alerts: {len(result['subscriber_alerts'])}")
    print("\nCheck LocalStack for the S3 object, DynamoDB items and SNS message.")


if __name__ == "__main__":
    main()
