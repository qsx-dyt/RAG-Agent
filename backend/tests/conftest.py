import os
import sys
import tempfile
from pathlib import Path

import pytest

# ensure backend/ is on sys.path when running pytest from repo root
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# File-based sqlite for tests: survives across threads/connections (unlike :memory:)
_db_file = Path(tempfile.gettempdir()) / "rag_test.db"
_db_file.unlink(missing_ok=True)
os.environ["DATABASE_URL"] = f"sqlite+pysqlite:///{_db_file}"


@pytest.fixture(autouse=True)
def _reset_settings():
    # get_settings() is lru_cached; clear so per-test monkeypatch.setenv takes effect
    from app.config import get_settings
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
