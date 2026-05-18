# Lean Proof Audit Forum Flows

This document describes the conversion of Wolfram Language proof audit and import graph logic into Python, and its integration with the Lean4-Automata forum ticket system.

## Overview

Four Wolfram Language modules were converted to Python:
1. **LeanProofMapAudit.wl** → Audit summary (file counts, mismatches)
2. **LeanImportGraphLib.wl** → Import graph and dependency closures
3. **LeanMillenniumPathChart.wl** → Dependency paths to Millennium.lean
4. **LeanCohesionSeams.wl** → Module ranking by cohesion score

All logic is now available as callable Python methods and forum flows that return structured JSON tickets.

## Architecture

### Core Module: `tools/lean_proof_audit.py`

The main implementation class `LeanImportGraph` provides:

```python
class LeanImportGraph:
    # File discovery
    get_lean_file_paths() → List[Path]
    get_lean_file_names() → List[str]
    get_known_files() → Dict[str, Path]
    
    # Import analysis
    extract_import_targets(text, known_files) → List[str]
    get_import_association() → Dict[str, List[str]]
    get_reverse_import_association() → Dict[str, List[str]]
    
    # Proof map parsing
    get_proof_map_association() → Dict[str, List[str]]
    
    # Audit logic
    get_audit_association() → Dict[str, Any]
    get_audit_summary() → Dict[str, Any]
    
    # Dependency analysis
    get_dependency_closure(target) → List[str]
    get_dependents_closure(target) → List[str]
    get_modules_off_target_path(target) → List[str]
    get_shortest_paths_to_target(target) → Dict[str, Optional[List[str]]]
    
    # Millennium analysis
    get_millennium_path_report(target, core) → Dict[str, Any]
    
    # Cohesion ranking
    get_aggregator_ranking(limit) → List[Dict[str, Any]]
```

### Forum Integration: `tools/forum_handlers.py`

Provides high-level handlers that wrap the core logic for forum consumption:

```python
handler_lean_proof_audit(report_type) → Dict[str, Any]
handler_lean_millennium_paths() → Dict[str, Any]
handler_lean_cohesion_ranking(limit) → Dict[str, Any]
execute_flow(flow_name, params) → Dict[str, Any]
```

Each handler creates a structured **Ticket** containing:
- Title and description
- Structured audit/analysis data
- Metadata (project root, timestamp)

### API Integration: `app/audit/router.py`

FastAPI router providing REST endpoints:

```
GET  /api/v1/audit/summary?report_type=summary|full
GET  /api/v1/audit/millennium?target=Millennium.lean
GET  /api/v1/audit/ranking?limit=15
POST /api/v1/audit/execute?flow_name=X&params={"key":"val"}
```

## Command-Line Usage

### Direct Python Execution

```bash
# Audit summary (file counts only)
python3 Lean4-Automata/tools/lean_proof_audit.py audit-summary

# Full audit (includes mismatch details)
python3 Lean4-Automata/tools/lean_proof_audit.py audit-full

# Millennium dependency analysis
python3 Lean4-Automata/tools/lean_proof_audit.py millennium-path

# Module cohesion ranking
python3 Lean4-Automata/tools/lean_proof_audit.py cohesion-ranking

# Proof edit guard with live build classification
python3 Lean4-Automata/tools/lean_proof_edit_guard.py --run-build
```

### Forum Handler Execution

```bash
# Create audit summary ticket
python3 Lean4-Automata/tools/forum_handlers.py lean_proof_audit '{"report_type":"summary"}'

# Create millennium paths ticket
python3 Lean4-Automata/tools/forum_handlers.py lean_millennium_paths '{}'

# Create cohesion ranking ticket (top 10)
python3 Lean4-Automata/tools/forum_handlers.py lean_cohesion_ranking '{"limit":10}'

# Create proof edit guard ticket
python3 Lean4-Automata/tools/forum_handlers.py lean_proof_edit_guard '{"run_build":false}'

# List available flows
python3 Lean4-Automata/tools/forum_handlers.py
```

## Audit Output Examples

### Audit Summary

```json
{
  "ActualSrcFiles": 66,
  "DocumentedEntries": 63,
  "CommonFiles": 63,
  "MissingInDoc": 3,
  "MissingInSrc": 0,
  "MismatchCount": 55
}
```

**Interpretation:**
- 66 `.lean` files exist in `src/`
- 63 are documented in `Lean_Proof_Map.txt`
- 3 files not yet documented
- 55 files have import differences between actual and documented

### Millennium Path Report

```json
{
  "Target": "Millennium.lean",
  "DependencyClosureSize": 5,
  "DependencyClosure": ["Millennium.lean", "MillenniumCore.lean", "Quantum.lean", ...],
  "AllModulesReachMillennium": false,
  "ModulesOffMillenniumPath": [61 files...]
}
```

**Interpretation:**
- Only 5 files needed to reach Millennium.lean from its dependencies
- 61 files are not on the path to Millennium (independent modules)
- Not all modules ultimately import Millennium

### Cohesion Ranking (Top 5)

```json
[
  {
    "File": "QuantumInfinityHarness.lean",
    "Imports": 12,
    "Dependents": 2,
    "DocDrift": 14,
    "Score": 28
  },
  {
    "File": "OsterwalderSchraderReconstruction.lean",
    "Imports": 7,
    "Dependents": 3,
    "DocDrift": 8,
    "Score": 18
  },
  ...
]
```

**Interpretation:**
- **Score** = Imports + Dependents + DocDrift (higher = more central/problematic)
- **DocDrift** = number of import mismatches (high = needs documentation update)
- QuantumInfinityHarness is the highest-priority module for review

### Proof Edit Guard

```json
{
  "guard": {
    "status": "red",
    "action": "rollback_or_repair_before_next_edit",
    "requires_rollback_consideration": true
  },
  "diff": {
    "metrics": {
      "removed_proof_closers": 4,
      "removed_critical_simplifiers": 2,
      "risk_score": 23
    }
  },
  "build": {
    "error_count": 3,
    "signals": [
      {"code": "unsolved_goals"},
      {"code": "no_goals_to_be_solved"},
      {"code": "metavariables"}
    ]
  }
}
```

**Interpretation:** This flow is designed for the exact failure mode where a warning-only Lean file is edited by broad tactic cleanup and the edit removes proof-closing context. It emits a rollback-oriented red ticket when build diagnostics appear after proof-edit risk.

## Forum Flow Registration

Flows are registered in `ui/flow_definitions.json`:

```json
{
  "name": "lean_proof_audit",
  "description": "Audit Lean proof map: compare actual imports vs documented",
  "handler_type": "subprocess",
  "command_template": "cd $PROJECT_ROOT && python3 Lean4-Automata/tools/lean_proof_audit.py audit-$REPORT_TYPE",
  "enabled": true,
  "tags": ["lean", "audit", "imports", "proof-map"]
}
```

Forum users can invoke flows via:
- CLI: `forum-cli run lean_proof_audit --params report_type=summary`
- REST API: `POST /forum/flows/lean_proof_audit`
- Web UI: Flow dropdown + parameter form

## Test Suite

Comprehensive test suite validates all flows:

```bash
python3 Lean4-Automata/test_forum_flows.py
```

Tests verify:
- ✓ Audit summary execution and ticket creation
- ✓ Audit full execution with mismatch details
- ✓ Millennium path analysis
- ✓ Cohesion ranking (top N)
- ✓ JSON structure validation
- ✓ All flows return valid tickets

## Implementation Details

### Porting Strategy

**Wolfram → Python Equivalents:**

| Wolfram | Python | Purpose |
|---------|--------|---------|
| `LeanFilePaths[]` | `get_lean_file_paths()` | Discover .lean files |
| `LeanImportAssociation[]` | `get_import_association()` | Parse import statements |
| `LeanReverseImportAssociation[]` | `get_reverse_import_association()` | Build reverse dependency map |
| `LeanProofMapAssociation[]` | `get_proof_map_association()` | Parse Lean_Proof_Map.txt |
| `LeanProofMapAuditAssociation[]` | `get_audit_association()` | Compare actual vs documented |
| `LeanDependencyClosure[]` | `get_dependency_closure()` | Forward dependency closure (BFS) |
| `LeanDependentsClosure[]` | `get_dependents_closure()` | Reverse dependency closure (BFS) |
| `LeanAggregatorRanking[]` | `get_aggregator_ranking()` | Score and rank modules |

### Algorithms

**Dependency Closure (BFS):**
```python
closure = {target}
queue = [target]
while queue:
    current = queue.pop(0)
    for dep in imports[current]:
        if dep not in closure:
            closure.add(dep)
            queue.append(dep)
return sorted(closure)
```

**Audit Comparison:**
```python
for filename in common_files:
    actual_imports = set(imports[filename])
    documented_imports = set(proof_map[filename])
    if actual_imports != documented_imports:
        mismatches[filename] = {
            "OnlyInActual": actual - documented,
            "OnlyInDoc": documented - actual
        }
```

## Performance Notes

- **File parsing:** O(N) where N = number of .lean files (typically 60-70)
- **Import resolution:** O(E) where E = import edges (typically 200-300)
- **Dependency closure:** O(V+E) BFS per target (V = vertices, E = edges)
- **Audit comparison:** O(N × M) where M = avg imports per file (~5)

**Total execution time:** < 1 second for typical codebase

## Limitations & Fallbacks

1. **Import regex:** Uses simple pattern matching; may not catch all Lean 4 syntax edge cases
   - Fallback: Returns empty import list if parsing fails
2. **Proof map format:** Regex-based parsing of Lean_Proof_Map.txt
   - Fallback: Skips malformed entries
3. **Circular imports:** Handled correctly by BFS with visited set
4. **Missing files:** Silently skipped in audit (not considered errors)

## Future Enhancements

- [ ] Streaming JSON output for large analyses
- [ ] Export to GraphML format for visualization
- [ ] Delta audits (compare against previous run)
- [ ] Integration with Lean 4 LSP for semantic import analysis
- [ ] Webhook notifications on drift threshold breach
- [ ] Historical tracking (audit database)

## Related Files

- Core logic: `tools/lean_proof_audit.py` (15KB)
- Forum handlers: `tools/forum_handlers.py` (7KB)
- API router: `app/audit/router.py` (5KB)
- Flow definitions: `ui/flow_definitions.json` (updated)
- Tests: `test_forum_flows.py` (4KB)
- Original Wolfram: `*.wl` files (reference)

---

**Status:** ✅ Production Ready
- All 4 original Wolfram modules successfully ported
- End-to-end tests passing
- Forum integration complete
- JSON output validated
