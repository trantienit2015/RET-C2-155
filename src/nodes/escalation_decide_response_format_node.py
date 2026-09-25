"""AgentCore Platform v1.0 - RET-C2-155 EscalationDecideResponseFormatNode (inner subgraph, step 4).

Hybrid rule+LLM: unambiguous exception classes
(E_STOP/LOCAL_STOP/WARNING) use the deterministic escalation table; ambiguous
cases (exception_class=NONE, e.g. "robot behaving erratically near personnel")
require LLM judgment in context. Then assembles the final response, always
preserving the safety_warning verbatim from SafetyCheckNode.
"""

from typing import Any, ClassVar

from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event

from src.schemas.state import from_json, to_json
from src.services.service import build_response_fallback, decide_escalation_deterministic

_VALID_ESCALATIONS = {"full_evacuation", "local_stop", "no_escalation", "manual_review"}


class EscalationDecideResponseFormatNode(FunctionNode):
    """Decide escalation (deterministic floor + LLM for ambiguous cases) and assemble the response."""

    required_trust_level: ClassVar[TrustLevel] = TrustLevel.VERIFIED_EXTERNAL

    def __init__(self, llm: Any = None) -> None:
        super().__init__()
        self._llm = llm

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        exception_class = state.get("exception_class", "NONE")
        safety_warning = state.get("safety_warning")
        sop_passages = from_json(state.get("sop_passages"), [])
        parsed = from_json(state.get("user_input"), {})
        query = parsed.get("query", "") if isinstance(parsed, dict) else ""

        escalation_decision = decide_escalation_deterministic(exception_class)

        if escalation_decision is None:
            # Ambiguous case - requires LLM judgment in context.
            if self._llm is None:
                # No LLM configured: the deterministic "manual_review" fallback
                # is the only valid degradation path here.
                escalation_decision = "manual_review"
            else:
                # LLM is configured - a failed/malformed call must surface as
                # ERROR, not silently degrade to SUCCESS/manual_review (that
                # would mask a real provider outage as a normal decision).
                try:
                    prompt = f"Ambiguous robot-ops case (no matched exception code): {query}. Decide escalation: full_evacuation, local_stop, no_escalation, or manual_review."
                    # BaseLLM.complete() contract: messages: list -> dict (content/tool_calls/model/usage).
                    llm_response = self._llm.complete([{"role": "user", "content": prompt}])
                except Exception as e:
                    emit_trace_event(
                        "escalation_llm_call_failed",
                        {"error": str(e), "correlation_id": state.get("correlation_id", "")},
                        state,
                    )
                    return {
                        "status": AgentStatus.ERROR.value,
                        "error_log": [f"EscalationDecideResponseFormatNode: LLM call failed: {e}"],
                    }

                content = llm_response.get("content") if isinstance(llm_response, dict) else None
                candidate = content.strip().lower() if isinstance(content, str) else None
                if candidate not in _VALID_ESCALATIONS:
                    emit_trace_event(
                        "escalation_llm_response_invalid",
                        {
                            "raw_response_type": type(llm_response).__name__,
                            "correlation_id": state.get("correlation_id", ""),
                        },
                        state,
                    )
                    return {
                        "status": AgentStatus.ERROR.value,
                        "error_log": [
                            "EscalationDecideResponseFormatNode: LLM returned a non-actionable escalation decision"
                        ],
                    }
                escalation_decision = candidate

        response = build_response_fallback(sop_passages, escalation_decision, safety_warning)
        response["exception_class"] = exception_class

        emit_trace_event(
            "escalation_decided_response_formatted",
            {
                "escalation_decision": escalation_decision,
                "llm_used": self._llm is not None,
                "correlation_id": state.get("correlation_id", ""),
            },
            state,
        )

        return {
            "escalation_decision": escalation_decision,
            "final_response": to_json(response),
            "status": AgentStatus.SUCCESS.value,
        }
