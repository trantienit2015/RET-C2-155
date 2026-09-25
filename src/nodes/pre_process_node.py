"""AgentCore Platform v1.0 - RET-C2-155 QueryClassifyRobotModelFilterNode (outer pre_process slot).

Normalize the robot-ops question; classify query type (finite types) and
filter the applicable robot model.
"""

from typing import Any, ClassVar

from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event

from src.schemas.state import to_json
from src.services.service import classify_query_type, filter_robot_model, normalize_query


class QueryClassifyRobotModelFilterNode(FunctionNode):
    """Normalize the query, classify query type, and filter the robot model."""

    required_trust_level: ClassVar[TrustLevel] = TrustLevel.VERIFIED_EXTERNAL

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        user_input = state.get("user_input", "")

        normalized, error = normalize_query(user_input)
        if error:
            return {
                "status": AgentStatus.ERROR.value,
                "error_log": [f"QueryClassifyRobotModelFilterNode: {error}"],
            }

        query_type = classify_query_type(normalized)
        robot_model = filter_robot_model(normalized)

        emit_trace_event(
            "warehouse_robot_query_received",
            {"query_type": query_type, "robot_model": robot_model, "correlation_id": state.get("correlation_id", "")},
            state,
        )

        return {
            "query_type": query_type,
            "robot_model": robot_model,
            "validated_input": to_json({"query": normalized, "query_type": query_type, "robot_model": robot_model}),
            "status": AgentStatus.SUCCESS.value,
        }
