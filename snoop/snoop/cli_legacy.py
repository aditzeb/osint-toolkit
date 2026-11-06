"""Development and demo utilities kept beside the main CLI."""

from __future__ import annotations

import json


async def run_utility(argv: list[str]) -> int:
    op = argv[0].casefold()
    if op == "evaluate":
        from snoop.evaluate import run_evaluation

        print(json.dumps(run_evaluation(), indent=2, default=str))
        return 0
    if op == "demo":
        from snoop.demo import create_demo_cases

        print(json.dumps(create_demo_cases(), indent=2, default=str))
        return 0
    raise SystemExit(f"unknown utility {op!r}")
