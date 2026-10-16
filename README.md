# LoveChat Backend

FastAPI backend for the private two-person LoveChat app.

## Local development

1. Create and activate a virtual environment.
2. Install dependencies with `pip install -r requirements.txt`.
3. Configure `DATABASE_URL`, `JWT_SECRET_KEY`, and the Cloudinary variables in your environment.
4. Start the API with `uvicorn app.main:app --reload`.

## Alembic migration baseline reset

The revision history was intentionally reset. The repository contains an initial schema baseline (`20261016_0001`) plus an additive delivery-event migration (`20261016_0002`). The baseline describes the core schema before durable event recovery; the second revision creates `delivery_events`.

### New, empty database

Run:

```bash
alembic upgrade head
```

This creates the current schema and records the baseline revision.

### Existing database (including Render/PostgreSQL)

**Do not run `alembic upgrade head` against an existing database until its schema has been inspected.** The baseline creates tables and is intended for an empty database. It does not reconcile pre-existing tables or columns.

1. Take a database backup first.
2. Inspect the actual schema, indexes, constraints, and `alembic_version` table.
3. Compare the live schema against `app/db/models.py` and the baseline revision.
4. Only if the live schema already matches the baseline, run:

   ```bash
   alembic stamp 20261016_0001
   ```

5. After stamping only `20261016_0001`, run `alembic upgrade head` to create the new `delivery_events` table. If the existing schema does not match the baseline, write and apply a reconciliation migration for the exact differences before stamping the baseline.

Do not drop production tables or remove columns merely to make a migration pass. A `DuplicateColumn` error means the database and migration assumptions differ; it does not mean the existing column should be deleted.

## Current API capabilities

- Cookie-based registration, login, session refresh, current-user lookup, and logout
- Relationship creation, lookup, listing, and ending
- Image avatar and chat-attachment uploads through Cloudinary
- REST and WebSocket messaging, replies, idempotency keys, read receipts, soft deletion, and attachment serialization
- Keyset-paginated history: `GET /api/conversations/{conversation_id}/messages?limit=50&before_id=<oldest_message_id>`
- Durable conversation event replay: `GET /api/conversations/{conversation_id}/events?after_id=<last_event_id>&limit=100`; persist the highest processed event ID on the client and replay after reconnect
- Alembic schema migrations
