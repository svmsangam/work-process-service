# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

AI-Assisted Work Intake System: a FastAPI backend that ingests "work items", runs them through an
LLM-backed analysis pipeline (categorization, priority, summary, recommended action), and exposes them
via a state machine workflow. A React (Vite) frontend consumes the API to create and list work items.

## Commands

### Backend (from `backend/`)

- Install deps: `pip install -r requirements.txt`
- Start Postgres (required for running the app, not for tests): `docker-compose up -d` (from repo root)
- Run the API: `uvicorn app.main:app --reload` (serves on `http://localhost:8000`)
- Run all tests: `pytest`
- Run a single test file: `pytest test/test_work_items.py`
- Run a single test: `pytest test/test_work_items.py::test_ai_failure_isolation_and_retry_eligibility`

Tests run against an in-memory SQLite DB (see `test/conftest.py`), not Postgres, so `pytest` works without
Docker running.

### Frontend (from `frontend/`)

- Install deps: `npm install`
- Dev server: `npm run dev` (Vite, default `http://localhost:5173`)
- Build: `npm run build`
- Lint: `npm run lint`

The frontend expects the backend at `http://localhost:8000` (override via `VITE_API_BASE_URL`), and the
backend's CORS config only allows `http://localhost:5173`, so keep both at their default ports in dev.

## Architecture

### Backend layering

`routers/` (HTTP layer, FastAPI) → `services/` (business logic) → `models.py` (SQLAlchemy ORM). Routers
contain no logic beyond request/response wiring; all business rules live in `WorkItemService`
(`app/services/work_item_service.py`).

- **State machine** (`app/state_machine.py`): all status transitions for a `WorkItem` go through
  `validate_state_transition`, which enforces the allowed-transitions graph:
  `RECEIVED → ANALYSING → READY_FOR_REVIEW → COMPLETED`, with `FAILED` reachable from `ANALYSING` and
  retryable back to `ANALYSING`. `COMPLETED` is terminal. Any new transition must be added to
  `ALLOWED_TRANSITIONS`, not bypassed in a service method.
- **AI provider abstraction** (`app/services/ai_service.py`): `BaseLLMService` is the adapter interface;
  `MockLLMService` (default), `GroqLLMService`, `OpenRouterLLMService`, and `LocalLLMService` (for a local
  OpenAI-compatible endpoint such as Ollama) implement it. `get_ai_service()` selects the provider based on
  `settings.AI_PROVIDER` (`mock` | `groq` | `gemini` | `openrouter` | `local` — `gemini` is declared in
  config but has no adapter implemented). Defaults to `mock` (not `openrouter`) precisely so the app and
  test suite run without API credentials or network access; don't change this default without also
  accounting for the test suite making real network calls. `OpenRouterLLMService` and `LocalLLMService`
  share one lazily-created module-level `httpx.AsyncClient` (`get_http_client()`) for connection pooling —
  reuse it rather than instantiating a new client per call. Adapters must raise on failure rather than
  returning a partial/invalid result; the service layer relies on this to drive the `FAILED` transition.
  `MockLLMService` treats a title containing `FAIL_LLM` as a deliberate failure trigger, used by tests.
- **Async analysis flow**: `POST /work-items` (on creation), `POST /work-items/{id}/analyse`, and
  `.../retry` all schedule `WorkItemService.process_ai_analysis` via FastAPI `BackgroundTasks` rather than
  running inline. That method: validates/moves the item to `ANALYSING`, calls the AI adapter, and on
  success stores `ai_analysis` + moves to `READY_FOR_REVIEW`, or on any exception rolls back, records
  `ai_error`, and moves to `FAILED`. When touching this method, preserve the rollback-then-refetch pattern
  before writing the failure state (the session is dirty after a mid-transaction exception).
  `retry` is only permitted when the item is currently `FAILED`; that check lives in the router.
  `test/conftest.py`'s `client` fixture no-ops `BackgroundTasks.add_task` because `TestClient` executes
  background tasks synchronously (unlike a real ASGI server, where they run after the response is sent) —
  without this, every item creation in a test would silently race ahead of `RECEIVED` before test code runs
  its own assertions. Tests that need to exercise analysis call `WorkItemService.process_ai_analysis`
  directly instead of going through the HTTP layer.
- **Idempotency**: `WorkItem.external_id` has a DB-level unique constraint; duplicate ingestion is rejected
  via a caught `IntegrityError` → `409 Conflict`, not a pre-check query.
- **Schemas** (`app/schemas.py`): request/response Pydantic models use `alias_generator=to_camel` with
  `populate_by_name=True`, so the API accepts/returns camelCase JSON (e.g. `externalId`) while Python code
  stays snake_case. Keep this pattern for any new request/response models.

### Frontend

Minimal structure: `src/api/client.js` wraps axios for the backend API, `src/App.jsx` holds the top-level
fetch/create state, and `src/components/` has presentational components (`WorkItemForm`, `WorkItemList`,
`Navbar`). No routing or global state library — state is lifted to `App.jsx` and passed down via props.
Styling is Tailwind utility classes inline in JSX.

## Notes

- This directory is not currently a git repository.
- `backend/.env` / `backend/.env.example` hold the AI provider settings (`AI_PROVIDER`,
  `OPENROUTER_API_KEY`, `OPENROUTER_BASE_URL`, `OPENROUTER_MODEL`, `YOUR_SITE_URL`, `YOUR_SITE_NAME`,
  `LOCAL_AI_BASE_URL`, `LOCAL_AI_MODEL`) plus `DATABASE_URL`; `Settings` (`app/config.py`) reads from
  `backend/.env` if present, and otherwise falls back to `AI_PROVIDER=mock` with a local Postgres
  connection string.
