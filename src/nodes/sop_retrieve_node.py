"""AgentCore Platform v1.0 - RET-C2-155 SOPRetrieveNode (inner subgraph, step 2).

VectorRAGAgent-pattern node (semantic retrieval over robot manufacturer
manuals). KB-backed only.
"""

from typing import Any, ClassVar

from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event

from src.schemas.state import from_json, to_json
from src.services.service import retrieve_sop_passages


class SOPRetrieveNode(FunctionNode):
    """Retrieve matching SOP passages from the robot manufacturer manual KB."""

    required_trust_level: ClassVar[TrustLevel] = TrustLevel.VERIFIED_EXTERNAL

    def __init__(self, kb: list[dict[str, Any]] | None = None) -> None:
        super().__init__()
        self._kb = kb or []

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        parsed = from_json(state.get("user_input"), {})
        query = parsed.get("query", "") if isinstance(parsed, dict) else ""
        robot_model = parsed.get("robot_model", "unknown") if isinstance(parsed, dict) else "unknown"

        if not query:
            return {"status": AgentStatus.ERROR.value, "error_log": ["SOPRetrieveNode: missing normalized query"]}

        sop_passages = retrieve_sop_passages(query, robot_model, self._kb)

        emit_trace_event(
            "sop_passages_retrieved",
            {
                "passage_count": len(sop_passages),
                "robot_model": robot_model,
                "correlation_id": state.get("correlation_id", ""),
            },
            state,
        )

        return {
            "sop_passages": to_json(sop_passages),
            "status": AgentStatus.SUCCESS.value,
        }
