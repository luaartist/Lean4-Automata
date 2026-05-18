from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_module():
    module_path = Path(__file__).resolve().parents[1] / "tools" / "wolfram_llm_synthesis.py"
    spec = importlib.util.spec_from_file_location("wolfram_llm_synthesis", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


wolfram_llm_synthesis = _load_module()


def test_missing_wolframscript_short_circuits_without_database() -> None:
    result = wolfram_llm_synthesis.run_synthesis(
        database_url="postgresql://unused:unused@127.0.0.1:1/unused",
        project_id=1,
        wolframscript="/definitely/missing/wolframscript",
        limit=1,
    )

    assert result["status"] == "wolfram_unavailable"
    assert result["attempted"] == 0
    assert result["updated"] == 0
    assert "no database connection" in result["message"]


def test_prompt_payload_truncates_raw_text() -> None:
    row = wolfram_llm_synthesis.CompanionMapRow(
        id=7,
        module_name="Alpha.Beta",
        wolfram_path="wolfram_lean_maps/Alpha.Beta.wl",
        file_hash="abc123",
        raw_text="0123456789",
    )

    payload = wolfram_llm_synthesis.build_prompt_payload(row, max_raw_chars=4, prompt_version="test-v1")

    assert payload["raw_text"] == "0123"
    assert payload["raw_text_chars"] == 10
    assert payload["raw_text_truncated"] is True
    assert payload["prompt_version"] == "test-v1"


def test_parse_wolfram_stdout_accepts_last_json_line() -> None:
    parsed, error = wolfram_llm_synthesis.parse_wolfram_stdout('loading message\n{"status":"ok","text":"done"}\n')

    assert error is None
    assert parsed == {"status": "ok", "text": "done"}


def test_build_wolfram_code_uses_llmsynthesize() -> None:
    code = wolfram_llm_synthesis.build_wolfram_code(
        {
            "module_name": "Alpha.Beta",
            "wolfram_path": "Alpha.Beta.wl",
            "raw_text": "Print[1]",
            "prompt_version": "test-v1",
        }
    )

    assert "LLMSynthesize" in code
    assert "FromCharacterCode" in code
    assert "Print[1]" not in code