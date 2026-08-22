from __future__ import annotations

from typing import Any, TypedDict


class GraphState(TypedDict, total=False):
    user_input: str
    intent: str
    context: dict[str, Any]
    missing_fields: list[str]
    pending_intent: str
    lookup_ready: bool
    create_ready: bool
    proposed_issue_summary: str
    tool_result: dict[str, Any]
    final_response: str
    error: str
