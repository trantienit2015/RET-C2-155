"""AgentCore Platform v1.0 - RET-C2-155 inner domain workflow graph.

Cat 2 inner graph: exception-code lookup -> SOP retrieval -> safety check ->
escalation decide + response format. Instantiated by
WarehouseRobotOpsGraphNode.get_subgraph() in graph.py.

Pipeline (linear, fail-fast on ERROR):
    START -> exception_code_lookup -> sop_retrieve -> safety_check
          -> escalation_decide_response_format -> END
"""

from typing import Any
from langgraph.graph import END, START

from framework.graph.base_graph import BaseGraph
from framework.schemas.agent_state import AgentState
from framework.schemas.agent_status import AgentStatus

from src.nodes.escalation_decide_response_format_node import EscalationDecideResponseFormatNode
from src.nodes.exception_code_lookup_node import ExceptionCodeLookupNode
from src.nodes.safety_check_node import SafetyCheckNode
from src.nodes.sop_retrieve_node import SOPRetrieveNode
from src.schemas.state import State


class WarehouseRobotOpsWorkflowGraph(BaseGraph):
    """Inner graph for the RET-C2-155 warehouse robot ops exception-handling workflow."""

    @property
    def name(self) -> str:
        return "warehouse-robot-ops-workflow"

    @property
    def state_schema(self) -> type:
        return State

    def _validate_config(self) -> None:
        # No mandatory config: llm and kb are optional (deterministic fallback exists).
        pass

    def register_nodes(self) -> None:
        # No super() - BaseGraph.register_nodes() is abstract.
        llm = self.config.get("llm")
        kb = self.config.get("kb")

        self._nodes["exception_code_lookup"] = ExceptionCodeLookupNode()
        self._nodes["sop_retrieve"] = SOPRetrieveNode(kb=kb)
        self._nodes["safety_check"] = SafetyCheckNode()
        self._nodes["escalation_decide_response_format"] = EscalationDecideResponseFormatNode(llm=llm)

    def add_edges(self) -> None:
        self._sg.add_edge(START, "exception_code_lookup")
        self._sg.add_conditional_edges(
            "exception_code_lookup",
            lambda s: END if self._is_error(s) else "sop_retrieve",
            {"sop_retrieve": "sop_retrieve", END: END},
        )
        self._sg.add_conditional_edges(
            "sop_retrieve",
            lambda s: END if self._is_error(s) else "safety_check",
            {"safety_check": "safety_check", END: END},
        )
        self._sg.add_conditional_edges(
            "safety_check",
            lambda s: END if self._is_error(s) else "escalation_decide_response_format",
            {"escalation_decide_response_format": "escalation_decide_response_format", END: END},
        )
        self._sg.add_edge("escalation_decide_response_format", END)

    @staticmethod
    def _is_error(state: AgentState) -> bool:
        return state.get("status") in (AgentStatus.ERROR.value, AgentStatus.ERROR.value)

    def route(self, state: AgentState) -> str:
        return END if self._is_error(state) else "escalation_decide_response_format"

    def get_output(self, state: AgentState) -> dict[str, Any]:
        return {
            "exception_class": state.get("exception_class"),
            "exception_match": state.get("exception_match"),
            "sop_passages": state.get("sop_passages"),
            "safety_warning": state.get("safety_warning"),
            "escalation_decision": state.get("escalation_decision"),
            "final_response": state.get("final_response"),
            "output": state.get("final_response"),
            "status": state.get("status"),
            "trace_id": state.get("trace_id"),
            "correlation_id": state.get("correlation_id"),
            "node_history": state.get("node_history", []),
        }
