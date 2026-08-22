---
applyTo: "src/**/*.py"
---

# IT Support Agent Rules

Use these rules when editing agent runtime code in this repository.

## Architecture Rules
- Preserve the layered architecture:
  - UI: app.py
  - Service: src/service.py
  - Orchestration: src/agent_graph.py
  - LLM routing/response: src/llm_router.py
  - Tools/data access: src/tools.py
  - Data model/init: src/models.py and src/database.py
- Keep business logic in the graph and tools, not in Streamlit UI.

## Workflow Rules
- Keep LangGraph stateful behavior intact for multi-turn flows.
- Do not remove required core tool paths:
  - knowledge_search
  - ticket_lookup
  - ticket_creation
- Maintain validation before write operations.
- Preserve duplicate prevention and graceful failure messages.

## Intent and Memory Rules
- Prefer deterministic routing for strict identifiers (EMP, TKT) and confirmations.
- Use LLM classification only as fallback for open language.
- Any workflow that requests follow-up input must persist pending context in state.

## Response Rules
- Final response must stay grounded in tool output.
- Distinguish retrieved facts from recommendations.
- Keep structured tool payloads compatible with tabular rendering in app.py.

## Safety Rules
- Never invent ticket IDs or statuses.
- Validate employee existence before ticket creation.
- Handle DB/tool failures with user-safe responses.

## Testing Rules
- Update unit tests in tests/test_agent_graph.py for behavior changes.
- Keep model/schema assumptions aligned with tests/test_database.py.
