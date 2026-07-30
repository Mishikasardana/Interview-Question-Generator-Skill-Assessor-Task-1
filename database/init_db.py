"""Create PostgreSQL tables for the Interview Intelligence Platform."""

from database.connection import init_db


if __name__ == "__main__":
    init_db()
    print("Database tables created.")
