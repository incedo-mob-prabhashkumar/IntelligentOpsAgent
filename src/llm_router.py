from __future__ import annotations

import json
import logging
import os
from functools import lru_cache
from typing import Any

import numpy as np
from langchain_ollama import ChatOllama
from langchain_openai import AzureChatOpenAI, ChatOpenAI
from pydantic import SecretStr


logger = logging.getLogger(__name__)


VALID_INTENTS = {
    "knowledge_search",
    "employee_lookup",
    "ticket_lookup",
    "ticket_update",
    "ticket_creation",
    "system_status",
    "small_talk",
}


INTENT_PROTOTYPES: dict[str, list[str]] = {
    "knowledge_search": [
        "How do I reset my VPN password?",
        "Steps to configure outlook sync",
        "How can I install python on my laptop",
        "Documentation for troubleshooting wifi setup",
    ],
    "employee_lookup": [
        "Show employee details for EMP1024",
        "Get employee profile information",
        "Find employee contact details",
    ],
    "ticket_lookup": [
        "What is the status of my ticket",
        "Check existing issue progress",
        "Lookup ticket TKT1001",
        "How many tickets has EMP1024 raised",
        "Get all tickets raised by EMP1024",
        "Show all issues for EMP1024",
        "Find all tickets raised by employee EMP1024",
        "All tickets raised by EMP1024",
    ],
    "ticket_update": [
        "Update ticket TKT1004 summary",
        "Modify my existing ticket description",
        "Correct ticket details",
    ],
    "ticket_creation": [
        "My VPN is not working, please raise a ticket",
        "Create a new support ticket",
        "Open a ticket for laptop issue",
        "I cannot connect to wifi and need a ticket",
    ],
    "system_status": [
        "What is the system status today",
        "Is there any outage in VPN gateway",
        "Check service health for email",
        "Are systems operational",
    ],
    "small_talk": [
        "Hello",
        "Thanks for your help",
        "Good morning",
    ],
}


@lru_cache(maxsize=1)
def _get_intent_embedding_model() -> Any:
    from sentence_transformers import SentenceTransformer

    model_name = os.getenv("INTENT_EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
    return SentenceTransformer(model_name)


@lru_cache(maxsize=1)
def _get_intent_centroids() -> dict[str, np.ndarray]:
    model = _get_intent_embedding_model()
    centroids: dict[str, np.ndarray] = {}
    for intent, samples in INTENT_PROTOTYPES.items():
        prototype_embeddings = model.encode(
            samples,
            normalize_embeddings=True,
            convert_to_numpy=True,
        )
        centroid = np.mean(prototype_embeddings, axis=0)
        centroid_norm = np.linalg.norm(centroid)
        if centroid_norm == 0:
            continue
        centroids[intent] = centroid / centroid_norm
    return centroids


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
        openai_api_key: str = "",
        openai_model: str = "gpt-4o-mini",
        openai_base_url: str = "https://api.openai.com/v1",
        llama_api_key: str = "",
    ) -> None:
        if provider == "azure_openai":
            if not all([azure_endpoint, azure_api_key, azure_deployment]):
                raise ValueError(
                    "Azure OpenAI requires AZURE_OPENAI_ENDPOINT, "
                    "AZURE_OPENAI_API_KEY, and AZURE_OPENAI_DEPLOYMENT."
                )
            self.llm = AzureChatOpenAI(
                azure_endpoint=azure_endpoint,
                api_key=SecretStr(azure_api_key),
                api_version=azure_api_version,
                azure_deployment=azure_deployment,
                temperature=0,
            )
        elif provider == "openai":
            if not openai_api_key:
                raise ValueError("OpenAI requires OPENAI_API_KEY.")
            self.llm = ChatOpenAI(
                model=openai_model or model,
                api_key=SecretStr(openai_api_key),
                base_url=openai_base_url or None,
                temperature=0,
            )
        elif provider == "ollama":
            self.llm = ChatOllama(model=model, base_url=base_url, temperature=0)
        elif provider == "llama":
            self.llm = ChatOpenAI(
                model=model or "llama3.1:8b",
                api_key=SecretStr(llama_api_key or "not-needed"),
                base_url=base_url or "http://localhost:8080/v1",
                temperature=0,
            )
        else:
            raise ValueError("LLM_PROVIDER must be one of: 'ollama', 'llama', 'azure_openai', or 'openai'.")

        self._tool_selector = None
        try:
            from src.tool_selector import SupportToolSelector

            self._tool_selector = SupportToolSelector(self.llm)
        except Exception:
            logger.exception("LangChain LLMToolSelectorMiddleware is unavailable; using heuristic routing")
            self._tool_selector = None

    def _semantic_intent(self, query: str) -> str | None:
        try:
            model = _get_intent_embedding_model()
            centroids = _get_intent_centroids()
            query_embedding = model.encode([query], normalize_embeddings=True, convert_to_numpy=True)[0]

            best_intent = None
            best_score = -1.0
            second_best = -1.0

            for intent, centroid in centroids.items():
                score = float(np.dot(query_embedding, centroid))

                if score > best_score:
                    second_best = best_score
                    best_score = score
                    best_intent = intent
                elif score > second_best:
                    second_best = score

            if best_intent is None:
                return None

            # Confidence guardrails to avoid unstable routing on weak semantic matches.
            if best_score < 0.30:
                return None
            if (best_score - second_best) < 0.03:
                return None

            return best_intent if best_intent in VALID_INTENTS else None
        except Exception:
            logger.exception("Semantic intent classification failed; falling back to heuristics")
            return None

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
        semantic_intent = self._semantic_intent(query)
        if semantic_intent in VALID_INTENTS:
            return semantic_intent

        if self._tool_selector is not None:
            try:
                selected = self._tool_selector.select_intent(query, context)
                if selected in VALID_INTENTS:
                    return selected
            except Exception:
                pass

        heuristic_intent = self._heuristic_fallback(query)
        return heuristic_intent


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
        openai_api_key: str = "",
        openai_model: str = "gpt-4o-mini",
        openai_base_url: str = "https://api.openai.com/v1",
        llama_api_key: str = "",
    ) -> None:
        if provider == "azure_openai":
            if not all([azure_endpoint, azure_api_key, azure_deployment]):
                raise ValueError(
                    "Azure OpenAI requires AZURE_OPENAI_ENDPOINT, "
                    "AZURE_OPENAI_API_KEY, and AZURE_OPENAI_DEPLOYMENT."
                )
            self.llm = AzureChatOpenAI(
                azure_endpoint=azure_endpoint,
                api_key=SecretStr(azure_api_key),
                api_version=azure_api_version,
                azure_deployment=azure_deployment,
                temperature=0.2,
            )
        elif provider == "openai":
            if not openai_api_key:
                raise ValueError("OpenAI requires OPENAI_API_KEY.")
            self.llm = ChatOpenAI(
                model=openai_model or model,
                api_key=SecretStr(openai_api_key),
                base_url=openai_base_url or None,
                temperature=0.2,
            )
        elif provider == "ollama":
            self.llm = ChatOllama(model=model, base_url=base_url, temperature=0.2)
        elif provider == "llama":
            self.llm = ChatOpenAI(
                model=model or "llama3.1:8b",
                api_key=SecretStr(llama_api_key or "not-needed"),
                base_url=base_url or "http://localhost:8080/v1",
                temperature=0.2,
            )
        else:
            raise ValueError("LLM_PROVIDER must be one of: 'ollama', 'llama', 'azure_openai', or 'openai'.")

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
