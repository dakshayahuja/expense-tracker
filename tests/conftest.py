"""
Pytest configuration for expense-tracker.

Sets DATABASE_URL to SQLite before importing api modules so the whole
app runs against an isolated test database (no Postgres needed).
dotenv never overrides existing env vars, so we set it first.
"""
import os

# Must be set BEFORE any api.* import so database.py picks up SQLite
os.environ["DATABASE_URL"] = "sqlite:///./test_expenses.db"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from api.models import Base
from api.database import get_db
from api.index import app

_TEST_DB_URL = "sqlite:///./test_expenses.db"
_test_engine = create_engine(_TEST_DB_URL, connect_args={"check_same_thread": False})
_TestSession = sessionmaker(autocommit=False, autoflush=False, bind=_test_engine)

# Create all tables once per session
Base.metadata.create_all(bind=_test_engine)


@pytest.fixture(autouse=True)
def _clear_db():
    """Wipe every table after each test for isolation."""
    yield
    with _test_engine.connect() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())
        conn.commit()


def _override_db():
    db = _TestSession()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def client():
    app.dependency_overrides[get_db] = _override_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def db():
    """Direct SQLAlchemy session for seeding test data."""
    session = _TestSession()
    yield session
    session.close()
