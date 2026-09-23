# AI-Assisted Work Intake System

A small full-stack app for ingesting "work items" (e.g. support/CRM cases), running them through
an LLM-backed triage pass (category, priority, summary, recommended action), and tracking each
item through a review workflow. FastAPI + SQLAlchemy + Postgres on the backend, React + Vite +
Tailwind on the frontend.

## Setup & Running Instructions

### Backend Setup

```bash
cd backend
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

pip install -r requirements.txt
```

Copy `backend/.env.example` to `backend/.env` and configure it. By default `AI_PROVIDER=mock`, so
the app runs out of the box with no API keys — the AI step returns a canned structured result
instead of calling a real model. To use OpenRouter for real:

```
AI_PROVIDER=openrouter
OPENROUTER_API_KEY=<your key>
OPENROUTER_MODEL=nex-agi/nex-n2.5-pro:free
```

Configure PostgreSQL and run the API. You can either start PostgreSQL in the included Docker
container or connect to an existing local or remote PostgreSQL server by setting its connection
string in `backend/.env` as `DATABASE_URL`:

```bash
docker-compose up -d          # optional: starts Postgres on localhost:5432
uvicorn app.main:app --reload --port 8000
```

### Frontend Setup

```bash
cd frontend
npm install
npm run dev   # http://localhost:5173
```

The frontend expects the backend at `http://localhost:8000` (override via `VITE_API_BASE_URL`),
and the backend's CORS config only allows `http://localhost:5173`, so keep both at their default
ports in development.

### Running Tests

```bash
cd backend
pytest
```

Tests run against an in-memory SQLite database (see `backend/test/conftest.py`), so they don't
require Postgres or Docker to be running.

## Architecture

### Layering

`routers/` (HTTP layer) → `services/` (business logic) → `models.py` (SQLAlchemy ORM), with
`schemas.py` defining the Pydantic request/response contracts. Routers do no more than
request/response wiring; all business rules live in `WorkItemService`
(`app/services/work_item_service.py`).

### Work item lifecycle

| From                | Allowed next states       |
|---------------------|----------------------------|
| `RECEIVED`          | `ANALYSING`                |
| `ANALYSING`         | `READY_FOR_REVIEW`, `FAILED` |
| `READY_FOR_REVIEW`  | `COMPLETED`, `ANALYSING` (re-run) |
| `FAILED`            | `ANALYSING` (retry)        |
| `COMPLETED`         | *(terminal — no exits)*    |

Transitions are centrally enforced in `app/state_machine.py` (`ALLOWED_TRANSITIONS`) and checked
on every status change — including the ones driven by the AI background job, not just the manual
`PATCH /work-items/{id}/status` endpoint.

### API

| Method | Path                          | Status | Notes                                             |
|--------|-------------------------------|--------|----------------------------------------------------|
| POST   | `/work-items`                 | 201    | Creates the item, auto-queues AI analysis         |
| GET    | `/work-items`                 | 200    | Optional `?status=` filter                        |
| GET    | `/work-items/{id}`            | 200    | 404 if not found                                  |
| POST   | `/work-items/{id}/analyse`    | 202    | Queues AI analysis in the background              |
| POST   | `/work-items/{id}/retry`      | 202    | Only valid when status is `FAILED` (else 400)     |
| PATCH  | `/work-items/{id}/status`     | 200    | Manual transition, validated by the state machine |
| GET    | `/health`                     | 200    | Reports the active `AI_PROVIDER`                  |

Errors use FastAPI's standard `HTTPException` shape (`{"detail": "..."}`) — `404` for missing
items, `409` for a duplicate `externalId`, `400` for an invalid state transition or an ineligible
retry.

### AI integration (`app/services/ai_service.py`)

`BaseLLMService` is the adapter interface; `get_ai_service()` selects an implementation based on
`AI_PROVIDER`:

- `mock` (default) — canned response, used in dev and by the test suite; a title containing
  `FAIL_LLM` deliberately raises, for exercising the failure path.
- `groq` — Groq's chat completions API.
- `openrouter` — OpenRouter's OpenAI-compatible chat completions API, called via a pooled
  `httpx.AsyncClient` (`get_http_client()`), with a 30-second request timeout.
- `local` — any local OpenAI-compatible endpoint (e.g. Ollama), same client, 45-second timeout.

All adapters raise on failure — network error, timeout, non-2xx response, empty content, or a
payload that doesn't parse into `AIAnalysisResult` — rather than returning a partial result. That
exception propagates to `WorkItemService.process_ai_analysis`, which is the single place that
decides what a failure means for the item: it rolls back, stores the error text on `ai_error`, and
moves the item to `FAILED`. A malformed/empty provider response and a network timeout both end up
FAILED with a human-readable `ai_error` (e.g. `"AI Analysis unavailable (malformed response
received)."` or `"AI Analysis failed: OpenRouter request timed out after 30 seconds."`) rather
than crashing the background task or silently fabricating a category/priority the model never
produced.

### Concurrency: background AI processing

`POST /work-items`, `/analyse`, and `/retry` all schedule `WorkItemService.process_ai_analysis` via
FastAPI `BackgroundTasks`, so the HTTP response returns immediately (item stays `RECEIVED`/whatever
it was) while analysis runs after. The frontend polls every 4 seconds while any item is
`RECEIVED`/`ANALYSING`, so the UI reflects completion without a manual refresh.

### Data Integrity & Architecture

- `WorkItem.external_id` has a database-level unique constraint; duplicate ingestion is rejected by
  catching `IntegrityError` and returning `409`, not a pre-check query (avoids a race between
  check and insert).
- In a multi-tenant system, a single-column `external_id` constraint is insufficient because
  different tenants may submit the same identifier, such as two clients both uploading `CRM-101`.
  Scope uniqueness with a composite constraint such as
  `UniqueConstraint('tenant_id', 'external_id')`.
- Enforce tenant data isolation with tenant-aware middleware or database Row-Level Security (RLS),
  so tenant context is applied automatically across queries rather than relying on each call site
  to filter results correctly.
- Status writes go through `db.commit()` and are rolled back on failure before writing the
  `FAILED` state, so a failed AI call can't leave the row half-updated.
- There's a single `work_items` table today (no foreign keys / relations yet).

### Validation

Request and response shapes are Pydantic models in `app/schemas.py` (`WorkItemCreate`,
`WorkItemStatusUpdate`, `WorkItemResponse`, `AIAnalysisResult`). `WorkItemCreate` and
`AIAnalysisResult` use `alias_generator=to_camel` so the API speaks camelCase (`externalId`,
`recommendedAction`) while the Python/DB side stays snake_case; `WorkItemResponse`'s top-level
fields are snake_case as-is (no alias generator).

### Frontend

`src/api/client.js` wraps axios; `src/App.jsx` owns fetch/filter/polling state; presentational
components live in `src/components/` (`WorkItemForm`, `WorkItemList`, `WorkItemCard`, `Navbar`),
with shared status label/color metadata in `src/lib/workItemStatus.js`. No routing or global state
library — state is lifted to `App.jsx` and passed down via props. Styling is Tailwind utility
classes.

### Maintainability & testing

Configuration is environment-based (`pydantic-settings` reading `backend/.env`), with `AI_PROVIDER`
switching between `mock`/`groq`/`openrouter`/`local` without code changes. Backend tests
(`backend/test/test_work_items.py`) use an in-memory SQLite DB via `TestClient` and cover:
duplicate `externalId` rejection, invalid/terminal state-machine transitions, and AI-failure
isolation (a failed analysis sets `FAILED` + `ai_error` without corrupting the rest of the row, and
retry is rejected unless the item is currently `FAILED`).

## Performance & Load Testing Analysis (k6)

The k6 stress test used up to 50 virtual users (VUs) and reported 142 HTTP requests over 58.1
seconds. It failed the `http_req_duration` threshold (`p95=30.07s`, target `<500ms`) and the
`http_req_failed` threshold (`11.97%`, target `<1%`). Create-item latency also failed its check
for 61 of 71 requests, and the backend returned HTTP 500 responses while listing and creating
work items.

### Key findings and failure modes

- **Database connection pool starvation.** The default SQLAlchemy engine configuration provides a
  pool of 5 connections with up to 10 overflow connections, for 15 simultaneous connections in
  total. Concurrent requests from 50 VUs exhausted that capacity. Waiting requests then hit the
  30-second pool timeout (`QueuePool limit of size 5 overflow 10 reached`), producing HTTP 500
  responses for database queries and inserts. This is the direct cause of the stack traces shown
  in the stress-test log.
- **Upstream AI rate limiting (HTTP 429).** Burst creation schedules concurrent background AI
  analyses. Those requests reached OpenRouter's free tier faster than its quota allowed, resulting
  in `OpenRouter API error 429` and failed analyses. These provider failures are separate from the
  database pool timeout, although both appear during the same burst.
- **In-memory worker saturation.** FastAPI `BackgroundTasks` runs work in the application process
  and shares the server's execution resources under load. Concurrent database work and slow
  external AI calls therefore compete with request handling, causing API latency to spike to
  `p95=30.07s`. In-memory background execution also does not provide durable queueing or
  independent worker scaling.

### Immediate and architectural solutions

- **Tune the database connection pool.** For a deployment with this load profile, configure the
  SQLAlchemy engine with larger limits, for example:

  ```python
  engine = create_engine(
      settings.DATABASE_URL,
      pool_pre_ping=True,
      pool_size=20,
      max_overflow=30,
      pool_timeout=60.0,
  )
  ```

  The values must still be sized against the PostgreSQL server's `max_connections` and the number
  of application instances. Pool tuning reduces avoidable timeouts; it does not replace query
  optimization or capacity planning.
- **Add rate-limit resilience to AI calls.** Bound concurrent provider requests with a semaphore,
  such as `asyncio.Semaphore(5)`, and retry transient `429` and `5xx` responses with exponential
  backoff using a library such as `tenacity`. Retries should include a maximum attempt count and
  jitter, and permanent failures should still transition the work item to `FAILED` with its
  `ai_error` recorded.
- **Use a distributed message queue in production.** Replace in-memory `BackgroundTasks` with a
  Kafka Producer/Consumer model paired with an `asyncio` worker pool or Celery/ARQ workers. The API
  should persist an analysis event and return quickly, while consumer groups and independently
  scaled workers execute AI calls. This decouples ingestion from background execution, prevents
  slow AI calls from saturating request-serving resources, provides durable event handling and
  backpressure, and lets API and AI worker capacity scale independently.

## Recommendations & Future Work

- **Distributed message queue.** Background AI processing currently runs via FastAPI
  `BackgroundTasks`, which is in-process and in-memory — a server restart mid-analysis loses the
  task silently (the item just sits in `ANALYSING` forever). Moving to Celery/RQ with Redis or
  RabbitMQ would give persistent queuing, retry policies with backoff, and horizontal worker
  scaling independent of the API process.
- **High-throughput Kafka producer/consumer and async worker pool.** For a distributed system
  handling thousands of incoming requests per second across multiple FastAPI nodes, replace
  in-memory `BackgroundTasks` with an asynchronous Kafka producer/consumer setup paired with an
  `asyncio` worker pool (or Celery, Dramatiq, or ARQ workers). This decouples API ingestion speed
  from external AI response latency, guarantees event persistence through distributed consumer
  groups, enables backpressure management, and lets API ingestion and AI worker instances scale
  independently.
- **WebSockets / Server-Sent Events.** The frontend polls every 4 seconds while items are active.
  That's fine at this scale, but doesn't scale well with more concurrent users/items and adds
  latency to perceived completion. A WebSocket or SSE channel that pushes status transitions would
  replace polling with real-time updates and cut needless request volume.
- **Stricter LLM output structuring.** Providers are asked for JSON via a prompt instruction plus
  `response_format: {"type": "json_object"}`, then validated against `AIAnalysisResult` after the
  fact. A provider that ignores the instruction still produces a `FAILED` item today (that's by
  design — see AI integration above), but a schema-constrained decoding mode (or a
  structured-output wrapper) where available would reduce how often that happens.
- **Multi-provider fallback routing.** `AI_PROVIDER` currently picks one adapter for the whole app;
  there's no automatic failover. Retrying transient failures against a secondary provider (a
  different OpenRouter free model, or a local Ollama model) before marking an item `FAILED` would
  reduce how often a flaky free-tier endpoint forces a manual retry.
- **Formal database migrations.** Tables are created via `Base.metadata.create_all()` on startup —
  fine for a single evolving table, but it doesn't support altering existing columns or tracking
  schema history. Alembic migrations should replace this once the schema grows past trivial
  additive changes.
