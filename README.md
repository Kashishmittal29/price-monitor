# Product Price Monitor

A full-stack system that collects product data from **Grailed**, **Fashionphile**, and **1stDibs**, tracks price changes in real time, and notifies interested parties via a durable event log.

---

## How to Run

### 1. Clone and set up

```bash
git clone https://github.com/YOUR_USERNAME/price-monitor.git
cd price-monitor
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Start the server

```bash
uvicorn main:app --reload
```

On first start the server will print a **default API key** — save it:

```
============================================================
DEFAULT API KEY (save this — shown only once):
  abc123XYZ...
============================================================
```

### 3. Load data

Trigger the first data refresh (replace `YOUR_KEY`):

```bash
curl -X POST http://localhost:8000/refresh \
     -H "X-API-Key: YOUR_KEY"
```

### 4. Open the UI

Visit **http://localhost:8000/static/index.html**, paste your API key, and explore.

### 5. Run tests

```bash
pytest tests/ -v
```

---

## API Documentation

All endpoints require the header `X-API-Key: <your_key>`.

### POST `/refresh`
Trigger a full data collection from all marketplaces.

**Response:**
```json
{ "loaded": 90, "updated": 0, "price_changes": 0, "errors": 0 }
```

---

### GET `/products`
Browse and filter products.

| Query param | Type | Description |
|---|---|---|
| `source` | string | `grailed` / `fashionphile` / `1stdibs` |
| `brand` | string | Partial match |
| `category` | string | Partial match |
| `min_price` | float | Minimum price (USD) |
| `max_price` | float | Maximum price (USD) |
| `is_sold` | bool | `true` / `false` |
| `limit` | int | 1–200, default 50 |
| `offset` | int | Pagination offset |

**Example:**
```bash
curl "http://localhost:8000/products?source=grailed&min_price=100&max_price=500" \
     -H "X-API-Key: YOUR_KEY"
```

**Response:**
```json
[
  {
    "id": 1,
    "source": "grailed",
    "brand": "amiri",
    "model": "Amiri Washed Filigree T-Shirt",
    "current_price": 425.0,
    "currency": "USD",
    "is_sold": false,
    ...
  }
]
```

---

### GET `/products/{id}`
Single product with full price history.

```bash
curl http://localhost:8000/products/1 -H "X-API-Key: YOUR_KEY"
```

**Response includes:**
```json
{
  "id": 1,
  "price_history": [
    { "id": 1, "price": 425.0, "currency": "USD", "recorded_at": "2026-04-01T10:00:00" }
  ],
  ...
}
```

---

### GET `/analytics`
Aggregate statistics.

```json
{
  "total_products": 90,
  "by_source": { "grailed": 30, "fashionphile": 30, "1stdibs": 30 },
  "avg_price_by_category": { "belts": 2841.23, "jewelry": 1550.0, "apparel_authentication": 410.5 },
  "total_price_changes_24h": 3
}
```

---

### GET `/events`
Price-change event log. Consumers poll this to receive notifications.

| Query param | Type | Description |
|---|---|---|
| `delivered` | bool | Filter by delivery status |
| `limit` | int | 1–200, default 50 |

---

### POST `/events/process`
Manually trigger delivery of pending events.

---

### GET `/health`
Returns `{ "status": "ok" }`. No auth required.

---

## Design Decisions

### How does price history scale at millions of rows?

The `price_history` table is **append-only** — rows are never updated or deleted. A composite index on `(product_id, recorded_at)` keeps point-in-time lookups at O(log n) regardless of table size.

At true scale (100M+ rows):
- **PostgreSQL range partitioning** by month: each partition is a smaller B-tree, pruned automatically in queries with a date filter.
- **Archive cold rows** (>1 year) to object storage (S3 + Parquet), keep only recent rows in hot DB.
- **Materialised views** pre-aggregate daily/weekly averages so analytics queries don't scan raw history.

SQLite users: WAL mode + `VACUUM` periodically; migrate to PostgreSQL before >10M rows.

### How are price-change notifications implemented?

I chose a **durable event-log** pattern over alternatives:

| Approach | Problem |
|---|---|
| Synchronous webhook in fetch loop | Blocks ingestion; one slow consumer delays all |
| Consumer polls main DB | Couples consumers to our schema; noisy reads |
| External queue (Kafka/SQS) | Correct, but heavy infra for an intern assignment |
| **Event log (chosen)** | Atomic writes, async delivery, no infra dependency |

Price changes are written to `price_events` **inside the same DB transaction** as the `price_history` insert — so events are never lost even if the notification worker crashes. A background `asyncio` task polls undelivered events every 10 seconds and marks them `delivered=True`. Failed deliveries increment `retry_count`; events with `retry_count >= 5` are abandoned (dead-letter logic).

In production: replace the log-write delivery with a Kafka producer; the interface is identical.

### How would you extend this to 100+ data sources?

Each source is a subclass of `BaseCollector` that implements one method: `collect() -> list[dict]`. Adding a new marketplace is:

1. Create `app/collectors/newsource.py` with the normalisation logic.
2. Register it in `app/collectors/__init__.py`.

The ingest service runs all collectors via `asyncio.gather()` — no other code changes needed. At 100+ sources, run each collector in a separate worker process (Celery / asyncio subprocess) with a shared result queue to avoid one slow scraper blocking others.

### Same product on multiple sources

Products are keyed by `(source, external_id)` — they are **not merged across sources**. This is intentional: a Chanel belt on 1stDibs and the same belt on Grailed have different prices, conditions, and sellers. Cross-source deduplication (by brand + model similarity) can be done as an analytics overlay without touching the core schema.

---

## Known Limitations

- **No live scraping**: collectors read local JSON files. In production each would call the marketplace API/scraper with proper rate limiting.
- **Single-node SQLite**: fine for development; migrate to PostgreSQL for multi-process deployments.
- **Notification delivery**: the current worker logs events to stdout. Production would POST to registered webhook URLs.
- **No API key rotation**: keys are static; production needs expiry + rotation.
- **No pagination cursor**: uses offset pagination which degrades at high offsets; keyset pagination would be better.
- **Frontend**: vanilla JS with no build step — simple but lacks reactivity for large product lists.

---

## Git Commit History Guide

| # | Message |
|---|---|
| 1 | `chore: init project structure, requirements, gitignore` |
| 2 | `feat: add SQLAlchemy ORM models and database session` |
| 3 | `feat: add Pydantic schemas for API responses` |
| 4 | `feat: implement marketplace collectors with retry logic` |
| 5 | `feat: implement ingest service with price-change detection` |
| 6 | `feat: add durable event-log notification system` |
| 7 | `feat: build REST API with auth, usage logging, all endpoints` |
| 8 | `feat: add vanilla JS frontend dashboard and product browser` |
| 9 | `test: add 14+ tests covering auth, ingest, API, collectors` |
| 10 | `docs: complete README with API docs and design rationale` |
