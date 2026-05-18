#!/usr/bin/env python3
"""
Real-world usage examples and validation.

This script demonstrates practical use cases and validates the integration.
"""

import json
import subprocess
import sys
from pathlib import Path


def run_command(cmd):
    """Execute command and return parsed JSON result."""
    result = subprocess.run(
        cmd,
        shell=True,
        capture_output=True,
        text=True,
        cwd=Path.cwd(),
    )
    if result.returncode != 0:
        print(f"  ❌ Command failed: {result.stderr}")
        return None
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        print(f"  ❌ Invalid JSON: {result.stdout[:100]}")
        return None


def example_1_audit_health_check():
    """Example 1: Quick health check of proof map."""
    print("\n" + "=" * 70)
    print("EXAMPLE 1: Audit Health Check")
    print("=" * 70)
    print("\nUse case: Quick verification that proof map is up-to-date")
    print("Command: python3 tools/lean_proof_audit.py audit-summary\n")

    result = run_command(
        "python3 Lean4-Automata/tools/lean_proof_audit.py audit-summary"
    )
    if not result:
        return False

    audit = result.get("audit", {})
    total = audit.get("ActualSrcFiles", 0)
    mismatches = audit.get("MismatchCount", 0)
    pct = (mismatches / total * 100) if total > 0 else 0

    print(f"  📊 Total .lean files: {total}")
    print(f"  📋 Documented entries: {audit.get('DocumentedEntries', 0)}")
    print(f"  ⚠️  Files with import drift: {mismatches} ({pct:.1f}%)")

    if pct > 20:
        print("\n  🔴 STATUS: High drift detected!")
        print("  📌 ACTION: Review Lean_Proof_Map.txt for accuracy")
    elif pct > 5:
        print("\n  🟡 STATUS: Moderate drift")
        print("  📌 ACTION: Update high-drift modules (see Example 2)")
    else:
        print("\n  🟢 STATUS: Proof map is current")

    return True


def example_2_find_priority_files():
    """Example 2: Identify highest-priority files for review."""
    print("\n" + "=" * 70)
    print("EXAMPLE 2: Priority Review List")
    print("=" * 70)
    print("\nUse case: Which files should we document/refactor first?")
    print("Command: python3 tools/lean_proof_audit.py cohesion-ranking 10\n")

    result = run_command(
        "python3 Lean4-Automata/tools/lean_proof_audit.py cohesion-ranking"
    )
    if not result:
        return False

    # raw result is a list, not wrapped
    ranking = result[:10] if isinstance(result, list) else result.get("ranking", [])[:10]
    print(f"  📈 Top 10 modules by cohesion score:\n")
    print(f"  {'Module':<40} {'Score':>8} {'Status':<8}")
    print(f"  {'-' * 40} {'-' * 8} {'-' * 8}")

    for i, module in enumerate(ranking, 1):
        name = module.get("File", "")[:39]
        score = module.get("Score", 0)
        if score > 20:
            status = "🔴 HIGH"
        elif score > 10:
            status = "🟡 MED"
        else:
            status = "🟢 LOW"
        print(f"  {i:2}. {name:<37} {score:>8} {status:<8}")

    if ranking:
        top_file = ranking[0].get("File", "")
        print(f"\n  📌 ACTION: Start with {top_file}")
        print("     - Check imports vs Lean_Proof_Map.txt")
        print("     - Update documentation if needed")
        print("     - Consider refactoring if too many dependents")

    return True


def example_3_millennium_analysis():
    """Example 3: Analyze Millennium.lean dependency tree."""
    print("\n" + "=" * 70)
    print("EXAMPLE 3: Millennium.lean Dependency Analysis")
    print("=" * 70)
    print("\nUse case: How large is the dependency tree for Millennium?")
    print("Command: python3 tools/lean_proof_audit.py millennium-path\n")

    result = run_command(
        "python3 Lean4-Automata/tools/lean_proof_audit.py millennium-path"
    )
    if not result:
        return False

    target = result.get("Target", "")
    closure_size = result.get("DependencyClosureSize", 0)
    total_modules = result.get("TotalModules", 0)
    off_path = total_modules - closure_size if total_modules > 0 else 0

    print(f"  🎯 Target: {target}")
    print(f"  📦 Dependency closure size: {closure_size} modules")
    print(f"  🚫 Modules NOT on path to {target}: {off_path}")

    pct_on_path = (closure_size / total_modules * 100) if total_modules > 0 else 0
    print(f"  📊 Percentage of codebase: {pct_on_path:.1f}%")

    if closure_size > 30:
        print("\n  🔴 WARNING: Large dependency tree")
        print("     - Consider breaking into smaller modules")
        print("     - Analyze circular dependencies")
    elif closure_size > 15:
        print("\n  🟡 INFO: Moderate dependency tree")
        print("     - Consider lazy imports for optional features")
    else:
        print("\n  🟢 GOOD: Lean dependency tree")
        print("     - Core functionality is well-isolated")

    if off_path > 0:
        print(f"\n  ℹ️  {off_path} independent modules detected:")
        print("     - These can be developed/tested in isolation")
        print("     - May be candidates for separate packages")

    return True


def example_4_forum_integration():
    """Example 4: Create forum ticket (integration demo)."""
    print("\n" + "=" * 70)
    print("EXAMPLE 4: Forum Ticket Creation")
    print("=" * 70)
    print("\nUse case: Generate structured ticket for forum system")
    print("Command: python3 tools/forum_handlers.py lean_cohesion_ranking\n")

    result = run_command(
        'python3 Lean4-Automata/tools/forum_handlers.py lean_cohesion_ranking "{}"'
    )
    if not result:
        return False

    ticket = result.get("ticket", {})
    print(f"  ✅ Ticket created successfully\n")
    print(f"  🏷️  Title: {ticket.get('title', '')}")
    print(f"  📝 Type: {ticket.get('type', '')}")
    print(f"  ⏰ Created: {ticket.get('created_at', '')}")

    data = ticket.get("data", [])
    if isinstance(data, list) and len(data) > 0:
        print(f"\n  📊 Top module:")
        top = data[0]
        print(
            f"     {top.get('File')}: score {top.get('Score')} "
            f"({top.get('Imports')} imports, "
            f"{top.get('Dependents')} dependents)"
        )
    elif isinstance(data, dict):
        ranking = data.get("ranking", [])
        if ranking:
            print(f"\n  📊 Top module:")
            top = ranking[0]
            print(
                f"     {top.get('File')}: score {top.get('Score')} "
                f"({top.get('Imports')} imports, "
                f"{top.get('Dependents')} dependents)"
            )

    print(f"\n  ✅ Ticket ready for forum system")
    print(f"     - Can be stored in forum database")
    print(f"     - Can be sent to webhooks")
    print(f"     - Can be displayed in web UI")

    return True


def main():
    """Run all examples."""
    print("\n" + "=" * 70)
    print("LEAN PROOF AUDIT - REAL-WORLD EXAMPLES")
    print("=" * 70)
    print("These examples demonstrate practical use cases")
    print("for the proof audit, analysis, and ranking flows.")

    examples = [
        example_1_audit_health_check,
        example_2_find_priority_files,
        example_3_millennium_analysis,
        example_4_forum_integration,
    ]

    passed = sum(1 for ex in examples if ex())
    total = len(examples)

    print("\n" + "=" * 70)
    print(f"COMPLETED: {passed}/{total} examples")
    print("=" * 70)
    print("\nFor more information, see:")
    print("  - QUICK_START.md — Quick reference guide")
    print("  - LEAN_PROOF_AUDIT_FLOWS.md — Full documentation")
    print()

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
