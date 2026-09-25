# RET-C2-155 - PB test: E-stop safety-warning preservation contract (novel
# S-3 pattern, locked in docs/02_design.md).
#
# Contract: any assembled response with exception_class=E_STOP must carry the
# exact SAFETY_WARNING text; this must be enforced non-suppressibly, never
# filtered/altered/dropped, regardless of what upstream data (SOP KB, LLM
# output) feeds into assembly.

from framework.schemas.agent_status import AgentStatus

from src.nodes.post_process_node import OutputValidateNode
from src.schemas.state import to_json
from src.services.service import SAFETY_WARNING, check_safety


class TestPBSafetyWarningPreservation:
    def test_check_safety_returns_exact_warning_for_e_stop(self):
        assert check_safety("E_STOP") == SAFETY_WARNING

    def test_check_safety_returns_none_for_non_e_stop(self):
        assert check_safety("LOCAL_STOP") is None
        assert check_safety("WARNING") is None
        assert check_safety("NONE") is None

    def test_gate_blocks_e_stop_response_with_dropped_warning(self):
        response = to_json({"exception_class": "E_STOP", "safety_warning": None})
        out = OutputValidateNode()._extra_security_gate_output({"result": response})
        assert out["status"] == AgentStatus.ERROR

    def test_gate_blocks_e_stop_response_with_altered_warning(self):
        response = to_json({"exception_class": "E_STOP", "safety_warning": "a different, weaker warning"})
        out = OutputValidateNode()._extra_security_gate_output({"result": response})
        assert out["status"] == AgentStatus.ERROR

    def test_gate_passes_e_stop_response_with_exact_warning(self):
        response = to_json({"exception_class": "E_STOP", "safety_warning": SAFETY_WARNING})
        state = {"result": response}
        assert OutputValidateNode()._extra_security_gate_output(state) is state
