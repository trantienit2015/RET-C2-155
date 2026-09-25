"""AgentCore Platform v1.0 - RET-C2-155 outer graph (Cat 2).

Cat 2: outer AgentBaseGraph with the fixed 5-node backbone. Domain complexity
is encapsulated in WarehouseRobotOpsGraphNode (the `main` slot), which wraps
the inner WarehouseRobotOpsWorkflowGraph. Do NOT override add_edges().

Backbone: initialize -> pre_process(QueryClassifyRobotModelFilter) -> main(GraphNode)
          -> post_process(OutputValidate) -> finalize

WarehouseRobotOpsGraphNode lives here (not under src/nodes/) - the PB-6
invoke-order test only discovers BaseNode subclasses under src/nodes/, and a
GraphNode's __call__ intentionally delegates S-2/S-3 content gating to the
inner subgraph's entry node. S-1 (required_trust_level) is still enforced by
the inherited BaseNode.__call__ on this class itself. This placement is
compensated by tests/proof_of_boundary/test_pb_graphnode_boundary.py, which
covers the S-1 gate, extract_input/merge_output field mapping, and the
inner-entry-node delegation explicitly.
"""

from typing import Any, ClassVar, cast

from framework.graph.agent_base_graph import AgentBaseGraph
from framework.nodes.graph_node import GraphNode
from framework.schemas.agent_state import AgentState
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event

from src.nodes.post_process_node import OutputValidateNode
from src.nodes.pre_process_node import QueryClassifyRobotModelFilterNode
from src.schemas.state import State


class WarehouseRobotOpsGraphNode(GraphNode):
    """Wraps the inner warehouse robot ops exception-handling workflow (Cat 2 composition)."""

    # S-1: outer main-slot wrapper - first node in the outer backbone receiving
    # caller input; must match agent.yaml required_trust_level and sibling
    # outer FunctionNodes (pre_process/post_process), not the inner ANONYMOUS trust.
    required_trust_level: ClassVar[TrustLevel] = TrustLevel.VERIFIED_EXTERNAL
    # "propagate": re-raise inner errors as SubgraphError (fail fast - default).
    error_strategy: ClassVar[str] = "propagate"
    # No HITL in this template.
    propagate_hitl: ClassVar[bool] = False

    def __init__(self, llm: Any = None, kb: Any = None) -> None:
        super().__init__()
        self._llm = llm
        self._kb = kb or []

    def get_subgraph(self) -> Any:
        from src.graph.domain_workflow_graph import WarehouseRobotOpsWorkflowGraph

        sg = WarehouseRobotOpsWorkflowGraph(config=self._parent_config())
        sg.compile()
        return sg

    def extract_input(self, state: AgentState) -> str:
        emit_trace_event(
            "warehouse_robot_ops_workflow_dispatched", {"correlation_id": state.get("correlation_id", "")}, state
        )
        return cast(str, state.get("validated_input", state.get("user_input", "")))

    def merge_output(self, state: AgentState, sub_result: dict[str, Any]) -> dict[str, Any]:
        emit_trace_event(
            "warehouse_robot_ops_workflow_completed",
            {"correlation_id": state.get("correlation_id", ""), "status": str(sub_result.get("status"))},
            state,
        )
        return {
            "exception_class": sub_result.get("exception_class"),
            "exception_match": sub_result.get("exception_match"),
            "sop_passages": sub_result.get("sop_passages"),
            "safety_warning": sub_result.get("safety_warning"),
            "escalation_decision": sub_result.get("escalation_decision"),
            "final_response": sub_result.get("final_response"),
            "result": sub_result.get("output"),
            "status": sub_result.get("status"),
        }

    def _parent_config(self) -> dict[str, Any]:
        return {"llm": self._llm, "kb": self._kb}


class RETC2155WarehouseRobotOpsQA(AgentBaseGraph):
    """RET-C2-155 - Retail Warehouse Physical AI Operations & Exception Handling Q&A Agent (Cat 2)."""

    @property
    def name(self) -> str:
        return "ret-c2-155"

    @property
    def state_schema(self) -> type:
        return State

    def register_nodes(self) -> None:
        super().register_nodes()  # injects initialize + finalize

        llm = self.config.get("llm")
        kb = self.config.get("kb")

        self._nodes["pre_process"] = QueryClassifyRobotModelFilterNode()
        self._nodes["main"] = WarehouseRobotOpsGraphNode(llm=llm, kb=kb)
        self._nodes["post_process"] = OutputValidateNode()

    # add_edges() is NOT overridden - backbone wiring belongs to the framework.


# Alias for agent.yaml module:"src.graph" resolution (AgentRegistry / api/server.py).
Graph = RETC2155WarehouseRobotOpsQA
