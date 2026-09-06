from __future__ import annotations

import json
import logging
import re
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import StructuredTool

logger = logging.getLogger(__name__)

TOOL_SELECTOR_SYSTEM_PROMPT = (
    "You select the single most relevant IT support tool for the user's request.\n"
    "Disambiguation rules:\n"
    "- knowledge_search: how-to, reset, install, configure, or documentation steps. "
    "Not for existing ticket status.\n"
    "- ticket_lookup: status of an existing issue/ticket, ticket counts, or TKT lookup. "
    "Not for creating a new ticket.\n"
    "- ticket_creation: user wants to raise/open/log a NEW ticket.\n"
    "- ticket_update: modify/edit/correct an existing ticket summary.\n"
    "- employee_lookup: employee profile/details for an EMP id.\n"
    "- system_status: outage, health, or operational status of IT services.\n"
    "- small_talk: greeting, thanks, or no IT tool is needed.\n"
    "Use conversation context for short follow-ups. Put the best tool first."
)

_TOOL_SPECS: tuple[tuple[str, str], ...] = (
    (
        "knowledge_search",
        "Search IT knowledge articles for how-to, password reset, install, configure, "
        "or troubleshooting steps. Do not use this to check existing ticket status.",
    ),
    (
        "ticket_lookup",
        "Look up existing tickets by employee or ticket ID, including ticket counts and "
        "status of a current issue. Do not use this to create a new ticket.",
    ),
    (
        "ticket_creation",
        "Create a new support ticket after the user asks to raise, open, log, or create one.",
    ),
    (
        "ticket_update",
        "Update or correct the summary/description of an existing ticket (usually with a TKT id).",
    ),
    (
        "employee_lookup",
        "Return employee profile details (name, department, email, location) for an EMP id.",
    ),
    (
        "system_status",
        "Report IT service health, outages, or operational/degraded status (VPN, email, etc.).",
    ),
    (
        "small_talk",
        "Handle greetings, thanks, or requests that do not require an IT data tool.",
    ),
)


def _unused_tool() -> str:
    """Catalog placeholder; LangGraph nodes execute the real tools."""
    return ""


def build_support_tool_catalog() -> list[StructuredTool]:
    return [
        StructuredTool.from_function(
            func=_unused_tool,
            name=name,
            description=description,
        )
        for name, description in _TOOL_SPECS
    ]


def _format_selection_message(query: str, context: dict[str, Any] | None) -> str:
    compact_context = {
        key: value
        for key, value in (context or {}).items()
        if key in {
            "employee_id",
            "ticket_id",
            "pending_intent",
            "last_intent",
            "proposed_issue_summary",
            "last_user_message",
            "previous_user_message",
        }
    }
    return (
        f"User request: {query}\n"
        f"Conversation context: {json.dumps(compact_context, ensure_ascii=True, default=str)}"
    )


def _deterministic_intent_override(query: str) -> str | None:
    lowered = query.lower().strip()

    if any(token in lowered for token in ["raise", "create", "open", "log a ticket", "new ticket"]):
        return "ticket_creation"

    has_incident = any(
        token in lowered
        for token in [
            "not working",
            "isn't working",
            "unable to",
            "cannot",
            "can't",
            "keeps failing",
            "keeps disconnecting",
            "broken",
        ]
    )
    has_status_check = any(
        token in lowered
        for token in ["system status", "service status", "status page", "outage", "health", "operational", "any outage"]
    )
    has_id = bool(re.search(r"\b(?:EMP\d{4}|TKT\d{4,})\b", query.upper()))

    # Keep incident reports in the support workflow instead of small_talk.
    if has_incident and not has_status_check and not has_id:
        return "knowledge_search"

    return None


class SupportToolSelector:
    """LangChain LLMToolSelectorMiddleware adapter for LangGraph intent routing."""

    def __init__(self, model: Any) -> None:
        from langchain.agents.middleware import LLMToolSelectorMiddleware

        self.model = model
        self.catalog = build_support_tool_catalog()
        self.middleware = LLMToolSelectorMiddleware(
            model=model,
            system_prompt=TOOL_SELECTOR_SYSTEM_PROMPT,
            max_tools=1,
            max_retries=1,
            on_parsing_failure="none",
        )

    def select_intent(self, query: str, context: dict[str, Any] | None = None) -> str | None:
        from langchain.agents.middleware import ModelRequest, ModelResponse

        overridden_intent = _deterministic_intent_override(query)
        if overridden_intent is not None:
            logger.info("Tool selector deterministic override chose %s for query=%r", overridden_intent, query)
            return overridden_intent

        selected: list[str] = []

        def _capture_selected_tools(request: Any) -> Any:
            selected.extend(
                tool.name
                for tool in request.tools
                if getattr(tool, "name", None) and not isinstance(tool, dict)
            )
            return ModelResponse(result=[AIMessage(content="")])

        request = ModelRequest(
            model=self.model,
            messages=[HumanMessage(content=_format_selection_message(query, context))],
            tools=list(self.catalog),
        )
        self.middleware.wrap_model_call(request, _capture_selected_tools)
        if not selected:
            logger.info("Tool selector returned no tools for query=%r", query)
            return None
        intent = selected[0]
        catalog_names = {name for name, _ in _TOOL_SPECS}
        if intent not in catalog_names:
            logger.info("Tool selector returned unknown tool %s", intent)
            return None
        logger.info("Tool selector chose %s for query=%r", intent, query)
        return intent
