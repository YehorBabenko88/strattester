import pytest
from strattester.persistence.postgres_state_store import PostgresStateStore
def test_postgres_dependency_is_optional(monkeypatch):
    # Adapter is importable without establishing a PostgreSQL connection.
    assert PostgresStateStore is not None
