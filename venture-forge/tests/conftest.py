import os
from pathlib import Path
import pytest
from alembic import command
from alembic.config import Config
from dotenv import dotenv_values
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, delete
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from venture_forge.shared.config import Settings
from venture_forge.shared.auth import hash_password
from venture_forge.product.core.models import Base, Founder
from venture_forge.product.api.app import create_app

ROOT = Path(__file__).resolve().parents[1]
PASSWORD = "test-only-founder-password"
ORIGIN = "http://127.0.0.1:3000"


@pytest.fixture(scope="session")
def database_url():
    url = os.environ.get("TEST_DATABASE_URL") or dotenv_values(ROOT / ".env").get("TEST_DATABASE_URL")
    if not url:
        pytest.fail("TEST_DATABASE_URL is required; tests run against dedicated PostgreSQL.")
    parsed = make_url(url)
    if parsed.get_backend_name() != "postgresql" or not (parsed.database or "").endswith("_test"):
        pytest.fail("Refusing to run destructive test cleanup outside a PostgreSQL *_test database.")
    config = Config(str(ROOT / "alembic.ini"))
    config.attributes["database_url"] = url
    command.upgrade(config, "head")
    return url


@pytest.fixture
def application(database_url):
    engine = create_engine(database_url)
    with engine.begin() as connection:
        for table in reversed(Base.metadata.sorted_tables):
            connection.execute(delete(table))
    with Session(engine) as session:
        session.add_all([Founder(id="00000000-0000-0000-0000-000000000001", email="one@test.local", name="One", password_hash=hash_password(PASSWORD)), Founder(id="00000000-0000-0000-0000-000000000002", email="two@test.local", name="Two", password_hash=hash_password(PASSWORD))])
        session.commit()
    app = create_app(Settings(database_url=database_url, app_origin=ORIGIN))
    yield app
    app.state.engine.dispose()
    engine.dispose()


@pytest.fixture
def client(application):
    with TestClient(application, headers={"Origin": ORIGIN}) as client:
        yield client


@pytest.fixture
def authenticated(client):
    assert client.post("/api/v1/auth/login", json={"email": "one@test.local", "password": PASSWORD}).status_code == 200
    return client
