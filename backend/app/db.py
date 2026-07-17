"""SQLite (via SQLModel) engine + session helpers.

Used by the paper-trading and lesson-progress features. Single-user, no auth
for v1.
"""

from collections.abc import Iterator

from sqlmodel import Session, SQLModel, create_engine

from app.config import get_settings

_settings = get_settings()
_url = _settings.sqlalchemy_url
_is_sqlite = _url.startswith("sqlite")

engine = create_engine(
    _url,
    echo=False,
    # check_same_thread=False lets FastAPI's threadpool share the SQLite connection.
    connect_args={"check_same_thread": False} if _is_sqlite else {},
    # Managed Postgres drops idle connections; without pre-ping the first query
    # after an idle period fails on a stale pooled connection.
    pool_pre_ping=not _is_sqlite,
)


def init_db() -> None:
    # Import models so they register on SQLModel.metadata before create_all.
    import app.models  # noqa: F401

    SQLModel.metadata.create_all(engine)


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session
