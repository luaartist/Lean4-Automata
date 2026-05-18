#!/usr/bin/env python3
"""
End-to-end test of Lean proof audit forum flows.

Tests all four flows:
1. Audit summary
2. Audit full
3. Millennium paths
4. Cohesion ranking
5. Proof edit guard

All results are validated and printed as structured JSON.
"""

import json
import sys
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
FORUM_HANDLER = REPO_ROOT / "tools" / "forum_handlers.py"


def run_flow(flow_name: str, params: dict = None) -> dict:
    """Execute a flow and return the parsed result."""
    if params is None:
        params = {}

    cmd = [
        sys.executable,
        str(FORUM_HANDLER),
        flow_name,
        json.dumps(params),
    ]

    result = subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )

    if result.returncode != 0:
        return {
            "status": "error",
            "stderr": result.stderr,
        }

    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as e:
        return {
            "status": "error",
            "error": f"JSON parse error: {e}",
            "output": result.stdout[:200],
        }


def validate_ticket(ticket: dict, expected_type: str) -> bool:
    """Validate ticket structure."""
    required = [
        "title",
        "description",
        "created_at",
        "type",
        "data",
        "metadata",
    ]
    for key in required:
        if key not in ticket:
            print(f"  ✗ Missing key: {key}")
            return False

    if ticket.get("type") != expected_type:
        print(f"  ✗ Wrong type. Expected: {expected_type}, Got: {ticket.get('type')}")
        return False

    return True


def main():
    """Run comprehensive tests."""
    print("=" * 70)
    print("LEAN PROOF AUDIT FORUM FLOWS - END-TO-END TEST")
    print("=" * 70)
    print()

    tests = [
        {
            "name": "Audit Summary",
            "flow": "lean_proof_audit",
            "params": {"report_type": "summary"},
            "validate": lambda r: (
                "ActualSrcFiles" in r.get("audit", {})
                and "DocumentedEntries" in r.get("audit", {})
            ),
        },
        {
            "name": "Audit Full",
            "flow": "lean_proof_audit",
            "params": {"report_type": "full"},
            "validate": lambda r: (
                "Mismatches" in r.get("ticket", {}).get("data", {})
            ),
        },
        {
            "name": "Millennium Paths",
            "flow": "lean_millennium_paths",
            "params": {},
            "validate": lambda r: (
                "DependencyClosureSize"
                in r.get("ticket", {}).get("data", {})
            ),
        },
        {
            "name": "Cohesion Ranking",
            "flow": "lean_cohesion_ranking",
            "params": {"limit": 5},
            "validate": lambda r: isinstance(
                r.get("ranking", []), list
            )
            and len(r.get("ranking", [])) > 0,
        },
        {
            "name": "Proof Edit Guard",
            "flow": "lean_proof_edit_guard",
            "params": {"run_build": False},
            "validate": lambda r: (
                r.get("proof_edit_guard", {}).get("tool")
                == "lean_proof_edit_guard"
                and "guard" in r.get("proof_edit_guard", {})
            ),
        },
    ]

    passed = 0
    failed = 0

    for test in tests:
        print(f"\n[TEST] {test['name']}")
        print("-" * 70)

        result = run_flow(test["flow"], test["params"])

        if result.get("status") != "ok":
            print(f"  ✗ Flow failed: {result.get('error', 'Unknown error')}")
            failed += 1
            continue

        # Validate ticket structure
        ticket = result.get("ticket")
        if not validate_ticket(ticket, "lean_audit"):
            failed += 1
            continue

        # Validate test-specific conditions
        if not test["validate"](result):
            print(f"  ✗ Validation failed for {test['name']}")
            failed += 1
            continue

        # All checks passed
        print(f"  ✓ Flow executed successfully")
        print(f"  ✓ Ticket created: {ticket.get('title')}")

        # Print sample data
        data = ticket.get("data", {})
        if isinstance(data, dict) and not isinstance(data, list):
            # For summary/paths
            for key, value in list(data.items())[:3]:
                if not isinstance(value, (list, dict)):
                    print(f"    - {key}: {value}")
        elif isinstance(data, list) and len(data) > 0:
            # For ranking
            first_item = data[0]
            if isinstance(first_item, dict):
                print(f"    Top module: {first_item.get('File')} (score: {first_item.get('Score')})")

        passed += 1

    # Summary
    print()
    print("=" * 70)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 70)

    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
