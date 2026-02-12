# Multi-tenant RAG Platform

Production-grade, portfolio-ready Retrieval-Augmented Generation (RAG) platform for chatting with uploaded PDFs.

This project demonstrates full-stack AI system design with multi-tenancy, async ingestion, hybrid retrieval, grounding safeguards, citation-first answers, evaluation metrics, and deployable infrastructure.

## Highlights

- Multi-tenant architecture with strict `workspace_id` scoping
- JWT auth (`access + refresh`) with hashed passwords
- Async PDF ingestion pipeline via Celery + Redis
- Token-aware chunking (`450` tokens, `80` overlap) with `tiktoken`
- OpenAI embeddings (`text-embedding-3-small`)
- Hybrid retrieval:
  - Vector similarity (`pgvector` cosine)
  - Keyword relevance (`Postgres tsvector/ts_rank`)
  - Weighted score fusion
- MMR reranking for diverse context selection
- Prompt-injection filtering on retrieved text
- Streaming chat responses via SSE
- Citation enforcement in final answers
- Evaluation harness with retrieval + grounding metrics
- Dockerized local environment (Postgres+pgvector, Redis, API, Worker, Web)

## Tech Stack

### Frontend
- Next.js 14
- React + TypeScript
- Tailwind CSS
- SSE streaming chat UI
- Citation sidebar with snippet expansion

### Backend
- FastAPI
- SQLAlchemy + Alembic
- Postgres + `pgvector`
- Redis + Celery worker
- PyPDF + `tiktoken`
- OpenAI Python SDK (Embeddings + Responses)

## System Architecture

```mermaid
flowchart LR
    U["User"] --> W["Next.js Web App"]
    W -->|"JWT + API calls"| A["FastAPI API"]
    A -->|"metadata"| P["Postgres + pgvector"]
    A -->|"enqueue job"| R["Redis"]
    R --> C["Celery Worker"]
    C -->|"chunks + embeddings"| P
    C -->|"file read"| S["Storage (Local/S3)"]
    A -->|"file write"| S
    A -->|"embed/query/stream"| O["OpenAI API"]
```

## Repository Structure

```text
backend/
  app/
    api/routes/         # Auth, documents, workspaces, chat, health
    core/               # Config, auth, logging, rate limiting, deps
    db/                 # Models, session, base
    services/           # Retrieval, chunking, OpenAI, storage, policy
    tasks/              # Celery app + ingestion task
    eval/               # Evaluation harness + dataset loaders
  alembic/              # DB migrations
  tests/                # Unit + integration tests
  scripts/              # Eval runner
web/
  app/                  # Next.js routes (/login, /documents, /chat)
  lib/                  # API client + auth token helpers
  components/           # UI components
docker-compose.yml
```

## Local Setup (Docker)

```bash
cd "/Users/rahul/Documents/Projects/RAG App"
cp .env.example .env
# set OPENAI_API_KEY and JWT_SECRET_KEY in .env

docker compose up --build -d
docker compose exec api alembic upgrade head
```

Endpoints:
- Web: http://localhost:3000
- API docs: http://localhost:8000/docs

## API Surface

- `POST /auth/register`
- `POST /auth/login`
- `POST /auth/refresh`
- `GET /me`
- `GET /workspaces`
- `POST /workspaces`
- `GET /documents`
- `POST /documents/upload`
- `DELETE /documents/{id}`
- `POST /documents/{id}/reindex`
- `POST /chat` (SSE)
- `GET /health`

## Retrieval Pipeline

1. Embed user query
2. Retrieve vector candidates (`cosine_distance`)
3. Retrieve keyword candidates (`ts_rank_cd` over `to_tsvector`)
4. Merge and normalize scores
5. Apply weighted fusion (`vector_weight`, `keyword_weight`)
6. Rerank with MMR for diversity
7. Sanitize chunks against prompt-injection patterns

## Grounding & Safety

- Strict system prompt enforcing context-only answers
- Fixed refusal policy when evidence is missing:
  - `I couldn't find that in your documents.`
- Prompt-injection filtering on chunk text
- Citation format enforcement and citation object extraction
- Per-user token-bucket rate limiting

## Evaluation Harness

Run offline evaluation against labeled cases:

```bash
cd backend
python scripts/run_evaluation.py --dataset eval/sample_dataset.jsonl --top-k 8
```

Metrics:
- `recall_at_k`
- `mrr`
- `citation_correctness`
- `refusal_rate`
- `refusal_accuracy`

Dataset format (`jsonl`):

```json
{"workspace_id":"<workspace_uuid>","question":"...","relevant_chunk_ids":["<chunk_uuid>"],"should_refuse":false}
```

## Tests

```bash
cd backend
pytest
```

DB-backed retrieval tests require:

```bash
export TEST_DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5432/rag_app_test
```

## Smoke Test

```bash
# register
REGISTER=$(curl -s -X POST http://localhost:8000/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"email":"demo@example.com","password":"StrongPass123"}')
ACCESS_TOKEN=$(echo "$REGISTER" | python3 -c 'import sys,json; print(json.load(sys.stdin)["access_token"])')

# workspace
WORKSPACE_ID=$(curl -s http://localhost:8000/workspaces \
  -H "Authorization: Bearer $ACCESS_TOKEN" | python3 -c 'import sys,json; print(json.load(sys.stdin)[0]["id"])')

# upload
curl -s -X POST http://localhost:8000/documents/upload \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -F "workspace_id=$WORKSPACE_ID" \
  -F "file=@/absolute/path/to/file.pdf"

# chat (SSE)
curl -N -X POST http://localhost:8000/chat \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H 'Content-Type: application/json' \
  -d "{\"workspace_id\":\"$WORKSPACE_ID\",\"message\":\"What is the release deadline?\",\"debug\":true}"
```

## Deployment Notes

- Set `STORAGE_BACKEND=s3` for S3-compatible object storage
- Use managed Postgres with `pgvector` extension enabled
- Use managed Redis for Celery + rate limiting
- Run Alembic migrations before switching traffic
- Keep secrets in secret manager (never in code)
- Configure `SENTRY_DSN` for production error tracking

