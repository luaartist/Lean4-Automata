from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS_DIR))

from lean_proof_edit_guard import analyze_build_output, analyze_diff, build_report


BROKEN_CLEANUP_DIFF = """diff --git a/src/SU3Simplicity.lean b/src/SU3Simplicity.lean
index 1111111..2222222 100644
--- a/src/SU3Simplicity.lean
+++ b/src/SU3Simplicity.lean
@@ -410,8 +410,7 @@ theorem ad2_sum (v : Fin 8 -> R) :
   fin_cases i <;> fin_cases j <;>
     simp [ad2Vec, SU3.gellMannMatrix, Fin.sum_univ_eight]
   all_goals
-    ring_nf
-    try simp [Complex.I_sq]
+    ring_nf
@@ -594,7 +593,7 @@ lemma bracket_3_e7 (b : R) :
   all_goals
     have h_sqrtC : (Real.sqrt 3 : C) != 0 := by norm_num
-    field_simp [h_sqrtC]; ring_nf; simp [Complex.I_sq]; ring
+    field_simp [h_sqrtC]; ring_nf
"""

BROKEN_BUILD_OUTPUT = """error: src/SU3Simplicity.lean:135:2: unsolved goals
case a.a._hyg.0.0.0
|- I + I = 2 * I
error: src/SU3Simplicity.lean:420:13: No goals to be solved
error: src/SU3Simplicity.lean:409:8: (kernel) declaration has metavariables 'SU3Simplicity.ad2_sum'
warning: src/SU3Simplicity.lean:473:41: This simp argument is unused: Complex.I_sq
"""


def test_diff_classifier_flags_removed_proof_closers() -> None:
    result = analyze_diff(BROKEN_CLEANUP_DIFF)

    assert result["changed_files"] == ["src/SU3Simplicity.lean"]
    assert result["metrics"]["removed_proof_closers"] >= 3
    assert result["metrics"]["removed_critical_simplifiers"] >= 1
    assert result["metrics"]["risk_score"] >= 8
    assert any(signal["code"] == "proof_closer_count_regression" for signal in result["signals"])


def test_build_classifier_flags_lean_goal_regressions() -> None:
    result = analyze_build_output(BROKEN_BUILD_OUTPUT, returncode=1)
    signal_codes = {signal["code"] for signal in result["signals"]}

    assert result["error_count"] >= 3
    assert "unsolved_goals" in signal_codes
    assert "no_goals_to_be_solved" in signal_codes
    assert "metavariables" in signal_codes
    assert "unused_simp_args" in signal_codes


def test_guard_report_red_with_backup_evidence(tmp_path: Path) -> None:
    backup_path = tmp_path / "pre_rollback_agent_edits.zip"
    backup_path.write_text("placeholder", encoding="utf-8")

    result = build_report(
        project_root=tmp_path,
        diff_text=BROKEN_CLEANUP_DIFF,
        build_output=BROKEN_BUILD_OUTPUT,
        build_returncode=1,
        backup_path=str(backup_path),
    )

    assert result["guard"]["status"] == "red"
    assert result["guard"]["requires_rollback_consideration"] is True
    assert result["backup_path"] == str(backup_path)


@pytest.mark.parametrize("flow_params", [{}, {"run_build": False}])
def test_forum_handler_exposes_guard_flow(flow_params: dict[str, object]) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    command = [
        sys.executable,
        str(repo_root / "tools" / "forum_handlers.py"),
        "lean_proof_edit_guard",
        json.dumps(flow_params),
    ]

    completed = subprocess.run(
        command,
        cwd=repo_root,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["status"] == "ok"
    assert payload["ticket"]["title"].startswith("Lean Proof Edit Guard")
    assert payload["proof_edit_guard"]["tool"] == "lean_proof_edit_guard"
