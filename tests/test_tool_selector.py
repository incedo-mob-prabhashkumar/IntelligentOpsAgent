from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from src.llm_router import VALID_INTENTS, IntentClassifier
from src.tool_selector import SupportToolSelector, build_support_tool_catalog


class ToolSelectorTests(unittest.TestCase):
    def test_catalog_covers_all_routed_intents(self) -> None:
        names = {tool.name for tool in build_support_tool_catalog()}
        self.assertEqual(names, VALID_INTENTS)

    def test_selector_maps_middleware_choice_to_intent(self) -> None:
        selector = SupportToolSelector.__new__(SupportToolSelector)
        selector.catalog = build_support_tool_catalog()
        selector.model = MagicMock()

        def wrap_model_call(request, handler):
            chosen = [tool for tool in request.tools if tool.name == "ticket_lookup"]
            return handler(request.override(tools=chosen))

        selector.middleware = MagicMock()
        selector.middleware.wrap_model_call.side_effect = wrap_model_call

        intent = selector.select_intent("What is the status of my laptop issue?", {})
        self.assertEqual(intent, "ticket_lookup")

    def test_selector_uses_deterministic_override_for_incident_reports(self) -> None:
        selector = SupportToolSelector.__new__(SupportToolSelector)
        selector.catalog = build_support_tool_catalog()
        selector.model = MagicMock()
        selector.middleware = MagicMock()

        intent = selector.select_intent("screen broken if my laptop", {})
        self.assertEqual(intent, "knowledge_search")
        selector.middleware.wrap_model_call.assert_not_called()

    def test_classifier_uses_semantic_before_tool_selector(self) -> None:
        classifier = IntentClassifier.__new__(IntentClassifier)
        classifier._semantic_intent = MagicMock(return_value="knowledge_search")
        classifier._tool_selector = MagicMock()
        classifier._tool_selector.select_intent.return_value = "ticket_creation"
        intent = classifier.classify("VPN is flaky, what should I do?", {})
        self.assertEqual(intent, "knowledge_search")
        classifier._tool_selector.select_intent.assert_not_called()

    def test_classifier_falls_back_when_selector_returns_nothing(self) -> None:
        classifier = IntentClassifier.__new__(IntentClassifier)
        classifier._semantic_intent = MagicMock(return_value=None)
        classifier._tool_selector = MagicMock()
        classifier._tool_selector.select_intent.return_value = None
        intent = classifier.classify("How do I reset my VPN password?", {})
        self.assertEqual(intent, "knowledge_search")
        classifier._semantic_intent.assert_called_once()
        classifier._tool_selector.select_intent.assert_called_once()

    def test_classifier_uses_semantic_language_understanding_for_employee_ticket_queries(self) -> None:
        classifier = IntentClassifier.__new__(IntentClassifier)
        classifier._semantic_intent = MagicMock(return_value="ticket_lookup")
        classifier._tool_selector = MagicMock()
        classifier._tool_selector.select_intent.return_value = "small_talk"
        intent = classifier.classify("get all tickets raised by EMP1024", {})
        self.assertEqual(intent, "ticket_lookup")


if __name__ == "__main__":
    unittest.main()
