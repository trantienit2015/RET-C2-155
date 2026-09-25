"""AgentCore Platform v1.0 - RET-C2-155 SafetyCheckNode (inner subgraph, step 3).

Deterministic rule-based safety check (Tool). E_STOP
class ALWAYS produces the hardcoded SAFETY_WARNING - never suppressable, never
LLM-derived. This is the source-of-truth safety-warning assignment; the
non-suppressible S-3 preservation gate in OutputValidateNode re-verifies it
survives to the final output.
"""

from typing import Any, ClassVar

from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event

from src.services.service import check_safety


class SafetyCheckNode(FunctionNode):
    """Deterministically assign the mandatory safety warning for E_STOP class exceptions."""

    required_trust_level: ClassVar[TrustLevel] = TrustLevel.VERIFIED_EXTERNAL

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        exception_class = state.get("exception_class", "NONE")

        safety_warning = check_safety(exception_class)

        emit_trace_event(
            "safety_check_completed",
            {
                "exception_class": exception_class,
                "warning_assigned": safety_warning is not None,
                "correlation_id": state.get("correlation_id", ""),
            },
            state,
        )

        return {
            "safety_warning": safety_warning,
            "status": AgentStatus.SUCCESS.value,
        }
