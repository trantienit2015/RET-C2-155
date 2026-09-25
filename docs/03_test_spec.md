# RET-C2-155 — Test Specification

## Test Strategy

Deterministic-core: `llm` is optional (ambiguous-case escalation judgment
only), so the full suite runs offline.

## Unit Tests (`tests/unit/test_nodes.py`)

| Node | Cases |
|---|---|
| QueryClassifyRobotModelFilterNode | success (query_type/robot_model classified); empty query→ERROR |
| ExceptionCodeLookupNode | known code matched → exception_class set; no code → NONE; missing input→ERROR; invalid query_type→ERROR (defense in depth) |
| SOPRetrieveNode | passages retrieved from KB; missing query→ERROR |
| SafetyCheckNode | E_STOP → SAFETY_WARNING assigned; other classes → None |
| EscalationDecideResponseFormatNode | deterministic escalation for E_STOP/LOCAL_STOP/WARNING; ambiguous (NONE) → manual_review fallback |
| OutputValidateNode | success; upstream error short-circuit; non-suppressible preservation hook blocks E_STOP response missing SAFETY_WARNING |

## Integration Tests (`tests/integration/test_graph.py`)

| ID | Test | Expected |
|---|---|---|
| I-1 | E-201 exception code query | SUCCESS; ≥5 nodes; exception_class=E_STOP; safety_warning present; escalation=full_evacuation |
| I-2 | E-105 exception code query | SUCCESS; exception_class=LOCAL_STOP; escalation=local_stop |
| I-3 | empty query | error |
| I-4 | ambiguous query (no matched code) | SUCCESS; escalation=manual_review (deterministic fallback, no LLM configured) |

## Proof-of-Boundary Tests (`tests/proof_of_boundary/`)

| PB-ID | Boundary | Test | Expected Result |
|-------|----------|------|----------------|
| PB-1 | BaseNode → EventEmitter | `emit_trace_event()` fires on every invocation path | No silent failures |
| PB-2 | State serialization | Post-invoke State is primitives only | No Pydantic/dataclass |
| PB-4 | Import isolation | No Level 0 imports | AST scan: 0 violations |
| PB-5 | Checkpoint safety | No JWT/Pydantic in checkpoint | Inspection pass |
| PB-6 | Invoke execution order | S-1 → node_start → S-2 → execute → S-3 → node_complete | Order verified |

## Business Logic Tests

| TC-ID | Test | Input | Expected Result |
|-------|------|-------|----------------|
| BL-01 | E-stop code recognition | "Geek+ AMR shows E-201 error near station 3" | exception_class=E_STOP, escalation=full_evacuation, safety_warning present |
| BL-02 | Local-stop code recognition | "sorting line E-105 jam" | exception_class=LOCAL_STOP, escalation=local_stop |
| BL-03 | Warning code recognition | "W-050 low battery" | exception_class=WARNING, escalation=no_escalation |
| BL-04 | Ambiguous ("erratic behavior") case | no matched exception code | escalation=manual_review deterministic fallback |

## Non-suppressible E-stop safety preservation tests (critical — novel S-3 pattern)

- E_STOP class responses ALWAYS carry the exact `SAFETY_WARNING` text; the
  post_process S-3 preservation hook checks the response's own fields only —
  never cross-references separate state fields.
- If the safety warning is ever dropped or altered before reaching output, the
  gate blocks the response entirely (`status=ERROR`), never silently emits an
  E_STOP response without the warning (unit + BL-01).
- Audit events never contain the raw query — query_type/robot_model/exception_class
  only.

## Test Execution Summary
- Execution date: 2026-07-07
- Total tests: see CI run
- Coverage: node-level unit + full-graph integration + PB-2/PB-4/PB-6
