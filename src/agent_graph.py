from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any, Callable

from langgraph.graph import END, START, StateGraph

from src.config import get_settings
from src.state import GraphState

if TYPE_CHECKING:
    from src.tools import LocalITTools


SETTINGS = get_settings()


def _extract_employee_id(text: str) -> str | None:
    match = re.search(r"\bEMP\d{4}\b", text.upper())
    return match.group(0) if match else None


def _extract_ticket_id(text: str) -> str | None:
    match = re.search(r"\bTKT\d{4,}\b", text.upper())
    return match.group(0) if match else None


def _build_issue_summary(text: str) -> str:
    cleaned = re.sub(
        r"\b(please|can you|could you|raise|create|open|log|ticket|for me|my)\b",
        "",
        text,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .,-")
    return cleaned


def _looks_like_affirmation(text: str) -> bool:
    normalized = text.strip().lower()
    return normalized in {"yes", "yeah", "yep", "sure", "ok", "okay", "please do", "go ahead"}


def _looks_like_create_confirmation(text: str) -> bool:
    lowered = text.lower()
    return bool(
        re.search(r"\b(?:create|open|raise)\s+(?:a\s+)?(?:new\s+)?ticket\b", lowered)
        or re.search(r"\b(?:yes|sure|okay|yep|go ahead|please do)\s+(?:create|open|raise)\b", lowered)
        or "create new" in lowered
    )


def _looks_like_negative(text: str) -> bool:
    normalized = text.strip().lower()
    return normalized in {"no", "nope", "not now", "skip", "don't", "do not"}


def _looks_like_greeting(text: str) -> bool:
    lowered = text.lower()
    return any(token in lowered for token in ["hi", "hello", "hey", "good morning", "good afternoon", "good evening"])


def _looks_like_thanks(text: str) -> bool:
    lowered = text.lower()
    return any(token in lowered for token in ["thanks", "thank you", "thx"])


def _looks_like_count_query(text: str) -> bool:
    lowered = text.lower()
    return any(token in lowered for token in ["how many", "count", "number of", "total tickets"]) \
        or re.search(r"\b(?:how many|count|number of)\s+(?:ticket|tickets|issues|issue)\b", lowered) is not None


def _looks_like_issue_summary(text: str) -> bool:
    lowered = text.lower()
    return any(
        token in lowered
        for token in [
            "hardware",
            "software",
            "network",
            "vpn",
            "wifi",
            "printer",
            "screen",
            "laptop",
            "mouse",
            "keyboard",
            "monitor",
            "audio",
            "video",
            "camera",
            "blurry",
            "blur",
            "battery",
            "driver",
            "issue",
            "problem",
            "not working",
            "broken",
            "offline",
            "fail",
            "disconnect",
        ]
    )


def _infer_ticket_category(text: str) -> str:
    lowered = text.lower()
    if any(token in lowered for token in ["vpn", "wifi", "network", "internet", "connectivity", "router", "lan", "dns", "firewall", "latency", "offline"]):
        return "network"
    if any(token in lowered for token in ["hardware", "screen", "monitor", "keyboard", "mouse", "printer", "audio", "speaker", "camera", "video", "blurry", "blur", "battery", "charger", "display", "laptop", "desktop", "device"]):
        return "hardware"
    if any(token in lowered for token in ["software", "app", "outlook", "excel", "browser", "driver", "install", "update", "crash", "login", "password", "email", "office", "application", "server", "os"]):
        return "software"
    return "general"


def _infer_ticket_priority(text: str) -> str:
    lowered = text.lower()
    if any(token in lowered for token in ["down", "blocked", "urgent", "critical", "cannot", "unable", "not working", "outage", "offline", "dead", "won't start"]):
        return "high"
    if any(token in lowered for token in ["slow", "intermittent", "flicker", "disconnects", "errors", "warning", "issue", "problem"]):
        return "medium"
    return "low"


def _looks_like_update_request(text: str) -> bool:
    lowered = text.lower()
    return any(token in lowered for token in ["modify", "update", "change", "edit", "correct"])


def _extract_updated_summary(text: str) -> str:
    if ":" in text:
        summary = text.split(":", 1)[1].strip()
        summary = re.sub(r"\b(for|to)\s+ticket\s+tkt\d{4,}\b", "", summary, flags=re.IGNORECASE).strip(" .")
        return summary

    match = re.search(
        r"(?:description|summary)\s*(?:to|as)\s*(.+)$",
        text,
        flags=re.IGNORECASE,
    )
    if match:
        summary = match.group(1).strip()
        summary = re.sub(r"\b(for|to)\s+ticket\s+tkt\d{4,}\b", "", summary, flags=re.IGNORECASE).strip(" .")
        return summary

    return ""


def _looks_like_employee_query(text: str) -> bool:
    lowered = text.lower()
    return any(token in lowered for token in ["employee details", "employee info", "employee information", "employee profile"])


def _looks_like_status_check(text: str) -> bool:
    lowered = text.lower()
    return any(
        token in lowered
        for token in [
            "system status",
            "service status",
            "status page",
            "outage",
            "health",
            "operational",
            "is there an issue",
            "any outage",
        ]
    )


def _looks_like_ticket_status_query(text: str) -> bool:
    lowered = text.lower()
    if any(token in lowered for token in ["system status", "service status", "status page", "outage", "health", "operational"]):
        return False
    issue_words = ["issue", "problem", "ticket", "bios", "vpn", "wifi", "printer", "laptop", "screen", "server", "access"]
    return (
        any(token in lowered for token in ["status of", "status for", "what is the status", "issue status", "problem status"])
        and any(token in lowered for token in issue_words)
    )


def _looks_like_ticket_creation_request(text: str) -> bool:
    lowered = text.lower()
    return bool(re.search(r"\b(?:raise|create|open|log a ticket|new ticket)\b", lowered))


def _looks_like_employee_ticket_lookup(text: str) -> bool:
    lowered = text.lower()
    if not _extract_employee_id(text):
        return False
    if _looks_like_ticket_creation_request(text):
        return False
    return any(token in lowered for token in ["ticket", "tickets", "issue", "issues", "raised", "opened", "status", "history"])


def _looks_like_incident_report(text: str) -> bool:
    lowered = text.lower()
    return any(
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


def _looks_like_knowledge_request(text: str) -> bool:
    lowered = text.lower()
    return any(token in lowered for token in ["how", "reset", "configure", "setup", "install", "steps"])


def build_graph(
    tools: "LocalITTools",
    classify_intent: Callable[[str, dict], str],
    compose_with_llm: Callable[[str, str, dict, dict, str], str] | None = None,
) -> Any:
    graph = StateGraph(GraphState)

    def capture_context(state: GraphState) -> GraphState:
        context = dict(state.get("context", {}))
        user_input = state.get("user_input", "")
        found_employee = _extract_employee_id(user_input)
        found_ticket = _extract_ticket_id(user_input)
        if found_employee:
            context["employee_id"] = found_employee
        if found_ticket:
            context["ticket_id"] = found_ticket
        if "last_user_message" in context:
            context["previous_user_message"] = context["last_user_message"]
        context["last_user_message"] = user_input
        return {"context": context}

    def decide_intent(state: GraphState) -> GraphState:
        user_input = state.get("user_input", "")
        context = dict(state.get("context", {}))
        semantic_intent = classify_intent(user_input, context)
        if context.get("awaiting_lookup_confirmation"):
            if _looks_like_create_confirmation(user_input):
                intent = "ticket_creation"
                context.pop("awaiting_lookup_confirmation", None)
                context["pending_intent"] = "ticket_creation"
                context["existing_tickets_checked"] = True
            elif _looks_like_affirmation(user_input):
                context.pop("awaiting_lookup_confirmation", None)
                if context.get("employee_id") and (
                    context.get("proposed_issue_summary")
                    or len(_build_issue_summary(user_input)) >= 8
                    or len(_build_issue_summary(context.get("last_user_message", ""))) >= 8
                ):
                    intent = "ticket_creation"
                    context["pending_intent"] = "ticket_creation"
                    context["existing_tickets_checked"] = True
                else:
                    intent = "ticket_lookup"
            elif _looks_like_negative(user_input):
                intent = "ticket_creation"
                context["existing_tickets_checked"] = True
                context.pop("awaiting_lookup_confirmation", None)
                context["pending_intent"] = "ticket_creation"
            else:
                # Treat additional issue details as continuation, not small talk.
                refined_summary = _build_issue_summary(user_input)
                if len(refined_summary) >= 8:
                    context["proposed_issue_summary"] = refined_summary
                    context["existing_tickets_checked"] = True
                    context.pop("awaiting_lookup_confirmation", None)
                    intent = "ticket_creation"
                else:
                    intent = "small_talk"
        elif context.get("awaiting_create_confirmation"):
            if _looks_like_affirmation(user_input):
                intent = "ticket_creation"
                context.pop("awaiting_create_confirmation", None)
            elif _looks_like_negative(user_input):
                intent = "small_talk"
                context.pop("awaiting_create_confirmation", None)
            else:
                intent = "small_talk"
        elif _extract_employee_id(user_input) and _looks_like_employee_query(user_input):
            intent = "employee_lookup"
        elif _extract_ticket_id(user_input) and _looks_like_update_request(user_input):
            intent = "ticket_update"
        elif _extract_ticket_id(user_input):
            intent = "ticket_lookup"
        elif _extract_employee_id(user_input) and _looks_like_employee_ticket_lookup(user_input):
            intent = "ticket_lookup"
        elif _looks_like_count_query(user_input):
            intent = "ticket_lookup"
        elif _looks_like_status_check(user_input):
            if _looks_like_ticket_status_query(user_input):
                intent = "ticket_lookup"
            else:
                intent = "system_status"
        else:
            pending_intent = context.get("pending_intent")
            if semantic_intent:
                intent = semantic_intent
                # Safety override: incident-like reports should not collapse to small talk.
                if _looks_like_ticket_creation_request(user_input):
                    intent = "ticket_creation"
                if (
                    intent == "ticket_creation"
                    and _looks_like_incident_report(user_input)
                    and not _looks_like_ticket_creation_request(user_input)
                    and not _looks_like_status_check(user_input)
                ):
                    intent = "knowledge_search"
                if (
                    intent == "small_talk"
                    and _looks_like_incident_report(user_input)
                    and not _looks_like_status_check(user_input)
                ):
                    intent = "knowledge_search"
                if intent == "small_talk" and _looks_like_issue_summary(user_input):
                    intent = "ticket_creation"
                if pending_intent and (_extract_employee_id(user_input) or _looks_like_affirmation(user_input)):
                    intent = pending_intent
                elif pending_intent and len(user_input.strip()) >= 8:
                    intent = pending_intent
            elif pending_intent and (_extract_employee_id(user_input) or _looks_like_affirmation(user_input)):
                intent = pending_intent
            elif pending_intent and len(user_input.strip()) >= 8:
                intent = pending_intent
            elif _looks_like_ticket_creation_request(user_input):
                intent = "ticket_creation"
            elif (
                _looks_like_incident_report(user_input)
                and not _looks_like_status_check(user_input)
                and not _looks_like_knowledge_request(user_input)
            ):
                intent = "knowledge_search"
            elif _looks_like_issue_summary(user_input):
                intent = "ticket_creation"
            else:
                intent = "small_talk"
        context["last_intent"] = intent
        if intent == "ticket_lookup":
            context.pop("awaiting_lookup_confirmation", None)
        if intent == "ticket_creation":
            context.pop("awaiting_create_confirmation", None)
        return {"intent": intent, "context": context}

    def knowledge_search_node(state: GraphState) -> GraphState:
        result = tools.search_knowledge(
            state.get("user_input", ""),
            top_k=SETTINGS.max_kb_results,
        )
        return {"tool_result": {"tool": "knowledge_search", "data": result}}

    def system_status_node(state: GraphState) -> GraphState:
        result = tools.get_system_status(query=state.get("user_input", ""))
        return {"tool_result": {"tool": "system_status", "data": result}}

    def employee_lookup_node(state: GraphState) -> GraphState:
        employee_id = _extract_employee_id(state.get("user_input", "")) or state.get("context", {}).get("employee_id", "")
        if not employee_id:
            return {
                "tool_result": {
                    "tool": "employee_lookup",
                    "data": {"employee_id": "", "employees": [], "count": 0, "source": "postgres.employees"},
                }
            }
        result = tools.lookup_employee_by_id(employee_id=employee_id)
        return {"tool_result": {"tool": "employee_lookup", "data": result}}

    def ticket_lookup_validate(state: GraphState) -> GraphState:
        context = state.get("context", {})
        ticket_id = _extract_ticket_id(state.get("user_input", ""))
        employee_id = context.get("employee_id")
        if ticket_id:
            context = dict(context)
            context.pop("pending_intent", None)
            return {"lookup_ready": True, "context": context}
        if not employee_id:
            context = dict(context)
            context["pending_intent"] = "ticket_lookup"
            return {
                "lookup_ready": False,
                "missing_fields": ["employee_id"],
                "context": context,
                "final_response": "I can check your ticket status. Please share your employee ID (example: EMP1024).",
            }
        if not tools.employee_exists(employee_id):
            context = dict(context)
            context.pop("pending_intent", None)
            return {
                "lookup_ready": False,
                "context": context,
                "final_response": (
                    f"I could not find employee ID {employee_id}. "
                    "Please verify and try again."
                ),
            }
        context = dict(context)
        context.pop("pending_intent", None)
        return {"lookup_ready": True, "context": context}

    def ticket_lookup_node(state: GraphState) -> GraphState:
        context = state.get("context", {})
        ticket_id = _extract_ticket_id(state.get("user_input", "")) or ""
        if ticket_id:
            result = tools.lookup_ticket_by_id(ticket_id=ticket_id)
        else:
            employee_id = context.get("employee_id", "")
            result = tools.lookup_tickets(employee_id=employee_id, query=state.get("user_input"))
        return {"tool_result": {"tool": "ticket_lookup", "data": result}}

    def ticket_create_validate(state: GraphState) -> GraphState:
        context = state.get("context", {})
        was_pending_ticket_creation = context.get("pending_intent") == "ticket_creation"
        employee_id = context.get("employee_id")
        user_input = state.get("user_input", "")
        previous_message = context.get("previous_user_message", "")
        issue_summary = _build_issue_summary(user_input)

        if len(issue_summary) < 8 and context.get("pending_intent") == "ticket_creation":
            prior_summary = context.get("proposed_issue_summary") or _build_issue_summary(previous_message)
            if len(prior_summary) >= 8:
                issue_summary = prior_summary

        missing_fields: list[str] = []
        if not employee_id:
            missing_fields.append("employee_id")
        if len(issue_summary) < 8:
            missing_fields.append("issue_summary")

        if missing_fields:
            context = dict(context)
            context["pending_intent"] = "ticket_creation"
            if len(issue_summary) >= 8:
                context["proposed_issue_summary"] = issue_summary
            prompts = []
            if "employee_id" in missing_fields:
                prompts.append("employee ID (example: EMP1024)")
            if "issue_summary" in missing_fields:
                prompts.append("a short issue description")
            return {
                "create_ready": False,
                "missing_fields": missing_fields,
                "context": context,
                "final_response": "Before I create a ticket, please share " + " and ".join(prompts) + ".",
            }

        if not tools.employee_exists(employee_id):
            context = dict(context)
            context.pop("pending_intent", None)
            return {
                "create_ready": False,
                "context": context,
                "final_response": (
                    f"I could not find employee ID {employee_id}. "
                    "Please verify and try again."
                ),
            }

        if was_pending_ticket_creation and not context.get("existing_tickets_checked"):
            context = dict(context)
            context["proposed_issue_summary"] = issue_summary
            context["pending_intent"] = "ticket_lookup"
            context["resume_intent"] = "ticket_creation"
            context["awaiting_lookup_confirmation"] = True
            return {
                "create_ready": False,
                "context": context,
                "final_response": (
                    f"I found your profile for {employee_id}. "
                    "Would you like me to check existing tickets before creating a new one?"
                ),
            }

        duplicate = tools.find_duplicate_ticket(employee_id=employee_id, issue_summary=issue_summary)
        if duplicate:
            context = dict(context)
            context.pop("pending_intent", None)
            reason = duplicate.get("duplicate_reason")
            reason_text = f"\nReason: {reason}" if reason else ""
            return {
                "create_ready": False,
                "tool_result": {"tool": "duplicate_check", "data": duplicate},
                "context": context,
                "final_response": (
                    "I found an existing open ticket with a similar issue: "
                    f"{duplicate.get('ticket_id')} ({duplicate.get('status')}). "
                    "I did not create a duplicate ticket."
                    f"{reason_text}"
                ),
            }

        context = dict(context)
        context["proposed_issue_summary"] = issue_summary
        context["detected_category"] = _infer_ticket_category(issue_summary)
        context["detected_priority"] = _infer_ticket_priority(issue_summary)
        context.pop("pending_intent", None)
        return {"create_ready": True, "context": context, "proposed_issue_summary": issue_summary}

    def ticket_create_node(state: GraphState) -> GraphState:
        context = state.get("context", {})
        employee_id = context.get("employee_id", "")
        issue_summary = state.get("proposed_issue_summary") or context.get("proposed_issue_summary", "")
        category = context.get("detected_category") or _infer_ticket_category(issue_summary)
        priority = context.get("detected_priority") or _infer_ticket_priority(issue_summary)

        result = tools.create_ticket(
            employee_id=employee_id,
            issue_summary=issue_summary,
            category=category,
            priority=priority,
        )
        if not result.get("created"):
            return {
                "tool_result": {"tool": "ticket_creation", "data": result},
                "final_response": (
                    "I could not create the ticket because the local ticket database is unavailable right now. "
                    "Please retry once the database connection is restored."
                ),
            }
        return {"tool_result": {"tool": "ticket_creation", "data": result}}

    def ticket_update_validate(state: GraphState) -> GraphState:
        context = state.get("context", {})
        user_input = state.get("user_input", "")
        ticket_id = _extract_ticket_id(user_input) or context.get("ticket_id")
        updated_summary = _extract_updated_summary(user_input)

        missing_fields: list[str] = []
        if not ticket_id:
            missing_fields.append("ticket_id")
        if len(updated_summary) < 5:
            missing_fields.append("updated_summary")

        if missing_fields:
            context = dict(context)
            context["pending_intent"] = "ticket_update"
            if ticket_id:
                context["ticket_id"] = ticket_id
            prompts = []
            if "ticket_id" in missing_fields:
                prompts.append("ticket ID (example: TKT1001)")
            if "updated_summary" in missing_fields:
                prompts.append("the new ticket description")
            return {
                "create_ready": False,
                "missing_fields": missing_fields,
                "context": context,
                "final_response": "Before I modify the ticket, please share " + " and ".join(prompts) + ".",
            }

        existing = tools.lookup_ticket_by_id(ticket_id)
        if existing.get("count", 0) == 0:
            return {
                "create_ready": False,
                "final_response": f"I could not find ticket {ticket_id}. Please verify and try again.",
            }

        context = dict(context)
        context.pop("pending_intent", None)
        context["ticket_id"] = ticket_id
        context["proposed_issue_summary"] = updated_summary
        return {"create_ready": True, "context": context, "proposed_issue_summary": updated_summary}

    def ticket_update_node(state: GraphState) -> GraphState:
        context = state.get("context", {})
        ticket_id = context.get("ticket_id", "")
        updated_summary = state.get("proposed_issue_summary") or context.get("proposed_issue_summary", "")
        result = tools.update_ticket_summary(ticket_id=ticket_id, new_summary=updated_summary)
        return {"tool_result": {"tool": "ticket_update", "data": result}}

    def small_talk_node(state: GraphState) -> GraphState:
        user_input = state.get("user_input", "")
        if _looks_like_thanks(user_input):
            return {
                "final_response": (
                    "You are welcome. I can still help with ticket status, IT troubleshooting guidance, "
                    "or creating a new support ticket whenever you are ready."
                )
            }

        if _looks_like_greeting(user_input):
            return {
                "final_response": (
                    "Hello. I am your AI IT support assistant. "
                    "I can help with knowledge base troubleshooting, ticket lookup by employee or ticket ID, "
                    "system status checks, and new ticket creation. "
                    "Try: 'How do I reset VPN password?', 'Check ticket status for EMP1024', "
                    "or 'Create a ticket for screen issue'."
                )
            }

        return {
            "final_response": (
                "I can help with IT support tasks including troubleshooting guidance from the knowledge base, "
                "ticket lookup, system status checks, and ticket creation. "
                "Please share your issue, employee ID, or ticket ID to get started."
            )
        }

    def compose_response(state: GraphState) -> GraphState:
        if state.get("final_response"):
            return {"final_response": state["final_response"]}

        intent = state.get("intent")
        tool_result = state.get("tool_result", {})
        data = tool_result.get("data", {})

        fallback_response = "I am ready to help. Ask about IT guidance, ticket status, or creating a new ticket."

        if intent == "knowledge_search":
            if data.get("error"):
                fallback_response = (
                    "I could not access the knowledge base right now because the local database connection failed. "
                    "Please retry after the database is available."
                )
                return {
                    "final_response": compose_with_llm(
                        state.get("user_input", ""), intent or "", state.get("context", {}), tool_result, fallback_response
                    ) if compose_with_llm else fallback_response
                }
            matches = data.get("matches", [])
            if not matches:
                context = dict(state.get("context", {}))
                issue_summary = _build_issue_summary(state.get("user_input", ""))
                if len(issue_summary) >= 8:
                    context["proposed_issue_summary"] = issue_summary
                context["pending_intent"] = "ticket_creation"
                fallback_response = (
                    "I could not find a matching knowledge base article. "
                    "Please share your employee ID (example: EMP1024), and I can continue with ticket support for this issue."
                )
                return {
                    "context": context,
                    "final_response": compose_with_llm(
                        state.get("user_input", ""), intent or "", state.get("context", {}), tool_result, fallback_response
                    ) if compose_with_llm else fallback_response
                }
            top = matches[0]
            fallback_response = (
                f"Here is what I found from the knowledge base:\n\n"
                f"Title: {top.get('title')}\n"
                f"Answer: {top.get('content')}\n\n"
                f"Reference: {top.get('article_id')}"
            )
            return {
                "final_response": compose_with_llm(
                    state.get("user_input", ""), intent or "", state.get("context", {}), tool_result, fallback_response
                ) if compose_with_llm else fallback_response
            }

        if intent == "system_status":
            if data.get("error"):
                fallback_response = (
                    "I could not access system status right now because the local database connection failed. "
                    "Please retry after the database is available."
                )
                return {
                    "final_response": compose_with_llm(
                        state.get("user_input", ""), intent or "", state.get("context", {}), tool_result, fallback_response
                    ) if compose_with_llm else fallback_response
                }
            statuses = data.get("statuses", [])
            used_fallback = bool(data.get("fallback_to_all"))
            if not statuses:
                fallback_response = "I could not find any matching system status entries."
                return {
                    "final_response": compose_with_llm(
                        state.get("user_input", ""), intent or "", state.get("context", {}), tool_result, fallback_response
                    ) if compose_with_llm else fallback_response
                }
            degraded = [row for row in statuses if str(row.get("status", "")).lower() != "operational"]
            if degraded:
                names = ", ".join(str(row.get("service")) for row in degraded)
                if used_fallback:
                    fallback_response = (
                        "I did not find an exact service match for your query, so I checked overall system status. "
                        f"Attention required for: {names}."
                    )
                else:
                    fallback_response = "Current system status retrieved. " f"Attention required for: {names}."
                return {
                    "final_response": compose_with_llm(
                        state.get("user_input", ""), intent or "", state.get("context", {}), tool_result, fallback_response
                    ) if compose_with_llm else fallback_response
                }
            if used_fallback:
                fallback_response = (
                    "I did not find an exact service match for your query, so I checked overall system status. "
                    "All listed services are operational."
                )
            else:
                fallback_response = "Current system status retrieved. All listed services are operational."
            return {
                "final_response": compose_with_llm(
                    state.get("user_input", ""), intent or "", state.get("context", {}), tool_result, fallback_response
                ) if compose_with_llm else fallback_response
            }

        if intent == "employee_lookup":
            if data.get("error"):
                fallback_response = (
                    "I could not access employee information right now because the local database connection failed. "
                    "Please retry after the database is available."
                )
                return {
                    "final_response": compose_with_llm(
                        state.get("user_input", ""), intent or "", state.get("context", {}), tool_result, fallback_response
                    ) if compose_with_llm else fallback_response
                }
            employees = data.get("employees", [])
            emp_id = data.get("employee_id", "")
            if not employees:
                fallback_response = f"I could not find employee details for {emp_id or 'the requested employee ID'}."
                return {
                    "final_response": compose_with_llm(
                        state.get("user_input", ""), intent or "", state.get("context", {}), tool_result, fallback_response
                    ) if compose_with_llm else fallback_response
                }
            employee = employees[0]
            fallback_response = (
                f"Employee details for {employee.get('employee_id')}:\n"
                f"Name: {employee.get('name')}\n"
                f"Department: {employee.get('department')}\n"
                f"Email: {employee.get('email')}\n"
                f"Location: {employee.get('location')}"
            )
            return {
                "final_response": compose_with_llm(
                    state.get("user_input", ""), intent or "", state.get("context", {}), tool_result, fallback_response
                ) if compose_with_llm else fallback_response
            }

        if intent == "ticket_lookup":
            if data.get("error"):
                fallback_response = (
                    "I could not look up the ticket because the local ticket database is unavailable right now. "
                    "Please retry after the database connection is restored."
                )
                return {
                    "final_response": compose_with_llm(
                        state.get("user_input", ""), intent or "", state.get("context", {}), tool_result, fallback_response
                    ) if compose_with_llm else fallback_response
                }
            tickets = data.get("tickets", [])
            ticket_id = data.get("ticket_id", "")
            employee_id = data.get("employee_id", "")
            if state.get("context", {}).get("resume_intent") == "ticket_creation" and not ticket_id:
                context = dict(state.get("context", {}))
                context["existing_tickets_checked"] = True
                context["pending_intent"] = "ticket_creation"
                context["awaiting_create_confirmation"] = True
                context.pop("resume_intent", None)
                if tickets:
                    fallback_response = (
                        f"I found {len(tickets)} existing ticket(s) for {employee_id}. "
                        "Would you like me to create a new ticket for your current issue as well?"
                    )
                else:
                    fallback_response = (
                        f"I found no existing tickets for {employee_id}. "
                        "Would you like me to create a new ticket for your current issue?"
                    )
                return {
                    "context": context,
                    "final_response": compose_with_llm(
                        state.get("user_input", ""), intent or "", context, tool_result, fallback_response
                    ) if compose_with_llm else fallback_response
                }
            if not tickets:
                if ticket_id:
                    fallback_response = (
                        f"I could not find ticket {ticket_id}. "
                        "Please verify the ticket ID and try again."
                    )
                    return {
                        "final_response": compose_with_llm(
                            state.get("user_input", ""), intent or "", state.get("context", {}), tool_result, fallback_response
                        ) if compose_with_llm else fallback_response
                    }
                fallback_response = (
                    f"I found no tickets for {employee_id}. "
                    "If your issue is new, I can create a ticket for you."
                )
                return {
                    "final_response": compose_with_llm(
                        state.get("user_input", ""), intent or "", state.get("context", {}), tool_result, fallback_response
                    ) if compose_with_llm else fallback_response
                }
            if _looks_like_count_query(state.get("user_input", "")):
                ticket_count = len(tickets)
                fallback_response = (
                    f"Employee {employee_id} has raised {ticket_count} ticket(s). "
                    "I listed all matching tickets in the table below."
                )
                return {
                    "final_response": compose_with_llm(
                        state.get("user_input", ""), intent or "", state.get("context", {}), tool_result, fallback_response
                    ) if compose_with_llm else fallback_response
                }
            latest = tickets[0]
            if ticket_id:
                fallback_response = (
                    f"Ticket {latest.get('ticket_id')} details:\n"
                    f"Employee ID: {latest.get('employee_id')}\n"
                    f"Status: {latest.get('status')}\n"
                    f"Summary: {latest.get('summary')}\n"
                    f"Last updated: {latest.get('updated_at')}"
                )
                return {
                    "final_response": compose_with_llm(
                        state.get("user_input", ""), intent or "", state.get("context", {}), tool_result, fallback_response
                    ) if compose_with_llm else fallback_response
                }
            fallback_response = (
                f"Latest ticket for {employee_id}: {latest.get('ticket_id')}\n"
                f"Status: {latest.get('status')}\n"
                f"Summary: {latest.get('summary')}\n"
                f"Last updated: {latest.get('updated_at')}"
            )
            return {
                "final_response": compose_with_llm(
                    state.get("user_input", ""), intent or "", state.get("context", {}), tool_result, fallback_response
                ) if compose_with_llm else fallback_response
            }

        if intent == "ticket_creation":
            ticket = data.get("ticket", {})
            fallback_response = (
                "Your ticket has been created successfully.\n"
                f"Ticket ID: {ticket.get('ticket_id')}\n"
                f"Status: {ticket.get('status')}\n"
                f"Summary: {ticket.get('summary')}"
            )
            return {
                "final_response": compose_with_llm(
                    state.get("user_input", ""), intent or "", state.get("context", {}), tool_result, fallback_response
                ) if compose_with_llm else fallback_response
            }

        if intent == "ticket_update":
            if data.get("error"):
                fallback_response = (
                    "I could not update the ticket because the local ticket database is unavailable right now. "
                    "Please retry after the database connection is restored."
                )
                return {
                    "final_response": compose_with_llm(
                        state.get("user_input", ""), intent or "", state.get("context", {}), tool_result, fallback_response
                    ) if compose_with_llm else fallback_response
                }
            if data.get("not_found"):
                fallback_response = f"I could not find ticket {data.get('ticket_id')}. Please verify and try again."
                return {
                    "final_response": compose_with_llm(
                        state.get("user_input", ""), intent or "", state.get("context", {}), tool_result, fallback_response
                    ) if compose_with_llm else fallback_response
                }
            ticket = data.get("ticket", {})
            fallback_response = (
                "Ticket description updated successfully.\n"
                f"Ticket ID: {ticket.get('ticket_id')}\n"
                f"Updated Summary: {ticket.get('summary')}"
            )
            return {
                "final_response": compose_with_llm(
                    state.get("user_input", ""), intent or "", state.get("context", {}), tool_result, fallback_response
                ) if compose_with_llm else fallback_response
            }

        return {"final_response": fallback_response}

    def route_after_intent(state: GraphState) -> str:
        intent = state.get("intent", "small_talk")
        if intent == "knowledge_search":
            return "knowledge_search"
        if intent == "employee_lookup":
            return "employee_lookup"
        if intent == "system_status":
            return "system_status"
        if intent == "ticket_lookup":
            return "ticket_lookup_validate"
        if intent == "ticket_update":
            return "ticket_update_validate"
        if intent == "ticket_creation":
            return "ticket_create_validate"
        return "small_talk"

    def route_lookup_validation(state: GraphState) -> str:
        return "ticket_lookup" if state.get("lookup_ready") else "compose_response"

    def route_create_validation(state: GraphState) -> str:
        return "ticket_create" if state.get("create_ready") else "compose_response"

    graph.add_node("capture_context", capture_context)
    graph.add_node("decide_intent", decide_intent)
    graph.add_node("knowledge_search", knowledge_search_node)
    graph.add_node("employee_lookup", employee_lookup_node)
    graph.add_node("system_status", system_status_node)
    graph.add_node("ticket_lookup_validate", ticket_lookup_validate)
    graph.add_node("ticket_lookup", ticket_lookup_node)
    graph.add_node("ticket_update_validate", ticket_update_validate)
    graph.add_node("ticket_update", ticket_update_node)
    graph.add_node("ticket_create_validate", ticket_create_validate)
    graph.add_node("ticket_create", ticket_create_node)
    graph.add_node("small_talk", small_talk_node)
    graph.add_node("compose_response", compose_response)

    graph.add_edge(START, "capture_context")
    graph.add_edge("capture_context", "decide_intent")

    graph.add_conditional_edges(
        "decide_intent",
        route_after_intent,
        {
            "knowledge_search": "knowledge_search",
            "employee_lookup": "employee_lookup",
            "system_status": "system_status",
            "ticket_lookup_validate": "ticket_lookup_validate",
            "ticket_update_validate": "ticket_update_validate",
            "ticket_create_validate": "ticket_create_validate",
            "small_talk": "small_talk",
        },
    )

    graph.add_edge("knowledge_search", "compose_response")
    graph.add_edge("employee_lookup", "compose_response")
    graph.add_edge("system_status", "compose_response")
    graph.add_edge("small_talk", "compose_response")

    graph.add_conditional_edges(
        "ticket_lookup_validate",
        route_lookup_validation,
        {
            "ticket_lookup": "ticket_lookup",
            "compose_response": "compose_response",
        },
    )

    graph.add_conditional_edges(
        "ticket_create_validate",
        route_create_validation,
        {
            "ticket_create": "ticket_create",
            "compose_response": "compose_response",
        },
    )

    graph.add_conditional_edges(
        "ticket_update_validate",
        route_create_validation,
        {
            "ticket_create": "ticket_update",
            "compose_response": "compose_response",
        },
    )

    graph.add_edge("ticket_lookup", "compose_response")
    graph.add_edge("ticket_update", "compose_response")
    graph.add_edge("ticket_create", "compose_response")
    graph.add_edge("compose_response", END)

    return graph.compile()
