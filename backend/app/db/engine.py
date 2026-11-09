"""
How this works / why it is safe:
This module manages database engine creation and transactional session lifecycles.
Using SQLAlchemy with psycopg3 sync driver, it configures connection pooling with pre-ping
to safely recycle stale cloud connections (e.g. Supabase, Neon). The session dependency
guarantees clean closure after every request. No transactions are auto-committed; all
commit and rollback points are explicit in domain services.
"""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings

# Runtime engine connects via DATABASE_URL_APP if provided, otherwise DATABASE_URL
db_url = settings.DATABASE_URL_APP or settings.DATABASE_URL

# Normalize postgres:// to postgresql+psycopg:// if needed
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql+psycopg://", 1)
elif db_url.startswith("postgresql://") and not db_url.startswith("postgresql+psycopg://"):
    db_url = db_url.replace("postgresql://", "postgresql+psycopg://", 1)

engine = create_engine(
    db_url,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    pool_recycle=300,
)

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


def get_db() -> Generator[Session, None, None]:
    """Dependency that yields a database session and guarantees closure."""
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
