import os
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path):
    db_path = tmp_path / "test.db"
    os.environ['KREDETE_DB_PATH'] = str(db_path)
    # import app after environment is set so init_db() uses this path
    from app.main import app
    # ensure DB initialized
    from app.db import init_db
    init_db()
    client = TestClient(app)
    yield client
    try:
        client.close()
    except Exception:
        pass
    try:
        os.remove(str(db_path))
    except Exception:
        pass
