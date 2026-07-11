# Cardly API

FastAPI + PostgreSQL backend for Cardly, a trading-card scanner app (mobile client: `cardly_case_study`). It takes a photo of a card, extracts the name/collector number via OCR, matches it against Scryfall, and persists cards/collections — scoped per device, with no login.

## Stack

- **FastAPI** — routing, validation, `TestClient`-based testing
- **SQLModel** (SQLAlchemy + Pydantic in one class) — ORM models and request/response schemas
- **PostgreSQL** (hosted on Aiven) — the database
- **Alembic** — schema migrations
- **OCR.space** — text extraction from card photos
- **Scryfall API** — card matching/metadata

## Project layout

```
app/
  main.py                    # FastAPI app, CORS, router mounting
  core/                       # settings (pydantic-settings), logging
  db/                         # SQLModel models, session/engine
  schemas/                    # request/response Pydantic schemas
  api/
    deps.py                   # DB session dependency, device-id auth dependency
    routes/                   # health, cards, collections, enrich
  services/                   # OCR client, Scryfall client, OCR text parser, enrichment orchestration
  middleware/                 # request logging
alembic/versions/              # migrations
tests/                         # pytest suite (SQLite in-memory fixtures)
```

## Getting started

**Requirements:** Python 3.11+, a PostgreSQL database (a free [Aiven](https://aiven.io) instance works fine), and an [OCR.space API key](https://ocr.space/ocrapi) (free tier, no card required).

1. **Install dependencies**

   ```bash
   python -m venv .venv
   source .venv/bin/activate   # .venv\Scripts\activate on Windows
   pip install -r requirements.txt
   ```

2. **Configure environment** — create a `.env` file in the repo root:

   ```env
   DATABASE_URL=postgresql://user:password@host:port/dbname
   OCR_SPACE_API_KEY=your-ocr-space-key
   CORS_ORIGINS=["*"]
   ENVIRONMENT=development
   LOG_LEVEL=INFO
   ```

3. **Run migrations** against your database:

   ```bash
   alembic upgrade head
   ```

4. **Start the server**

   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

   `--host 0.0.0.0` matters if you're testing against a physical phone or simulator on the same network — `127.0.0.1` only accepts connections from the machine running the server. Once it's up, interactive API docs are at `http://localhost:8000/docs`.

5. **Run tests**

   ```bash
   pytest
   ```

   84 tests, using an in-memory SQLite database (no connection to your real Postgres instance needed to run the suite).

## API overview

All endpoints except `/health` and `/enrich` require an `X-Device-Id` header (any stable string — the mobile app generates and persists a UUID). Every card/collection is scoped to the device that created it; a missing header returns `400`, and accessing another device's resource returns `404`.

| Method | Path | Notes |
|---|---|---|
| `GET` | `/health` | No auth, no DB dependency — used as a Render cold-start prewarm target |
| `POST` | `/enrich` | Multipart image upload (≤8MB, JPEG/PNG/WebP). **Stateless** — never touches the DB. Returns `matched`, `unrecognized`, or `error` |
| `POST` / `GET` | `/cards` | Create / list cards (newest first) |
| `GET` / `DELETE` | `/cards/{id}` | Fetch / delete a single card |
| `POST` / `GET` | `/collections` | Create / list collections (with card counts) |
| `GET` / `PATCH` / `DELETE` | `/collections/{id}` | Fetch (with member cards) / rename / delete |
| `POST` / `DELETE` | `/collections/{id}/cards/{card_id}` | Add / remove a card from a collection |

`/enrich`'s three response shapes are deliberate: OCR/Scryfall failures and unmatched cards resolve to a `200 unrecognized` response (with whatever OCR text was found) rather than an error, so the client can always fall back to "save without analysis." A real `error` status is reserved for bad uploads, missing config, or genuinely unhandled exceptions.

## Migrations

New schema change:

```bash
alembic revision --autogenerate -m "describe the change"
```

Always review the generated migration file before applying it — the tests don't touch your real database, so nothing else will catch a bad migration for you. Apply with:

```bash
alembic upgrade head
```

## Deploying

The app is a standard ASGI app, deployable anywhere that runs `uvicorn`/`gunicorn` (Render, Fly.io, Railway, etc.). At minimum you'll need:

- Build: `pip install -r requirements.txt`
- Start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Environment variables: `DATABASE_URL`, `OCR_SPACE_API_KEY`, `CORS_ORIGINS` (restrict this to your app's actual origin(s) in production instead of `["*"]`)
- Run `alembic upgrade head` once against the production database before (or as part of) the first deploy.

If deployed on a free tier that cold-starts, point the mobile app's connectivity check at `/health` to prewarm the instance before a scan.
