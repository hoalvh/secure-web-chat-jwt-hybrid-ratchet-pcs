"""Test configuration.

Point the database at an isolated throwaway SQLite file before the app (and its
db module) are imported, so running the suite never touches dev/demo data. Each
test resets the schema via reset_demo_store().
"""

import os
import tempfile
from pathlib import Path

_TEST_DB = Path(tempfile.gettempdir()) / "secure_chat_test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB.as_posix()}"
os.environ.setdefault("JWT_SECRET", "test-secret")
