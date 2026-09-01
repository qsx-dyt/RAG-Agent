import os
import sys
import tempfile
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_DIR.parent

# ensure backend/ is on sys.path when running pytest from repo root
sys.path.insert(0, str(BACKEND_DIR))

# File-based sqlite for tests: survives across threads/connections (unlike :memory:)
_db_file = Path(tempfile.gettempdir()) / "rag_test.db"
_db_file.unlink(missing_ok=True)
os.environ["DATABASE_URL"] = f"sqlite+pysqlite:///{_db_file}"

# pymilvus(及其依赖)在 import 时会把项目根 .env 加载进 os.environ,
# 污染默认值测试。记录这些键并在每个测试前清除。
_ENV_FILE_KEYS = []
_env_path = PROJECT_ROOT / ".env"
if _env_path.exists():
    for line in _env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            _ENV_FILE_KEYS.append(line.split("=", 1)[0].strip())


@pytest.fixture(autouse=True)
def _reset_settings():
    # get_settings() 是 lru_cached;清除使每个测试的环境变量修改生效
    from app.config import get_settings
    get_settings.cache_clear()
    # 清除 pymilvus 注入的 .env 变量,保持测试隔离
    for key in _ENV_FILE_KEYS:
        os.environ.pop(key, None)
    yield
    get_settings.cache_clear()
    for key in _ENV_FILE_KEYS:
        os.environ.pop(key, None)
