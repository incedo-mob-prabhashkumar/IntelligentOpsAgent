# Tools and Routing Guide

This document explains what each tool does, when it is selected, and what it returns.

## 1) Intent Categories
The assistant routes user requests into these categories:
- knowledge_search
- ticket_lookup
- ticket_creation
- ticket_update
- employee_lookup
- system_status
- small_talk

## 2) Tool Overview

### knowledge_search
Purpose:
- Finds IT troubleshooting guidance from the local knowledge base.

Typical inputs:
- How-to questions (reset, configure, install, fix).
- Incident-style messages that do not explicitly request ticket creation.

Execution:
- Semantic ranking with SentenceTransformer.
- Lexical fallback when semantic retrieval is unavailable or weak.

Output shape:
- query
- matches (list of KB articles)
- count
- source
- retrieval

### ticket_lookup
Purpose:
- Retrieves existing tickets by employee ID or ticket ID.

Typical inputs:
- "What is my ticket status?"
- "Show TKT1004"
- "How many tickets has EMP1024 raised?"

Validation:
- Requires employee ID unless a ticket ID is supplied.
- Validates employee existence for employee-based lookup.

Output shape:
- employee_id or ticket_id
- tickets (list)
- count
- source

### ticket_creation
Purpose:
- Creates a new support ticket.

Typical inputs:
- "Create a ticket for VPN issue"
- "Open a new ticket for laptop screen problem"

Validation and safety:
- Requires employee ID.
- Requires issue summary.
- Validates employee exists.
- Checks for duplicate open tickets before creating.

Output shape:
- created (boolean)
- ticket (created ticket payload)
- source

### ticket_update
Purpose:
- Updates an existing ticket summary.

Typical inputs:
- "Update TKT1004 summary to ..."

Validation:
- Requires ticket ID.
- Requires updated summary text.
- Validates ticket exists before update.

Output shape:
- updated (boolean)
- ticket
- ticket_id
- source

### employee_lookup
Purpose:
- Returns employee profile details for a known EMP ID.

Output shape:
- employee_id
- employees (list)
- count
- source

### system_status
Purpose:
- Returns service health and outage-related system state.

Search behavior:
- Matches query phrase and tokens against service/status fields.
- Falls back to all services when no direct match is found.

Output shape:
- statuses
- count
- source
- query
- fallback_to_all

### small_talk
Purpose:
- Handles greetings/thanks and provides guidance on what the assistant can do.

## 3) Multi-turn State
Conversation state keeps:
- employee_id
- ticket_id
- pending_intent
- proposed_issue_summary
- awaiting_lookup_confirmation
- awaiting_create_confirmation
- resume_intent

This enables workflows such as:
1. User reports issue.
2. Assistant asks for employee ID.
3. User provides EMP ID.
4. Assistant offers to check existing tickets.
5. User confirms and flow continues.

## 4) Safety Guarantees
- No ticket creation without required fields.
- No duplicate ticket creation when a similar open ticket exists.
- Missing information is explicitly requested.
- Tool/DB errors return safe user messages.
- Final responses are grounded in tool output.
