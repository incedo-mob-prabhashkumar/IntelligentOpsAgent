from __future__ import annotations

import logging
from typing import Any

from src.agent_graph import build_graph
from src.config import get_settings
from src.database import DatabaseStatus, initialize_database
from src.llm_router import IntentClassifier, SupportResponseGenerator
from src.logging_utils import configure_logging
from src.tools import LocalITTools


logger = logging.getLogger(__name__)


class ITSupportAgent:
    def __init__(self) -> None:
        configure_logging()
        settings = get_settings()
        self.settings = settings
        self.database, self.database_status = initialize_database(settings.postgres_dsn)
        self.tools = LocalITTools(self.database)
        model_name = (
            settings.ollama_model
            if settings.llm_provider == "ollama"
            else settings.llama_model if settings.llm_provider == "llama" else settings.openai_model
        )
        base_url = (
            settings.ollama_base_url
            if settings.llm_provider == "ollama"
            else settings.llama_base_url if settings.llm_provider == "llama" else settings.openai_base_url
        )

        self.classifier = IntentClassifier(
            model=model_name,
            base_url=base_url,
            provider=settings.llm_provider,
            azure_endpoint=settings.azure_openai_endpoint,
            azure_api_key=settings.azure_openai_api_key,
            azure_api_version=settings.azure_openai_api_version,
            azure_deployment=settings.azure_openai_deployment,
            openai_api_key=settings.openai_api_key,
            openai_model=settings.openai_model,
            openai_base_url=settings.openai_base_url,
            llama_api_key=settings.llama_api_key,
        )
        self.responder = SupportResponseGenerator(
            model=model_name,
            base_url=base_url,
            provider=settings.llm_provider,
            azure_endpoint=settings.azure_openai_endpoint,
            azure_api_key=settings.azure_openai_api_key,
            azure_api_version=settings.azure_openai_api_version,
            azure_deployment=settings.azure_openai_deployment,
            openai_api_key=settings.openai_api_key,
            openai_model=settings.openai_model,
            openai_base_url=settings.openai_base_url,
            llama_api_key=settings.llama_api_key,
        )
        self.graph = build_graph(self.tools, self.classifier.classify, self.responder.compose)

    def handle_message(
        self,
        user_message: str,
        context: dict[str, Any] | None = None,
    ) -> tuple[str, dict[str, Any], dict[str, Any]]:
        state_input = {
            "user_input": user_message,
            "context": context or {},
        }

        try:
            state_output = self.graph.invoke(state_input)
            response = state_output.get("final_response", "I could not generate a response.")
            next_context = state_output.get("context", context or {})
            trace = {
                "intent": state_output.get("intent"),
                "missing_fields": state_output.get("missing_fields", []),
                "tool_result": state_output.get("tool_result", {}),
            }
            return response, next_context, trace
        except Exception as exc:
            logger.exception("Agent execution failed")
            return (
                (
                    "I hit an internal error while processing your request. "
                    "Please check the configured LLM service and PostgreSQL connection, then try again."
                ),
                context or {},
                {"error": str(exc)},
            )

    def get_data_snapshot(self) -> dict[str, list[dict[str, Any]]]:
        return {
            "employees": self.tools.list_employees(),
            "tickets": self.tools.list_tickets(),
            "knowledge_base": self.tools.list_knowledge_articles(),
        }
