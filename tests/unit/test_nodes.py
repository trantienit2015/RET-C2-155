# RET-C2-155 - Unit tests: per-node success + error/edge paths.

from framework.schemas.agent_status import AgentStatus

from src.nodes.escalation_decide_response_format_node import EscalationDecideResponseFormatNode
from src.nodes.exception_code_lookup_node import ExceptionCodeLookupNode
from src.nodes.post_process_node import OutputValidateNode
from src.nodes.pre_process_node import QueryClassifyRobotModelFilterNode
from src.nodes.safety_check_node import SafetyCheckNode
from src.nodes.sop_retrieve_node import SOPRetrieveNode
from src.schemas.state import from_json, to_json
from src.services.service import SAFETY_WARNING

KB = [{"manual_section": "5.2", "content": "E-201 barcode error resolution near personnel zones", "robot_models": ["geekplus"]}]


class TestQueryClassifyRobotModelFilterNode:
    def test_success(self):
        state = {"user_input": "Geek+ AMR shows E-201 error near station 3"}
        r = QueryClassifyRobotModelFilterNode().execute(state)
        assert r["status"] == AgentStatus.SUCCESS
        assert r["robot_model"] == "geekplus"

    def test_empty_query_error(self):
        assert QueryClassifyRobotModelFilterNode().execute({"user_input": ""})["status"] == AgentStatus.ERROR


def _inner_state(query="E-201 error near station 3", query_type="exception_code", robot_model="geekplus"):
    return {"user_input": to_json({"query": query, "query_type": query_type, "robot_model": robot_model})}


class TestExceptionCodeLookupNode:
    def test_e_stop_matched(self):
        r = ExceptionCodeLookupNode().execute(_inner_state())
        assert r["status"] == AgentStatus.SUCCESS
        assert r["exception_class"] == "E_STOP"

    def test_no_match_returns_none_class(self):
        state = _inner_state(query="robot behaving erratically near personnel")
        r = ExceptionCodeLookupNode().execute(state)
        assert r["exception_class"] == "NONE"

    def test_missing_input_error(self):
        assert ExceptionCodeLookupNode().execute({"user_input": None})["status"] == AgentStatus.ERROR

    def test_invalid_query_type_error(self):
        state = {"user_input": to_json({"query": "x", "query_type": "invalid", "robot_model": "geekplus"})}
        assert ExceptionCodeLookupNode().execute(state)["status"] == AgentStatus.ERROR


class TestSOPRetrieveNode:
    def test_success(self):
        r = SOPRetrieveNode(kb=KB).execute(_inner_state())
        assert r["status"] == AgentStatus.SUCCESS
        passages = from_json(r["sop_passages"], [])
        assert len(passages) >= 1

    def test_missing_query_error(self):
        assert SOPRetrieveNode(kb=KB).execute({"user_input": ""})["status"] == AgentStatus.ERROR


class TestSafetyCheckNode:
    def test_e_stop_gets_warning(self):
        r = SafetyCheckNode().execute({"exception_class": "E_STOP"})
        assert r["safety_warning"] == SAFETY_WARNING

    def test_other_class_no_warning(self):
        r = SafetyCheckNode().execute({"exception_class": "LOCAL_STOP"})
        assert r["safety_warning"] is None


class TestEscalationDecideResponseFormatNode:
    def test_e_stop_full_evacuation(self):
        state = {**_inner_state(), "exception_class": "E_STOP", "safety_warning": SAFETY_WARNING, "sop_passages": to_json([])}
        r = EscalationDecideResponseFormatNode().execute(state)
        assert r["status"] == AgentStatus.SUCCESS
        assert r["escalation_decision"] == "full_evacuation"
        response = from_json(r["final_response"], {})
        assert response["safety_warning"] == SAFETY_WARNING

    def test_ambiguous_case_manual_review_fallback(self):
        state = {**_inner_state(query="robot behaving erratically"), "exception_class": "NONE", "safety_warning": None, "sop_passages": to_json([])}
        r = EscalationDecideResponseFormatNode().execute(state)
        assert r["escalation_decision"] == "manual_review"

    def test_ambiguous_case_llm_configured_but_raises_returns_error(self):
        class _BrokenLLM:
            def complete(self, messages):
                raise RuntimeError("provider outage")

        state = {**_inner_state(query="robot behaving erratically"), "exception_class": "NONE", "safety_warning": None, "sop_passages": to_json([])}
        r = EscalationDecideResponseFormatNode(llm=_BrokenLLM()).execute(state)
        assert r["status"] == AgentStatus.ERROR.value
        assert "LLM call failed" in r["error_log"][0]

    def test_ambiguous_case_llm_configured_but_returns_junk_returns_error(self):
        class _JunkLLM:
            def complete(self, messages):
                return {"content": "not a valid escalation value"}

        state = {**_inner_state(query="robot behaving erratically"), "exception_class": "NONE", "safety_warning": None, "sop_passages": to_json([])}
        r = EscalationDecideResponseFormatNode(llm=_JunkLLM()).execute(state)
        assert r["status"] == AgentStatus.ERROR.value

    def test_ambiguous_case_llm_configured_valid_response_used(self):
        class _GoodLLM:
            def complete(self, messages):
                assert isinstance(messages, list) and messages[0]["role"] == "user"
                return {"content": "Local_Stop"}

        state = {**_inner_state(query="robot behaving erratically"), "exception_class": "NONE", "safety_warning": None, "sop_passages": to_json([])}
        r = EscalationDecideResponseFormatNode(llm=_GoodLLM()).execute(state)
        assert r["status"] == AgentStatus.SUCCESS.value
        assert r["escalation_decision"] == "local_stop"


class TestOutputValidateNode:
    def test_success_e_stop_with_warning(self):
        response = {"exception_class": "E_STOP", "safety_warning": SAFETY_WARNING, "escalation_decision": "full_evacuation", "resolution": "x"}
        r = OutputValidateNode().execute({"final_response": to_json(response)})
        assert r["status"] == AgentStatus.SUCCESS

    def test_upstream_error_short_circuits(self):
        assert OutputValidateNode().execute({"status": AgentStatus.ERROR})["status"] == AgentStatus.ERROR

    def test_extra_gate_blocks_e_stop_missing_warning(self):
        bad = to_json({"exception_class": "E_STOP", "safety_warning": None})
        out = OutputValidateNode()._extra_security_gate_output({"result": bad})
        assert out["status"] == AgentStatus.ERROR

    def test_extra_gate_passthrough_non_e_stop(self):
        good = to_json({"exception_class": "LOCAL_STOP", "safety_warning": None})
        state = {"result": good}
        assert OutputValidateNode()._extra_security_gate_output(state) is state

    def test_extra_gate_passthrough_e_stop_with_warning(self):
        good = to_json({"exception_class": "E_STOP", "safety_warning": SAFETY_WARNING})
        state = {"result": good}
        assert OutputValidateNode()._extra_security_gate_output(state) is state
