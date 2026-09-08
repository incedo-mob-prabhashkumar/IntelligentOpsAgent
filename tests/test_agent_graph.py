from __future__ import annotations

import unittest

from src.agent_graph import build_graph


class StubTools:
    def __init__(self) -> None:
        self.created_tickets: list[dict[str, str]] = []
        self.updated_tickets: list[dict[str, str]] = []

    def search_knowledge(self, query: str, top_k: int = 3) -> dict:
        if "install python" in query.lower():
            return {
                "query": query,
                "matches": [],
                "count": 0,
            }
        return {
            "query": query,
            "matches": [
                {
                    "article_id": "KB-001",
                    "title": "Reset VPN Password",
                    "content": "Use the self-service portal.",
                }
            ],
            "count": 1,
        }

    def get_system_status(self, query: str | None = None) -> dict:
        return {
            "statuses": [
                {
                    "service": "VPN Gateway",
                    "status": "operational",
                    "updated_at": "2026-08-22T08:00:00Z",
                },
                {
                    "service": "Email Service",
                    "status": "degraded",
                    "updated_at": "2026-08-22T07:45:00Z",
                },
            ],
            "count": 2,
        }

    def lookup_employee_by_id(self, employee_id: str) -> dict:
        if employee_id.upper() == "EMP2048":
            return {
                "employee_id": "EMP2048",
                "employees": [
                    {
                        "employee_id": "EMP2048",
                        "name": "Diya Nair",
                        "department": "Engineering",
                        "email": "diya.nair@example.com",
                        "location": "Pune",
                    }
                ],
                "count": 1,
            }
        return {"employee_id": employee_id.upper(), "employees": [], "count": 0}

    def lookup_tickets(self, employee_id: str, query: str | None = None) -> dict:
        return {
            "employee_id": employee_id,
            "tickets": [
                {
                    "ticket_id": "TKT1001",
                    "status": "open",
                    "summary": "VPN disconnects every 10 minutes",
                    "updated_at": "2026-08-20T11:10:00Z",
                }
            ],
            "count": 1,
        }

    def lookup_ticket_by_id(self, ticket_id: str) -> dict:
        if ticket_id.upper() in {"TKT1001", "TKT1004"}:
            return {
                "ticket_id": ticket_id.upper(),
                "employee_id": "EMP1024",
                "tickets": [
                    {
                        "ticket_id": ticket_id.upper(),
                        "employee_id": "EMP1024",
                        "status": "open",
                        "summary": "VPN disconnects every 10 minutes" if ticket_id.upper() == "TKT1001" else "but wifi dont exists",
                        "updated_at": "2026-08-20T11:10:00Z",
                    }
                ],
                "count": 1,
            }
        return {"ticket_id": ticket_id, "employee_id": "", "tickets": [], "count": 0}

    def employee_exists(self, employee_id: str) -> bool:
        return employee_id.upper() == "EMP1024"

    def find_duplicate_ticket(self, employee_id: str, issue_summary: str) -> dict | None:
        if "disconnect" in issue_summary.lower():
            return {
                "ticket_id": "TKT1001",
                "status": "open",
                "summary": issue_summary,
            }
        return None

    def create_ticket(
        self,
        employee_id: str,
        issue_summary: str,
        category: str = "general",
        priority: str = "medium",
    ) -> dict:
        payload = {
            "ticket_id": "TKT2001",
            "employee_id": employee_id,
            "summary": issue_summary,
            "category": category,
            "priority": priority,
            "status": "open",
        }
        self.created_tickets.append(payload)
        return {"created": True, "ticket": payload}

    def update_ticket_summary(self, ticket_id: str, new_summary: str) -> dict:
        payload = {
            "ticket_id": ticket_id.upper(),
            "employee_id": "EMP1024",
            "summary": new_summary,
            "status": "open",
        }
        self.updated_tickets.append(payload)
        return {"updated": True, "ticket": payload, "ticket_id": ticket_id.upper()}


class AgentGraphTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tools = StubTools()
        self.graph = build_graph(self.tools, self.classify)

    @staticmethod
    def classify(query: str, context: dict) -> str:
        q = query.lower()
        if "employee" in q and any(token in q for token in ["details", "info", "information", "profile"]):
            return "employee_lookup"
        if "system" in q or "service" in q or "outage" in q:
            return "system_status"
        if any(token in q for token in ["how", "reset", "configure", "setup", "install", "unable"]):
            return "knowledge_search"
        if "reset" in q:
            return "knowledge_search"
        if "status" in q:
            return "ticket_lookup"
        if any(token in q for token in ["modify", "update", "change", "edit", "correct"]):
            return "ticket_update"
        if "ticket" in q or "vpn" in q:
            return "ticket_creation"
        return "small_talk"

    def test_knowledge_search_route_returns_article(self) -> None:
        result = self.graph.invoke({"user_input": "How do I reset my VPN password?", "context": {}})
        self.assertEqual(result["intent"], "knowledge_search")
        self.assertIn("KB-001", result["final_response"])

    def test_system_status_route_returns_status_summary(self) -> None:
        result = self.graph.invoke({"user_input": "What is the system status today?", "context": {}})
        self.assertEqual(result["intent"], "system_status")
        self.assertIn("Attention required for", result["final_response"])

    def test_incident_report_prefers_knowledge_search_before_ticket_creation(self) -> None:
        result = self.graph.invoke({"user_input": "VPN not working", "context": {}})
        self.assertEqual(result["intent"], "knowledge_search")
        self.assertIn("KB-001", result["final_response"])

    def test_typo_incident_report_does_not_fall_back_to_small_talk(self) -> None:
        result = self.graph.invoke({"user_input": "creen broken if my laptop", "context": {}})
        self.assertEqual(result["intent"], "knowledge_search")

    def test_system_status_fallback_message_is_explicit(self) -> None:
        class StatusFallbackTools(StubTools):
            def get_system_status(self, query: str | None = None) -> dict:
                return {
                    "statuses": [
                        {
                            "service": "Email Service",
                            "status": "degraded",
                            "updated_at": "2026-08-22T07:45:00Z",
                        }
                    ],
                    "count": 1,
                    "fallback_to_all": True,
                }

        graph = build_graph(StatusFallbackTools(), self.classify)
        result = graph.invoke({"user_input": "vpn not working", "context": {}})
        self.assertEqual(result["intent"], "knowledge_search")

        # Force an explicit status query so the system_status node runs.
        result_status = graph.invoke({"user_input": "system status for vpn not working", "context": {}})
        self.assertEqual(result_status["intent"], "system_status")
        self.assertIn("did not find an exact service match", result_status["final_response"].lower())

    def test_employee_lookup_returns_employee_details(self) -> None:
        result = self.graph.invoke({"user_input": "get employee details EMP2048", "context": {}})
        self.assertEqual(result["intent"], "employee_lookup")
        self.assertIn("EMP2048", result["final_response"])

    def test_ticket_lookup_requests_missing_employee_id(self) -> None:
        result = self.graph.invoke({"user_input": "What is the status of my laptop issue?", "context": {}})
        self.assertEqual(result["intent"], "ticket_lookup")
        self.assertEqual(result["missing_fields"], ["employee_id"])
        self.assertEqual(result["context"]["pending_intent"], "ticket_lookup")

    def test_employee_issue_queries_route_to_ticket_lookup(self) -> None:
        for query in [
            "get all issues of EMP1024",
            "get all ticket raised by employee EMP1024",
            "all tickets raised by EMP1024",
        ]:
            with self.subTest(query=query):
                result = self.graph.invoke({"user_input": query, "context": {}})
                self.assertEqual(result["intent"], "ticket_lookup")
                self.assertIn("TKT1001", result["final_response"])

    def test_follow_up_employee_id_completes_pending_lookup(self) -> None:
        first = self.graph.invoke({"user_input": "What is the status of my laptop issue?", "context": {}})
        second = self.graph.invoke({"user_input": "EMP1024", "context": first["context"]})
        self.assertEqual(second["intent"], "ticket_lookup")
        self.assertIn("TKT1001", second["final_response"])

    def test_direct_ticket_id_lookup_does_not_require_employee_id(self) -> None:
        result = self.graph.invoke({"user_input": "TKT1001, get this ticket info", "context": {}})
        self.assertEqual(result["intent"], "ticket_lookup")
        self.assertIn("Ticket TKT1001 details", result["final_response"])

    def test_employee_count_query_ignores_stale_ticket_id(self) -> None:
        context = {"employee_id": "EMP1024", "ticket_id": "TKT1001"}
        result = self.graph.invoke(
            {"user_input": "EMP1024, how many ticket raised by the employee", "context": context}
        )
        self.assertEqual(result["intent"], "ticket_lookup")
        self.assertIn("has raised", result["final_response"])

    def test_ticket_creation_blocks_duplicate(self) -> None:
        result = self.graph.invoke(
            {
                "user_input": "Please create a ticket for VPN disconnect issue EMP1024",
                "context": {},
            }
        )
        self.assertEqual(result["intent"], "ticket_creation")
        self.assertIn("did not create a duplicate ticket", result["final_response"])
        self.assertEqual(self.tools.created_tickets, [])

    def test_ticket_creation_requires_employee_id_before_write(self) -> None:
        result = self.graph.invoke(
            {
                "user_input": "Please create a ticket for my laptop screen issue",
                "context": {},
            }
        )
        self.assertEqual(result["intent"], "ticket_creation")
        self.assertIn("employee ID", result["final_response"])
        self.assertEqual(result["context"].get("pending_intent"), "ticket_creation")
        self.assertEqual(self.tools.created_tickets, [])

    def test_issue_status_query_routes_to_ticket_lookup(self) -> None:
        result = self.graph.invoke(
            {
                "user_input": "what is the status of bios failed issue",
                "context": {"employee_id": "EMP1024"},
            }
        )
        self.assertEqual(result["intent"], "ticket_lookup")
        self.assertIn("TKT1001", result["final_response"])

    def test_ticket_creation_follow_up_uses_saved_issue_summary(self) -> None:
        first = self.graph.invoke({"user_input": "My email is broken. Please create a ticket.", "context": {}})
        second = self.graph.invoke({"user_input": "EMP1024", "context": first["context"]})
        self.assertEqual(second["intent"], "ticket_creation")
        self.assertIn("Would you like me to check existing tickets", second["final_response"])

        third = self.graph.invoke({"user_input": "Yes", "context": second["context"]})
        self.assertEqual(third["intent"], "ticket_creation")
        self.assertIn("created successfully", third["final_response"])
        self.assertEqual(self.tools.created_tickets[0]["employee_id"], "EMP1024")

    def test_bios_ticket_creation_is_visible_after_lookup_confirmation(self) -> None:
        first = self.graph.invoke({"user_input": "bios failed", "context": {}})
        self.assertEqual(first["intent"], "ticket_creation")
        self.assertIn("employee ID", first["final_response"])

        second = self.graph.invoke({"user_input": "EMP1024", "context": first["context"]})
        self.assertEqual(second["intent"], "ticket_creation")
        self.assertIn("Would you like me to check existing tickets", second["final_response"])

        third = self.graph.invoke({"user_input": "yes", "context": second["context"]})
        self.assertEqual(third["intent"], "ticket_creation")
        self.assertIn("created successfully", third["final_response"])
        self.assertIn("bios failed", third["final_response"])
        self.assertEqual(self.tools.created_tickets[-1]["employee_id"], "EMP1024")

    def test_ticket_update_changes_description(self) -> None:
        result = self.graph.invoke(
            {
                "user_input": "TKT1004, modify ticket description : wifi network not visible",
                "context": {},
            }
        )
        self.assertEqual(result["intent"], "ticket_update")
        self.assertIn("updated successfully", result["final_response"])
        self.assertEqual(self.tools.updated_tickets[0]["ticket_id"], "TKT1004")
        self.assertEqual(self.tools.updated_tickets[0]["summary"], "wifi network not visible")

    def test_ticket_update_reports_missing_required_fields(self) -> None:
        result = self.graph.invoke(
            {
                "user_input": "modify ticket",
                "context": {},
            }
        )
        self.assertEqual(result["intent"], "ticket_update")
        self.assertIn("ticket ID", result["final_response"])
        self.assertIn("new ticket description", result["final_response"])
        self.assertEqual(result["missing_fields"], ["ticket_id", "updated_summary"])

    def test_ticket_creation_tool_failure_is_graceful(self) -> None:
        class FailingCreateTools(StubTools):
            def find_duplicate_ticket(self, employee_id: str, issue_summary: str) -> dict | None:
                return None

            def create_ticket(
                self,
                employee_id: str,
                issue_summary: str,
                category: str = "general",
                priority: str = "medium",
            ) -> dict:
                return {
                    "created": False,
                    "ticket": {},
                    "error": "Database unavailable",
                }

        graph = build_graph(FailingCreateTools(), self.classify)
        result = graph.invoke(
            {
                "user_input": "Please create a ticket for screen flicker EMP1024",
                "context": {},
            }
        )
        self.assertEqual(result["intent"], "ticket_creation")
        self.assertIn("could not create the ticket", result["final_response"])
        self.assertIn("database", result["final_response"].lower())

    def test_ticket_creation_response_uses_tool_ticket_id(self) -> None:
        result = self.graph.invoke(
            {
                "user_input": "Please create a ticket for keyboard issue EMP1024",
                "context": {},
            }
        )
        self.assertEqual(result["intent"], "ticket_creation")
        self.assertIn("TKT2001", result["final_response"])
        self.assertIn("created successfully", result["final_response"])

    def test_kb_no_match_starts_stateful_ticket_creation_flow(self) -> None:
        first = self.graph.invoke({"user_input": "i am unable to install python", "context": {}})
        self.assertEqual(first["intent"], "knowledge_search")
        self.assertEqual(first["context"]["pending_intent"], "ticket_creation")
        self.assertIn("employee ID", first["final_response"])

        second = self.graph.invoke({"user_input": "EMP1024", "context": first["context"]})
        self.assertEqual(second["intent"], "ticket_creation")
        self.assertIn("Would you like me to check existing tickets", second["final_response"])

        third = self.graph.invoke({"user_input": "Yes", "context": second["context"]})
        self.assertEqual(third["intent"], "ticket_creation")
        self.assertIn("created successfully", third["final_response"])

    def test_issue_text_during_lookup_confirmation_continues_creation(self) -> None:
        context = {
            "employee_id": "EMP1024",
            "pending_intent": "ticket_creation",
            "awaiting_lookup_confirmation": True,
            "proposed_issue_summary": "i have an issue",
        }
        result = self.graph.invoke({"user_input": "i am unable to install python", "context": context})
        self.assertEqual(result["intent"], "ticket_creation")
        self.assertIn("created successfully", result["final_response"])

    def test_issue_description_with_device_keywords_routes_to_ticket_creation(self) -> None:
        result = self.graph.invoke({"user_input": "its hardware issue", "context": {}})
        self.assertEqual(result["intent"], "ticket_creation")
        self.assertIn("employee ID", result["final_response"])

    def test_video_blurry_issue_routes_to_ticket_creation(self) -> None:
        result = self.graph.invoke({"user_input": "video is blurry", "context": {}})
        self.assertEqual(result["intent"], "ticket_creation")
        self.assertIn("employee ID", result["final_response"])

    def test_direct_create_confirmation_after_lookup_moves_to_ticket_creation(self) -> None:
        first = self.graph.invoke({"user_input": "i am unable to install python", "context": {}})
        self.assertEqual(first["intent"], "knowledge_search")

        second = self.graph.invoke({"user_input": "EMP1024", "context": first["context"]})
        self.assertEqual(second["intent"], "ticket_creation")
        self.assertIn("Would you like me to check existing tickets", second["final_response"])

        third = self.graph.invoke({"user_input": "yes create new", "context": second["context"]})
        self.assertEqual(third["intent"], "ticket_creation")
        self.assertIn("created successfully", third["final_response"])

    def test_negative_follow_up_after_lookup_skips_existing_ticket_check(self) -> None:
        first = self.graph.invoke({"user_input": "i am unable to install python", "context": {}})
        second = self.graph.invoke({"user_input": "EMP1024", "context": first["context"]})

        third = self.graph.invoke({"user_input": "no", "context": second["context"]})
        self.assertEqual(third["intent"], "ticket_creation")
        self.assertIn("created successfully", third["final_response"])

    def test_greeting_returns_friendly_capabilities(self) -> None:
        result = self.graph.invoke({"user_input": "hello", "context": {}})
        self.assertEqual(result["intent"], "small_talk")
        self.assertIn("AI IT support assistant", result["final_response"])
        self.assertIn("ticket creation", result["final_response"])

    def test_thanks_returns_polite_follow_up(self) -> None:
        result = self.graph.invoke({"user_input": "thanks", "context": {}})
        self.assertEqual(result["intent"], "small_talk")
        self.assertIn("You are welcome", result["final_response"])


if __name__ == "__main__":
    unittest.main()
