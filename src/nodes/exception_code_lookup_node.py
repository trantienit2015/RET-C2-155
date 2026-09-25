"""AgentCore Platform v1.0 - RET-C2-155 ExceptionCodeLookupNode (inner subgraph, step 1).

Deterministic structured exception-code lookup (Tool).
Determines exception_class from a known-code match, defaulting to NONE when no
code is found (SOP-lookup-only queries).

Note: since AgentBaseGraph's pre_process -> main edge is unconditional, an
upstream pre_process ERROR still dispatches into this inner subgraph. The
query/query_type shape is therefore re-validated here, never
trusting that the upstream rejection
alone stopped the pipeline.
"""

from typing import Any, ClassVar

from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event

from src.schemas.state import from_json, to_json
from src.services.service import VALID_QUERY_TYPES, lookup_exception_code


class ExceptionCodeLookupNode(FunctionNode):
    """Look up the exception code and determine the exception class."""

    required_trust_level: ClassVar[TrustLevel] = TrustLevel.VERIFIED_EXTERNAL

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        parsed = from_json(state.get("user_input"), None)
        if not isinstance(parsed, dict):
            return {
                "status": AgentStatus.ERROR.value,
                "error_log": ["ExceptionCodeLookupNode: missing validated input"],
            }

        query = parsed.get("query", "")
        query_type = parsed.get("query_type", "")
        if query_type not in VALID_QUERY_TYPES:
            return {
                "status": AgentStatus.ERROR.value,
                "error_log": [f"ExceptionCodeLookupNode: invalid query_type '{query_type}'"],
            }

        match = lookup_exception_code(query)
        exception_class = match["exception_class"] if match else "NONE"

        emit_trace_event(
            "exception_code_lookup_completed",
            {
                "exception_class": exception_class,
                "matched": match is not None,
                "correlation_id": state.get("correlation_id", ""),
            },
            state,
        )

        return {
            "exception_match": to_json(match),
            "exception_class": exception_class,
            "status": AgentStatus.SUCCESS.value,
        }
