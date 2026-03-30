"""Shared test fixtures."""

import pytest
from pathlib import Path

from haoinvest.db import Database


@pytest.fixture
def db(tmp_path: Path) -> Database:
    """Create an in-memory-like SQLite database for testing."""
    database = Database(db_path=tmp_path / "test.db")
    database.init_schema()
    yield database
    database.close()
