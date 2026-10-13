"""Database session management and initialization for SQLModel."""

from collections.abc import Generator
from typing import Any

from sqlalchemy import event
from sqlmodel import Session, SQLModel, create_engine

from app.config import settings

# Configure SQLite engine with foreign key enforcement and multi-thread support
connect_args: dict[str, Any] = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG and settings.ENV == "development",
    connect_args=connect_args,
)


@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection: Any, connection_record: Any) -> None:
    """Enable foreign key constraints for SQLite connections."""
    if settings.DATABASE_URL.startswith("sqlite"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def init_db(target_engine: Any = None) -> None:
    """Create all database tables defined in SQLModel metadata."""
    # Ensure all models are imported so SQLModel knows about them
    import app.db.models  # noqa: F401

    db_engine = target_engine or engine
    SQLModel.metadata.create_all(db_engine)


def get_session() -> Generator[Session, None, None]:
    """FastAPI dependency to provide a database session per request."""
    with Session(engine) as session:
        yield session
