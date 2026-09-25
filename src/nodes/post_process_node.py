"""AgentCore Platform v1.0 - RET-C2-155 OutputValidateNode (outer post_process slot).

S-3 PRESERVATION VARIANT (novel pattern): E-stop class
exceptions REQUIRE the hardcoded SAFETY_WARNING in the output - MUST NOT be
suppressable. This is a preservation check (reject output that DROPS required
safety-critical content), not a filtering check. `_extra_security_gate_output()`
is the only correct mechanism - a separate `compliance_check_node` is an
anti-pattern. The hook checks the assembled response's OWN
fields only, never cross-referencing separately-read sibling `state` fields.
On failure the output is dropped entirely
(status=ERROR, forcing a retry), never silently emitted without the warning.
"""

from typing import Any, ClassVar

from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event

from src.schemas.state import from_json, to_json
from src.services.service import SAFETY_WARNING


class OutputValidateNode(FunctionNode):
    """Assemble the final output; non-suppressible E-stop safety-warning preservation re-check."""

    required_trust_level: ClassVar[TrustLevel] = TrustLevel.ANONYMOUS

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        if state.get("status") in (AgentStatus.ERROR.value, AgentStatus.ERROR.value):
            return {"status": AgentStatus.ERROR.value}

        response = from_json(state.get("final_response"), None)
        if not isinstance(response, dict):
            return {"status": AgentStatus.ERROR.value, "error_log": ["OutputValidateNode: missing assembled response"]}

        emit_trace_event(
            "warehouse_robot_response_validated",
            {
                "exception_class": response.get("exception_class"),
                "escalation_decision": response.get("escalation_decision"),
                "correlation_id": state.get("correlation_id", ""),
            },
            state,
        )

        return {
            "formatted_output": response,
            "result": to_json(response),
            "status": AgentStatus.SUCCESS.value,
        }

    def _extra_security_gate_output(self, state: dict[str, Any]) -> dict[str, Any]:
        """Non-suppressible PRESERVATION re-check: E_STOP class must retain SAFETY_WARNING verbatim (own-dict fields only)."""
        response = from_json(state.get("result"), None)
        if not isinstance(response, dict):
            return state

        if response.get("exception_class") == "E_STOP" and SAFETY_WARNING not in (response.get("safety_warning") or ""):
            emit_trace_event("output_gate_safety_warning_dropped_blocked", {}, state)
            return {
                "status": AgentStatus.ERROR.value,
                "error_log": [
                    "Output gate: E_STOP class response is missing the mandatory safety warning - blocked (S-3 preservation variant)"
                ],
            }

        return state
