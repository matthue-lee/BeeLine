# Database Operations

## Prerequisites
- Ensure Python dependencies are installed (`pip install -r requirements.txt`).
- Copy `.env.docker.example` to `.env.docker` (or export `DATABASE_URL` manually).

## Running Migrations
```bash
export DATABASE_URL=sqlite:///db/beeline.db  # or your Postgres URI
alembic upgrade head
```

## Resetting the Database
```bash
./scripts/db_reset.sh
```
The script will:
1. Load `.env.docker` (unless `DATABASE_URL` already set).
2. Delete the SQLite file if applicable.
3. Recreate the schema with `alembic upgrade head`.

For Postgres, ensure the referenced database exists and the user has privileges; the script leaves data in place and simply reapplies migrations.

## Adding New Migrations
```bash
alembic revision -m "description"
# edit the file under alembic/versions/
alembic upgrade head
```

## Troubleshooting
- Verify `DATABASE_URL` matches the service you want to migrate (e.g., `postgresql+psycopg://user:pass@localhost:55432/beeline`).
- Use `alembic current` to see the applied revision.
- SQLite resets remove the DB file; for Postgres, manually drop/recreate if a clean slate is required.
