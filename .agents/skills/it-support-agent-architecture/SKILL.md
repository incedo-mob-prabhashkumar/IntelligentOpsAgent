# Skill: IT Support Agent Architecture

## Purpose
Use this skill when working on this repository's AI IT support assistant to keep changes aligned with required agentic behavior and business constraints.

## When to Use
- Modify intent routing or state transitions.
- Add or change tool behavior.
- Update ticket creation/lookup/update workflows.
- Adjust Streamlit behavior tied to tool traces and tables.
- Diagnose wrong routing, missing context continuity, or duplicate checks.

## Required Invariants
- Keep LangGraph as orchestration engine.
- Preserve core tools:
  - Knowledge Search
  - Ticket Lookup
  - Ticket Creation
- Retain stateful multi-turn flow with context memory.
- Validate required fields before write actions.
- Avoid fabricated business data.

## State Checklist
- Issue context survives across turns.
- Employee ID is captured and reused.
- Pending intent is explicit when waiting for follow-up.
- Confirmation branches (yes/no/details) do not drop context.

## Routing Checklist
- Rule-first for strict formats (EMP/TKT/confirmation tokens).
- LLM fallback for open-ended language.
- No route should accidentally discard actionable user input.

## Tool Contract Checklist
- Every tool returns structured, predictable dict payloads.
- Errors are explicit and non-throwing to the user layer.
- Table-ready fields are present for Streamlit rendering.

## Testing Checklist
- Add/adjust unit tests for new state transitions.
- Ensure conversation regressions are covered in tests/test_agent_graph.py.
- Keep schema-level expectations green.

## Output Style
- Explain architecture-impact first.
- Then explain exact behavior delta.
- Then confirm tests and risks.
