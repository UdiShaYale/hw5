"""Run the Campus Customs agent team from the command line.

    python run_team.py
    python run_team.py --message "Work ticket 103 only."
    python run_team.py --approve "Uditaa Shandilya"     # allows record_payment

Every run appends its agent-loop steps to output/audit_trail.json.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

# The Windows console defaults to cp1252, which cannot encode the arrows and
# dashes the agents write. Print UTF-8 and replace anything that still fails.
for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")

from agents.team import run_team  # noqa: E402

DEFAULT_MESSAGE = (
    "Work today's open tickets at Campus Customs. For each one, verify the facts "
    "with the shop tools, delegate to the right specialist, and tell me what you "
    "decided and what still needs a human."
)


async def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Campus Customs agent team")
    parser.add_argument("--message", default=DEFAULT_MESSAGE)
    parser.add_argument(
        "--approve",
        default="",
        metavar="NAME",
        help="name of the human approving spending; without this, payments are blocked",
    )
    parser.add_argument("--json", action="store_true", help="print the full result as JSON")
    args = parser.parse_args()

    result = await run_team(
        args.message,
        approved_by=args.approve,
        allow_spending=bool(args.approve.strip()),
    )

    if args.json:
        print(json.dumps(result, indent=2, default=str))
    else:
        print(f"\n=== run {result['run_id']} ===\n")
        print(result["answer"])
        print("\n--- delegations ---")
        for d in result["delegations"]:
            print(f"  {d['from_agent']} → {d['to_agent']} [{d['status']}] {d['question'][:90]}")
        print("\n--- usage ---")
        print(json.dumps(result["usage"], indent=2))
        print(f"\naudit trail now holds {result['audit_steps']} steps")

    return 1 if result.get("error") else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
