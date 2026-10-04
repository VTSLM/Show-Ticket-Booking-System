# Show Booking System – Browse Nearby Shows (FastAPI)

Backend for the **Browse Nearby Shows** feature: select a location, view nearby shows,
search by name, and view show details. Built on the provided PostgreSQL schema.

## Project structure
```
app/
├── main.py                  # app factory, middleware, lifespan
├── api/
│   ├── deps.py              # dependency wiring (session -> repo -> service)
│   └── v1/
│       ├── router.py
│       └── endpoints/       # thin HTTP layer: locations, shows, health
├── core/                    # config (env), logging, exceptions
├── db/                      # declarative Base, async engine/session
├── models/                  # SQLAlchemy models (all tables in the schema + enums)
├── schemas/                 # Pydantic request/response models
├── repositories/            # all SQL lives here
└── services/                # business rules (filters, timezone, mapping)
alembic/                     # migrations (async env)
scripts/seed.py              # demo data
tests/                       # API tests with dependency overrides
```
Flow: `endpoint -> service -> repository -> DB`. Endpoints never touch SQL; repositories never raise HTTP errors.

## Endpoints (`/api/v1`)
| Feature | Endpoint |
|---|---|
| Select Location | `GET /locations/cities?q=gan` |
| View Nearby Shows | `GET /shows?city=Gandhinagar&event_type=MOVIE&language=Hindi&date_from=2026-10-02&page=1&page_size=20` |
| Search Shows | `GET /shows/search?q=interstellar&city=Gandhinagar` |
| View Show Details | `GET /shows/{show_id}` |
| Health | `GET /health`, `GET /health/ready` |

Interactive docs at `/docs` (disabled when `ENVIRONMENT=production`).

## Run locally
```bash
cp .env.example .env
docker compose up -d db
pip install -r requirements-dev.txt
alembic revision --autogenerate -m "initial schema"   # first time only; commit the file
alembic upgrade head
python -m scripts.seed                                 # optional demo data
uvicorn app.main:app --reload
pytest
```
Or everything in Docker: `docker compose up --build` (after generating the initial migration).

## Design notes
- **"Nearby" = same city.** The schema has no coordinates, so nearby is city-based. For true
  distance search, add `latitude/longitude` to `venues` and filter with PostGIS / `earthdistance`.
- **What counts as browsable:** `shows.status = SCHEDULED`, `events.status = PUBLISHED`, and `start_time` in the future.
- **Availability:** a seat is available if `AVAILABLE`, or `HELD` with an expired `locked_until`
  (so abandoned checkouts don't show as sold out).
- **Prices:** `min_price`/`max_price` come from `show_seats`; the details endpoint adds per-seat-type pricing and availability.
- **Dates** (`date_from`/`date_to`) are interpreted in `DEFAULT_TIMEZONE` (Asia/Kolkata), not UTC.
- **Search** is case-insensitive substring on `events.title` with LIKE-wildcards escaped.
  For large catalogs add a trigram index: `CREATE EXTENSION pg_trgm; CREATE INDEX ON events USING gin (title gin_trgm_ops);`
- **Errors** share one shape: `{"error": {"code", "message", "details?"}}`.
