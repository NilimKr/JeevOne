"""
storage/database.py
===================
Creates and manages the SQLite engine and session factory.
Call init_db() once at startup.
"""

from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.config_loader import cfg
from app.storage.models import Base

_log = logging.getLogger(__name__)

_engine = None
_SessionFactory = None


def init_db() -> None:
    """Create the SQLite file and all tables (idempotent)."""
    global _engine, _SessionFactory

    db_path: Path = cfg.db_path
    db_path.parent.mkdir(parents=True, exist_ok=True)

    db_url = f"sqlite:///{db_path}"
    _log.info("Initialising SQLite database at %s", db_path)

    _engine = create_engine(
        db_url,
        connect_args={"check_same_thread": False},
        echo=False,
    )

    # Enable WAL mode for better concurrent read/write performance
    @event.listens_for(_engine, "connect")
    def set_wal(dbapi_conn, _record):
        dbapi_conn.execute("PRAGMA journal_mode=WAL")
        dbapi_conn.execute("PRAGMA synchronous=NORMAL")

    Base.metadata.create_all(_engine)
    _SessionFactory = sessionmaker(bind=_engine, expire_on_commit=False)
    _log.info("Database ready – tables: %s", list(Base.metadata.tables.keys()))


def get_session() -> Session:
    """Return a new database session. Caller is responsible for closing it."""
    if _SessionFactory is None:
        raise RuntimeError("Database not initialised – call init_db() first")
    return _SessionFactory()
