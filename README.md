# LoveChat Backend

FastAPI backend for the private two-person LoveChat app.

## Local development

1. Create and activate a virtual environment.
2. Install dependencies with `pip install -r requirements.txt`.
3. Configure `DATABASE_URL`, `JWT_SECRET_KEY`, and the Cloudinary variables in your environment.
4. Start the API with `uvicorn app.main:app --reload`.

## Alembic migration baseline reset

The revision history was intentionally reset. The repository now contains one baseline revision at `migrations/versions/20261016_0001_initial_schema.py`, describing the current SQLAlchemy models.

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
   alembic stamp head
   ```

5. If it does not match, write and apply a reconciliation migration for the exact differences before stamping the baseline.

Do not drop production tables or remove columns merely to make a migration pass. A `DuplicateColumn` error means the database and migration assumptions differ; it does not mean the existing column should be deleted.

## Current API capabilities

- Cookie-based registration, login, session refresh, current-user lookup, and logout
- Relationship creation, lookup, listing, and ending
- Image avatar and chat-attachment uploads through Cloudinary
- REST and WebSocket messaging, replies, idempotency keys, read receipts, soft deletion, and attachment serialization
- Alembic schema migrations
