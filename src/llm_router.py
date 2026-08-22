from __future__ import annotations

import json
import re
from typing import Any

from langchain_ollama import ChatOllama
from langchain_openai import AzureChatOpenAI


VALID_INTENTS = {
    "knowledge_search",
    "employee_lookup",
    "ticket_lookup",
    "ticket_update",
    "ticket_creation",
    "system_status",
    "small_talk",
}


class IntentClassifier:
    def __init__(
        self,
        model: str,
        base_url: str,
        provider: str = "ollama",
        azure_endpoint: str = "",
        azure_api_key: str = "",
        azure_api_version: str = "2024-10-21",
        azure_deployment: str = "",
    ) -> None:
        if provider == "azure_openai":
            if not all([azure_endpoint, azure_api_key, azure_deployment]):
                raise ValueError(
                    "Azure OpenAI requires AZURE_OPENAI_ENDPOINT, "
                    "AZURE_OPENAI_API_KEY, and AZURE_OPENAI_DEPLOYMENT."
                )
            self.llm = AzureChatOpenAI(
                azure_endpoint=azure_endpoint,
                api_key=azure_api_key,
                api_version=azure_api_version,
                azure_deployment=azure_deployment,
                temperature=0,
            )
        elif provider == "ollama":
            self.llm = ChatOllama(model=model, base_url=base_url, temperature=0)
        else:
            raise ValueError("LLM_PROVIDER must be either 'ollama' or 'azure_openai'.")

    def _heuristic_fallback(self, query: str) -> str:
        q = query.lower()
        if any(token in q for token in ["employee details", "employee info", "employee information", "employee profile"]):
            return "employee_lookup"
        if any(token in q for token in ["modify", "update", "change", "edit", "correct"]) and "ticket" in q:
            return "ticket_update"
        if any(token in q for token in ["system status", "service status", "outage", "health", "down", "operational"]):
            return "system_status"
        if any(token in q for token in ["raise", "create", "open", "log a ticket", "new ticket"]):
            return "ticket_creation"
        if any(token in q for token in ["status", "ticket", "existing issue", "my issue"]):
            return "ticket_lookup"
        if any(token in q for token in ["how", "reset", "configure", "setup", "install", "unable"]):
            return "knowledge_search"
        return "small_talk"

    def classify(self, query: str, context: dict[str, Any] | None = None) -> str:
        prompt = (
            "You are an IT support request intent classifier. "
            "Classify the request into exactly one of these labels: "
            "knowledge_search, employee_lookup, ticket_lookup, ticket_update, ticket_creation, system_status, small_talk.\n"
            "Return strict JSON only, with this schema: "
            '{"intent":"<one label>","reason":"<short reason>"}.\n'
            f"User request: {query}\n"
            f"Context: {json.dumps(context or {}, ensure_ascii=True)}"
        )

        try:
            result = self.llm.invoke(prompt)
            content = str(getattr(result, "content", "")).strip()
            match = re.search(r"\{.*\}", content, re.DOTALL)
            payload = json.loads(match.group(0) if match else content)
            intent = str(payload.get("intent", "")).strip()
            if intent in VALID_INTENTS:
                return intent
        except Exception:
            pass

        return self._heuristic_fallback(query)


class SupportResponseGenerator:
    def __init__(
        self,
        model: str,
        base_url: str,
        provider: str = "ollama",
        azure_endpoint: str = "",
        azure_api_key: str = "",
        azure_api_version: str = "2024-10-21",
        azure_deployment: str = "",
    ) -> None:
        if provider == "azure_openai":
            if not all([azure_endpoint, azure_api_key, azure_deployment]):
                raise ValueError(
                    "Azure OpenAI requires AZURE_OPENAI_ENDPOINT, "
                    "AZURE_OPENAI_API_KEY, and AZURE_OPENAI_DEPLOYMENT."
                )
            self.llm = AzureChatOpenAI(
                azure_endpoint=azure_endpoint,
                api_key=azure_api_key,
                api_version=azure_api_version,
                azure_deployment=azure_deployment,
                temperature=0.2,
            )
        elif provider == "ollama":
            self.llm = ChatOllama(model=model, base_url=base_url, temperature=0.2)
        else:
            raise ValueError("LLM_PROVIDER must be either 'ollama' or 'azure_openai'.")

    def compose(
        self,
        user_input: str,
        intent: str,
        context: dict[str, Any],
        tool_result: dict[str, Any],
        fallback_response: str,
    ) -> str:
        prompt = (
            "You are an AI IT support assistant. Generate a helpful final reply for the user.\n"
            "Rules:\n"
            "1) Use ONLY facts present in the provided tool result and context.\n"
            "2) Do not invent ticket IDs, statuses, employee data, or system facts.\n"
            "3) Keep the response concise and professional.\n"
            "4) Include a short reasoning line that explains why this answer/action is appropriate.\n"
            "5) If the tool result has errors, clearly mention the limitation.\n"
            "\n"
            f"User input: {user_input}\n"
            f"Intent: {intent}\n"
            f"Context: {json.dumps(context or {}, ensure_ascii=True, default=str)}\n"
            f"Tool result: {json.dumps(tool_result or {}, ensure_ascii=True, default=str)}\n"
            f"Fallback response: {fallback_response}\n"
            "\n"
            "Return plain text only."
        )
        try:
            result = self.llm.invoke(prompt)
            content = str(getattr(result, "content", "")).strip()
            return content or fallback_response
        except Exception:
            return fallback_response
