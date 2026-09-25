# RET-C2-155 - Integration test: full graph compile + invoke (Cat 2 outer + inner).

from framework.schemas.invocation_context import InvocationContext
from framework.schemas.trust_level import TrustLevel

from src.graph.graph import Graph

E_STOP_QUERY = "Geek+ AMR shows E-201 error near station 3 - is this a full evacuation or local stop?"
LOCAL_STOP_QUERY = "sorting line E-105 jam, what is the SOP for restarting?"
EMPTY_QUERY = ""
AMBIGUOUS_QUERY = "The robot is behaving erratically near personnel"

KB = [{"manual_section": "5.2", "content": "E-201 barcode error resolution near personnel zones", "robot_models": ["geekplus"]}]


class TestAgentIntegration:
    def test_e_stop_exception_full_evacuation(self):
        agent = Graph(config={"max_retry": 1, "kb": KB})
        agent.compile()
        ctx = InvocationContext(session_id="it-1", caller_trust_level=TrustLevel.VERIFIED_EXTERNAL, caller_id="warehouse-supervisor")
        result = agent.invoke(E_STOP_QUERY, ctx=ctx)

        assert result["status"] == "success"
        assert len(result.get("node_history", [])) >= 5

    def test_local_stop_exception(self):
        agent = Graph(config={"max_retry": 1, "kb": KB})
        agent.compile()
        ctx = InvocationContext(session_id="it-2", caller_trust_level=TrustLevel.VERIFIED_EXTERNAL, caller_id="warehouse-supervisor")
        result = agent.invoke(LOCAL_STOP_QUERY, ctx=ctx)
        assert result["status"] == "success"

    def test_empty_query_error(self):
        agent = Graph(config={"max_retry": 1, "kb": KB})
        agent.compile()
        ctx = InvocationContext(session_id="it-3", caller_trust_level=TrustLevel.VERIFIED_EXTERNAL, caller_id="warehouse-supervisor")
        result = agent.invoke(EMPTY_QUERY, ctx=ctx)
        assert result["status"] in ("error", "cancelled")

    def test_ambiguous_case_manual_review(self):
        agent = Graph(config={"max_retry": 1, "kb": KB})
        agent.compile()
        ctx = InvocationContext(session_id="it-4", caller_trust_level=TrustLevel.VERIFIED_EXTERNAL, caller_id="warehouse-supervisor")
        result = agent.invoke(AMBIGUOUS_QUERY, ctx=ctx)
        assert result["status"] == "success"
