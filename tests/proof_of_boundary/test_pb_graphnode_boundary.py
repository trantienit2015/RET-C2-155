# PB-6 gap-fill: outer GraphNode security boundary.
# PB-6 (test_pb_invoke_order.py) only discovers BaseNode subclasses under
# src/nodes/. WarehouseRobotOpsGraphNode lives in src/graph/graph.py (correct
# per the Cat 2 pattern, so a single-node probe does not drag in the whole
# inner subgraph) - but that placement does not exempt it from S-1/boundary
# proof. This file is the required compensating test (PB-6
# gap-fill spec).

from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel

from src.graph.graph import WarehouseRobotOpsGraphNode
from src.nodes.exception_code_lookup_node import ExceptionCodeLookupNode


class TestGraphNodeS1TrustGate:
    """S-1: the outer GraphNode is the first node to receive caller input in
    the `main` slot - it must enforce required_trust_level like any other
    outer node, not rely on the inner subgraph to reject low-trust callers."""

    def test_anonymous_caller_denied_before_execute(self, monkeypatch):
        node = WarehouseRobotOpsGraphNode()
        assert node.required_trust_level == TrustLevel.VERIFIED_EXTERNAL

        called = {"execute": False}
        monkeypatch.setattr(
            WarehouseRobotOpsGraphNode,
            "execute",
            lambda self, state: called.__setitem__("execute", True) or {},
        )

        state = {
            "caller_trust_level": TrustLevel.ANONYMOUS.value,
            "correlation_id": "pb-graphnode-boundary-test",
        }
        result = node(state)

        assert called["execute"] is False, "execute() must not run when S-1 trust gate denies the caller"
        assert result["status"] == AgentStatus.ERROR.value
        assert "S-1 trust gate denied" in result["error_log"][0]

    def test_verified_external_caller_allowed_through_gate(self, monkeypatch):
        node = WarehouseRobotOpsGraphNode()

        called = {"execute": False}
        monkeypatch.setattr(
            WarehouseRobotOpsGraphNode,
            "execute",
            lambda self, state: called.__setitem__("execute", True) or {"status": AgentStatus.SUCCESS.value},
        )

        state = {
            "caller_trust_level": TrustLevel.VERIFIED_EXTERNAL.value,
            "correlation_id": "pb-graphnode-boundary-test",
        }
        node(state)

        assert called["execute"] is True, "execute() must run once the caller meets required_trust_level"


class TestGraphNodeBoundaryMapping:
    """Criterion #9: extract_input/merge_output must map fields explicitly -
    no raw pass-through of the parent state or the subgraph result dict."""

    def test_extract_input_reads_only_validated_input(self):
        node = WarehouseRobotOpsGraphNode()
        state = {
            "validated_input": '{"query": "E-201 alarm"}',
            "user_input": "raw unrelated text",
            "some_unrelated_field": "must not leak into the subgraph call",
        }
        assert node.extract_input(state) == '{"query": "E-201 alarm"}'

    def test_extract_input_falls_back_to_user_input(self):
        node = WarehouseRobotOpsGraphNode()
        state = {"user_input": "fallback text"}
        assert node.extract_input(state) == "fallback text"

    def test_merge_output_maps_explicit_fields_only(self):
        node = WarehouseRobotOpsGraphNode()
        sub_result = {
            "exception_class": "E_STOP",
            "exception_match": '{"code": "E-201"}',
            "sop_passages": "[]",
            "safety_warning": "evacuate",
            "escalation_decision": "full_evacuation",
            "final_response": '{"resolution": "..."}',
            "output": '{"resolution": "..."}',
            "status": AgentStatus.SUCCESS.value,
            "some_internal_subgraph_field": "must not leak through",
        }
        merged = node.merge_output({"correlation_id": "cid"}, sub_result)

        assert "some_internal_subgraph_field" not in merged
        assert merged["exception_class"] == "E_STOP"
        assert merged["result"] == '{"resolution": "..."}'
        assert merged["status"] == AgentStatus.SUCCESS.value


class TestInnerSubgraphDelegatedGating:
    """Delegation is intentional (GraphNode.__call__ / execute() hands off S-2/
    S-3 to the inner subgraph, see framework/nodes/graph_node.py) - but the
    inner entry node must actually carry its own S-1/S-2/S-3 gate so the
    delegation is not a silent no-op."""

    def test_inner_entry_node_declares_trust_level(self):
        assert ExceptionCodeLookupNode.required_trust_level == TrustLevel.VERIFIED_EXTERNAL

    def test_inner_entry_node_is_a_gated_function_node(self):
        from framework.nodes.function_node import FunctionNode

        assert issubclass(ExceptionCodeLookupNode, FunctionNode)
