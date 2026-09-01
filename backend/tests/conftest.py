import os
import sys
import tempfile
from pathlib import Path

# ensure backend/ is on sys.path when running pytest from repo root
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# File-based sqlite for tests: survives across threads/connections (unlike :memory:)
_db_file = Path(tempfile.gettempdir()) / "rag_test.db"
_db_file.unlink(missing_ok=True)
os.environ["DATABASE_URL"] = f"sqlite+pysqlite:///{_db_file}"
