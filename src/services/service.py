"""AgentCore Platform v1.0 - RET-C2-155 domain services.

Deterministic helpers only: query normalize + classify (finite types), robot-
model filter (deterministic lookup), exception-code lookup (structured table),
SOP retrieval mock (real interface - semantic search over manufacturer
manuals), safety-rule check (E-stop class -> hardcoded warning, never
suppressable), escalation decision table (unambiguous cases only -
deterministic; ambiguous cases handled by the LLM node), and audit-safe topic
extraction. No agenticstar imports.
"""

from __future__ import annotations

from typing import Any

MAX_QUERY_LENGTH = 2000

VALID_QUERY_TYPES = ("exception_code", "sop_lookup", "escalation", "safety")
VALID_ROBOT_MODELS = ("geekplus", "mir", "greyorange", "mujin", "unknown")
VALID_EXCEPTION_CLASSES = ("E_STOP", "LOCAL_STOP", "WARNING", "NONE")

# Mandatory hardcoded safety warning per exception class - non-suppressible,
# never LLM-generated.
SAFETY_WARNING = "E-STOP CLASS: Full evacuation required. Do not restart the robot until a certified safety officer confirms the area is clear."

# Deterministic exception-code -> known-SOP table (structured lookup).
_EXCEPTION_CODE_TABLE = {
    "E-201": {
        "exception_class": "E_STOP",
        "known_sop": "Unrecognized barcode near a personnel zone - full evacuation protocol applies.",
    },
    "E-105": {
        "exception_class": "LOCAL_STOP",
        "known_sop": "Sorting line jam - local stop, clear jam, resume via control panel.",
    },
    "W-050": {"exception_class": "WARNING", "known_sop": "Low battery warning - route robot to charging station."},
}


def normalize_query(raw_query: str) -> tuple[str, str | None]:
    """S-1: normalize + length-validate the incoming robot-ops question."""
    if not isinstance(raw_query, str) or not raw_query.strip():
        return "", "query is empty or missing"
    return raw_query.strip()[:MAX_QUERY_LENGTH], None


def classify_query_type(query: str) -> str:
    """Deterministic finite-type classifier (Tool)."""
    q = query.lower()
    if any(tok in q for tok in ("e-", "error", "code", "エラー")):
        return "exception_code"
    if any(tok in q for tok in ("sop", "procedure", "restart", "手順")):
        return "sop_lookup"
    if any(tok in q for tok in ("evacuat", "escalat", "避難", "エスカレ")):
        return "escalation"
    if any(tok in q for tok in ("safety", "e-stop", "安全")):
        return "safety"
    return "sop_lookup"


def filter_robot_model(query: str) -> str:
    """Deterministic robot-model -> applicable manual section lookup (Tool)."""
    q = query.lower()
    if "geek+" in q or "geekplus" in q:
        return "geekplus"
    if "mir" in q:
        return "mir"
    if "greyorange" in q:
        return "greyorange"
    if "mujin" in q:
        return "mujin"
    return "unknown"


def lookup_exception_code(query: str) -> dict[str, Any] | None:
    """Deterministic structured exception-code lookup (Tool)."""
    for code, entry in _EXCEPTION_CODE_TABLE.items():
        if code.lower() in query.lower():
            return {"code": code, **entry}
    return None


def retrieve_sop_passages(query: str, robot_model: str, kb: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """Deterministic mock vector search over robot manufacturer manuals
    (VectorRAGAgent-pattern node). KB-backed only."""
    kb = kb or []
    q_lower = query.lower()
    matches = []
    for doc in kb:
        tags = doc.get("robot_models", [])
        if robot_model in tags or "all" in tags:
            text = f"{doc.get('manual_section', '')} {doc.get('content', '')}".lower()
            if any(tok in text for tok in q_lower.split() if len(tok) > 1):
                matches.append(
                    {"manual_section": doc.get("manual_section", ""), "snippet": doc.get("content", "")[:200]}
                )
    return matches[:5]


def check_safety(exception_class: str) -> str | None:
    """Deterministic rule-based safety check (Tool). E_STOP class ALWAYS
    returns the hardcoded SAFETY_WARNING - never suppressable, never LLM-derived."""
    if exception_class == "E_STOP":
        return SAFETY_WARNING
    return None


def decide_escalation_deterministic(exception_class: str) -> str | None:
    """Deterministic escalation decision for unambiguous cases only.
    Returns None for ambiguous cases requiring LLM judgment."""
    if exception_class == "E_STOP":
        return "full_evacuation"
    if exception_class == "LOCAL_STOP":
        return "local_stop"
    if exception_class == "WARNING":
        return "no_escalation"
    return None  # ambiguous - requires LLM judgment


def build_response_fallback(
    sop_passages: list[dict[str, Any]], escalation_decision: str, safety_warning: str | None
) -> dict[str, Any]:
    """Deterministic fallback response assembly when no LLM is configured."""
    resolution = (
        "\n".join(f"- [{p['manual_section']}] {p['snippet']}" for p in sop_passages)
        if sop_passages
        else "No matching SOP found in the knowledge base."
    )
    return {
        "resolution": resolution,
        "escalation_decision": escalation_decision,
        "safety_warning": safety_warning,
    }


def extract_audit_safe_topic(query_type: str, robot_model: str, exception_class: str) -> dict[str, Any]:
    """S-4: audit-safe metadata - type/model/class only, never the raw query."""
    return {"query_type": query_type, "robot_model": robot_model, "exception_class": exception_class}
