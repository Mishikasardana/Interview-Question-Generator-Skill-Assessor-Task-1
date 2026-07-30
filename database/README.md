# Database Layer

This folder contains the PostgreSQL persistence layer for the Interview
Intelligence Platform.

## Files

- `connection.py`: reads `DATABASE_URL`, creates the SQLAlchemy engine/session.
- `models.py`: SQLAlchemy models for all PostgreSQL tables.
- `repositories.py`: helper functions used by `app.py` to save records.
- `init_db.py`: command-line entry point to create tables.
- `schema.sql`: plain SQL version of the schema for review or manual setup.

## Setup

Add this to `.env`:

```env
DATABASE_URL=postgresql+psycopg://USERNAME:PASSWORD@localhost:5432/interview_platform
```

Then run:

```bash
python -m database.init_db
```

Real users authenticate via Google Sign-In (see the root README's "Google
Sign-In setup" section) — `ensure_demo_user()` in `repositories.py` is only
used by scripts/tests that need a `User` row without going through that
flow.
