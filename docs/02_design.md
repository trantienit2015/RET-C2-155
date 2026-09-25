# Template Design Specification

## Position in AgentCore Architecture

- **Agent Class**: `RETC2155WarehouseRobotOpsQA`
- **L1 Base**: AgentBaseGraph
- **Three-Layer Separation**:
  - State: flat TypedDict composition (no Pydantic — msgpack incompatible)
  - Node: L1 inheritance (Template Method: `execute(self, state: dict) -> dict` override only)
  - Graph: composition (`register_nodes()` for node substitution)

## Architecture Overview

Cat 2: outer `AgentBaseGraph` (fixed 5-node backbone) + `GraphNode` in the `main`
slot wrapping an inner `BaseGraph` (4-step linear domain workflow), per the
locked node-type table.

### Node Configuration (outer)

| Node | Responsibility | Input State | Output State | Inherits/Overrides |
|------|---------------|-------------|--------------|-------------------|
| initialize | schema_version/session_id/trust_level | - | - | InitializeNode (default) |
| pre_process | `QueryClassifyRobotModelFilterNode` — normalize query, classify query type, filter robot model | `user_input` | `query_type`, `robot_model`, `validated_input` | FunctionNode |
| main | `WarehouseRobotOpsGraphNode` — wraps inner workflow | `validated_input` | `exception_class`, `exception_match`, `sop_passages`, `safety_warning`, `escalation_decision`, `final_response` | GraphNode |
| post_process | `OutputValidateNode` — S-3 PRESERVATION VARIANT re-check | `final_response` | `formatted_output`, `result` | FunctionNode |
| finalize | response_metadata, total_time_ms | - | - | FinalizeNode (default) |

### Node Configuration (inner, per the locked node-type table)

| Node | Type | Responsibility |
|------|------|-----------------|
| `ExceptionCodeLookupNode` | Tool — structured lookup | Deterministic exception-code → known-SOP table match; determines exception_class; re-checks query_type validity (the pre_process→main edge is unconditional) |
| `SOPRetrieveNode` | VectorRAGAgent pattern | Semantic retrieval over robot manufacturer manuals (Geek+/MiR/GreyOrange/Mujin), scoped by robot_model |
| `SafetyCheckNode` | Tool (rule-based) | E_STOP class → hardcoded SAFETY_WARNING, never suppressable, never LLM-derived |
| `EscalationDecideResponseFormatNode` | Hybrid rule+LLM | Unambiguous exception classes use the deterministic escalation table; ambiguous cases (exception_class=NONE) require LLM judgment in context; assembles the final response |

### Data Flow

```
START → initialize → pre_process → main → {route} → post_process → finalize → END
                                            ↓ (retry)
                                          pre_process

Inner (main slot): START → exception_code_lookup → sop_retrieve
                         → safety_check → escalation_decide_response_format → END
```

### State Definition

| Field | Type | Purpose | Required |
|-------|------|---------|----------|
| `query_type` | str | "exception_code"/"sop_lookup"/"escalation"/"safety" | NotRequired |
| `robot_model` | str | "geekplus"/"mir"/"greyorange"/"mujin"/"unknown" | NotRequired |
| `exception_class` | str | "E_STOP"/"LOCAL_STOP"/"WARNING"/"NONE" | NotRequired |
| `exception_match` | str\|None (JSON) | {code, exception_class, known_sop} | NotRequired |
| `sop_passages` | str\|None (JSON) | list[{manual_section, snippet}] | NotRequired |
| `safety_warning` | str\|None | mandatory hardcoded warning for E_STOP class | NotRequired |
| `escalation_decision` | str | "full_evacuation"/"local_stop"/"no_escalation"/"manual_review" | NotRequired |
| `final_response` | str\|None (JSON) | assembled SOP resolution + safety warning + escalation decision | NotRequired |

**State Constraints (mandatory):**
- Flat TypedDict only (primitives + JSON-serializable types)
- No JWT, API keys, credentials in State (checkpoint DB leakage)
- InvocationContext via `config["configurable"]` only (not in State)
- No Pydantic models, dataclass, arbitrary Python objects (msgpack incompatible)

## S-3 Safety Preservation — E-Stop Class (novel pattern)

E-stop class exceptions REQUIRE the hardcoded `SAFETY_WARNING` in the output -
MUST NOT be suppressable. `OutputValidateNode._extra_security_gate_output()` is
a **preservation variant**: it rejects output that DROPS the required
safety-critical content (not a filtering check). A separate
`compliance_check_node` is an anti-pattern; the preservation
check is the only correct mechanism.

> **Reuse note:** this E-stop safety preservation pattern is a candidate for a
> standardized S-3 safety-critical preservation variant in other physical-AI
> templates.

## Framework Utilization

### Shared Components Used
- [x] InvocationContext (correlation_id, session_id, permissions, credential handle)
- [x] S-3 preservation variant: `OutputValidateNode._extra_security_gate_output()`
      — non-suppressible re-check that E_STOP class responses retain
      `SAFETY_WARNING` verbatim
- [x] S-4: `emit_trace_event()` — domain events at every node (query received,
      exception looked up, SOP retrieved, safety checked, escalation decided/
      response validated)

> **S-2/S-3 gate behaviour by node type (ADR-017):**
> - `FunctionNode` subclass → framework `@final` gate always runs automatically;
>   extend via `_extra_security_gate_input()` / `_extra_security_gate_output()` only
> - `GraphNode` / `RemoteAgentNode` → deliberate no-op (upstream or remote node's gate already applied)
> - Custom `BaseNode` subclass → must implement `_security_gate_input()` and
>   `_security_gate_output()` directly (`@abstractmethod` — omission raises `TypeError` at instantiation)

### Composition Pattern

- **Pattern**: GraphNode (subgraph)
- **Composition target**: `WarehouseRobotOpsWorkflowGraph` (inner `BaseGraph`)
- **Error propagation strategy**: propagate (fail fast; no HITL in this template)

## Import Isolation Confirmation
- [x] Template does not import agenticstar-platform SDK (Level 0)
- [x] Import targets: framework/ and shared/ only (no agents/base/ required)

## Design Decision Record

| Decision | Option A | Option B | Chosen | Rationale |
|----------|----------|----------|--------|-----------|
| L1 base type | AgentBaseGraph | AutonomousBaseGraph | AgentBaseGraph | Fixed multi-step exception-resolution workflow, no self-directed loop needed |
| Composition pattern | Standalone nodes | GraphNode (subgraph) | GraphNode | Cat 2 domain complexity (4-step inner workflow) encapsulated per scaffold convention |
| Safety warning mechanism | Separate compliance_check_node | S-3 `_extra_security_gate_output()` preservation | Preservation gate | `compliance_check_node` is an anti-pattern; preservation gate is the correct mechanism |
| Escalation decision | Pure deterministic | Hybrid rule+LLM | Hybrid | Unambiguous cases (E_STOP/LOCAL_STOP/WARNING) use the deterministic table; ambiguous cases require LLM judgment in context |
