# Project 3 - AI Operations Assistant Using Agentic AI

## Project Title
AI IT Support Assistant (LangGraph + Streamlit + PostgreSQL + Ollama)

## Problem Statement
Employees need fast help for common IT issues such as VPN access, ticket status, and raising new support tickets. The assistant should understand intent, route to the right tool, validate required inputs, avoid duplicates, and provide clear responses.

## Solution Overview
This project implements a local Agentic AI IT Support Assistant with:
- LangGraph workflow orchestration
- Intent-based conditional routing
- Core tools (knowledge search, ticket lookup, ticket creation) plus a system status tool
- Stateful multi-turn handling (employee ID, pending action, and issue summary retained across turns)
- Safety validations before write actions
- Streamlit chat interface with trace visibility
- Local Ollama model (`gemma:4`) for intent classification
- PostgreSQL as the local system of record
- Automated unit tests for routing and validation behavior

## Architecture Diagram
```mermaid
flowchart TD
   subgraph UI[Streamlit UI Layer]
      U[User Message]
      H[Chat History]
      T[Tabular Tool Output]
   end

   subgraph APP[Service + LangGraph Orchestrator]
      SVC[ITSupportAgent.handle_message]
      ST[Graph State]
      C1[Capture Context Node]
      C2[Intent Decision Node]
      RSP[Response Composition Node]
   end

   subgraph MEMORY[State Memory]
      M1[employee_id]
      M2[ticket_id]
      M3[pending_intent]
      M4[proposed_issue_summary]
      M5[confirmation_flags]
   end

   subgraph ROUTES[Conditional Routing]
      I1[knowledge_search]
      I2[employee_lookup]
      I3[ticket_lookup]
      I4[ticket_creation]
      I5[ticket_update]
      I6[system_status]
      I7[small_talk]
   end

   subgraph VALIDATION[Safety and Validation Gates]
      V1[Employee ID Required]
      V2[Employee Exists]
      V3[Duplicate Ticket Check]
      V4[Ticket Exists for Update]
      V5[Missing Field Prompt]
   end

   subgraph TOOLS[Local Tools and Data Access]
      K[Knowledge Search Tool]
      E[Employee Lookup Tool]
      L[Ticket Lookup Tool]
      CR[Ticket Creation Tool]
      UP[Ticket Update Tool]
      SS[System Status Tool]
   end

   subgraph DATA[PostgreSQL]
      D1[(employees)]
      D2[(knowledge_base)]
      D3[(tickets)]
      D4[(system_status)]
   end

   subgraph LLM[LLM Layer]
      LI[Intent Classifier]
      LR[Grounded Response Generator]
   end

   U --> SVC --> ST --> C1 --> C2
   C1 --> M1
   C1 --> M2
   C1 --> M3
   C1 --> M4
   C1 --> M5

   C2 --> LI
   C2 --> I1
   C2 --> I2
   C2 --> I3
   C2 --> I4
   C2 --> I5
   C2 --> I6
   C2 --> I7

   I1 --> K --> D2
   I2 --> E --> D1

   I3 --> V1
   V1 -->|has employee_id or ticket_id| V2
   V1 -->|missing data| V5 --> RSP
   V2 -->|valid| L --> D3
   V2 -->|invalid| V5 --> RSP

   I4 --> V1
   V1 -->|has employee_id| V2
   V2 -->|valid| V3
   V3 -->|not duplicate| CR --> D3
   V3 -->|duplicate detected| V5 --> RSP

   I5 --> V4
   V4 -->|valid ticket| UP --> D3
   V4 -->|missing/invalid ticket| V5 --> RSP

   I6 --> SS --> D4
   I7 --> RSP

   K --> RSP
   E --> RSP
   L --> RSP
   CR --> RSP
   UP --> RSP
   SS --> RSP

   RSP --> LR --> H
   RSP --> T
   H --> A[Final Assistant Response]
   T --> A
```

## Technology Stack
- Python 3.10+
- LangGraph
- LangChain
- langchain-ollama
- Streamlit
- PostgreSQL
- psycopg (v3)
- SQLAlchemy ORM
- unittest

## Project Structure
```text
capstone/
├── app.py
├── requirements.txt
├── .env.example
├── README.md
├── tests/
│   └── test_agent_graph.py
├── db/
│   └── init.sql
├── data/
│   ├── employees.json
│   ├── knowledge_base.json
│   ├── system_status.json
│   └── tickets.json
└── src/
    ├── __init__.py
    ├── agent_graph.py
    ├── config.py
    ├── database.py
    ├── llm_router.py
    ├── models.py
    ├── service.py
    ├── state.py
    └── tools.py
```

## Setup Instructions
1. Create and activate an isolated Python virtual environment from the repository root:
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```
   If PowerShell blocks script activation, use Command Prompt instead:
   ```bat
   .venv\Scripts\activate.bat
   ```
2. Install the project dependencies inside the active virtual environment:
   ```powershell
   python -m pip install --upgrade pip
   python -m pip install -r requirements.txt
   ```
3. Install PostgreSQL locally and ensure it is running.
4. Create a database named `it_support`.
5. The application automatically creates and validates the required database schema at startup. It also inserts the sample data only when the matching record does not already exist. To initialize it manually before running the app, use:
   ```bash
   psql -U postgres -d it_support -f db/init.sql
   ```
6. Install and run Ollama, then pull model:
   ```bash
   ollama pull gemma4:latest
   ```
7. Create `.env` from `.env.example` and adjust connection values.
8. Optional but recommended: run the unit tests before the demo.
   ```bash
   python -m unittest discover -s tests -v
   ```

## Environment Variables
Required:
- `OLLAMA_BASE_URL` (default `http://localhost:11434`)
- `OLLAMA_MODEL` (default `gemma4:latest`)
- `POSTGRES_DSN` (example `postgresql://postgres:postgres@localhost:5432/it_support`)

Optional:
- `MAX_KB_RESULTS` (default `3`)
- `APP_NAME` (default `AI IT Support Assistant`)
- `SHOW_TRACE` (`true` to show routing/tool trace in the UI)

## Database Startup Behavior
- SQLAlchemy models define `Employee`, `KnowledgeArticle`, `SystemStatus`, and `Ticket` as the application data model.
- On startup, SQLAlchemy creates the `employees`, `knowledge_base`, `system_status`, and `tickets` tables when they do not exist.
- Existing records are preserved. Sample employees, knowledge articles, and tickets are only inserted when their primary key is absent.
- The application validates the expected columns for every table before accepting requests.
- If PostgreSQL is unavailable or its schema is incompatible, the UI displays a clear warning and tool calls return safe error messages.
- For future changes to an existing production schema, add an Alembic migration. `create_all()` creates missing tables but intentionally does not alter existing columns automatically.

## How to Run the Application
Activate the virtual environment first, then start the Streamlit application:
```powershell
.\.venv\Scripts\Activate.ps1
streamlit run app.py
```

Open `http://localhost:8501` in a browser. Keep PostgreSQL and Ollama running in separate terminals while using the application.

## How to Build
Run these checks from the active virtual environment before packaging:
```powershell
python -m unittest discover -s tests -v
python -m compileall app.py src tests
```

Build the container image after local validation:
```powershell
podman build -t ai-it-support:local .
```

Podman is the next step after all three local services work independently. The container will run Streamlit, while PostgreSQL and the configured LLM remain external services.

## Sample Inputs
- `How do I reset my VPN password?`
- `What is the status of my laptop issue? EMP1024`
- `My VPN is not working. Please raise a ticket. EMP3001`

## Sample Outputs
- Knowledge answer with article reference (e.g., `KB-001`)
- System status summary with service-level details
- Latest ticket status for employee ID
- New ticket confirmation with generated ticket ID
- Graceful validation prompts if employee ID or issue summary is missing
- Duplicate-ticket prevention message when a similar open ticket already exists

## Key Design Decisions
- LangGraph state is used to retain conversation context (`employee_id`) across turns.
- LangGraph state is used not only for memory, but also for workflow continuity through `pending_intent` and `proposed_issue_summary`.
- Tool APIs are deterministic Python functions and are routed by an LLM classifier with fallback heuristics.
- Ticket creation includes guardrails:
  - Required field checks
  - Employee existence validation
  - Duplicate ticket detection in recent open tickets
- Database failures are converted into user-safe responses instead of raw stack traces.
- The Streamlit UI can expose tool and routing traces for demonstration and evaluation.

## Evaluation Criteria Mapping
- Functional completeness: all three required tools are implemented and accessible through a single agent workflow.
- GenAI implementation: Ollama is used for intent classification, with deterministic fallbacks to reduce brittle behavior.
- Architecture: orchestration, routing, service layer, config, state, and tools are separated into dedicated modules.
- Technical depth: LangGraph state, nodes, edges, conditional routing, multi-step validation, and duplicate checks are implemented in code.
- Code quality: the codebase uses typed structures, focused modules, and testable tool interfaces.
- Error handling: database and runtime failures produce clear, user-safe messages.
- User experience: the Streamlit app preserves chat history, supports reset, and can expose tool traces for transparency.
- Documentation: setup, architecture, samples, and design decisions are documented here.
- Engineering practices: environment variables, `.env.example`, logging, tests, and modular organization are included.
- Demonstration: the trace panel and test coverage make it easier to explain the architecture live.

## Testing
Run:
```bash
python -m unittest discover -s tests -v
```

The tests cover:
- Knowledge search routing
- Missing-information prompting
- Multi-turn stateful follow-up
- Duplicate-ticket prevention
- Successful ticket creation after follow-up input

## Safety and Validation Coverage
- No blind writes to database
- Graceful missing information prompts
- Duplicate prevention before ticket creation
- Clear distinction between retrieved data and assistant guidance
- Error handling with user-safe messages

## Limitations
- Intent routing uses a lightweight classifier prompt and can be improved with richer evaluation.
- Knowledge search is lexical SQL matching (not embedding/vector search).
- Authentication/authorization is not implemented (local demo scope).
- Concurrent ticket ID generation is basic for local-demo usage.
- This project assumes local Ollama and PostgreSQL are already installed and reachable.

## Submission Checklist Mapping
- Source code: Included (modular `src/` design)
- README: Included with all required sections
- Sample data: Included (`db/init.sql` and JSON examples)
- Demonstration: Run locally or record short video
- GitHub repository assets: `README`, code, sample data, `requirements.txt`, `.env.example`, architecture diagram in README

## Security Note
Do not commit real credentials, API keys, or production connection strings.
