"""Isolated browser fixture: refuse any database not explicitly ending in _test."""
import os
from pathlib import Path
from dotenv import dotenv_values
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, delete
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
import uvicorn
from venture_forge.shared.config import Settings
from venture_forge.shared.auth import hash_password
from venture_forge.product.core.models import Base, Founder
from venture_forge.product.api.app import create_app

root = Path(__file__).resolve().parents[1]
os.environ["MODEL_ROUTER_POLICY"] = "disabled"
os.environ["MODEL_PROFILES"] = "[]"
os.environ["MODEL_PROFILES_FILE"] = ""
os.environ["APP_ENV"] = "development"
os.environ["COOKIE_SECURE"] = "false"
for key in ("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GITHUB_CLIENT_ID", "GITHUB_CLIENT_SECRET"):
    os.environ[key] = ""
portable = os.environ.get("FORGE_PORTABLE_TEST") == "1"
url = "sqlite:///" + (root / ".local" / "browser_test.sqlite3").as_posix() if portable else os.environ.get("TEST_DATABASE_URL") or dotenv_values(root / ".env")["TEST_DATABASE_URL"]
parsed = make_url(url)
if not portable and (parsed.get_backend_name() != "postgresql" or not (parsed.database or "").endswith("_test")):
    raise SystemExit("Browser tests require an isolated PostgreSQL *_test database.")
config = Config(str(root / "alembic.ini"))
config.attributes["database_url"] = url
command.upgrade(config, "head")
engine = create_engine(url)
with engine.begin() as connection:
    for table in reversed(Base.metadata.sorted_tables):
        connection.execute(delete(table))
with Session(engine) as session:
    session.add(Founder(email="browser@test.local", name="Test Founder", password_hash=hash_password("browser-test-only-password")))
    session.add(Founder(email="cycle-browser@test.local", name="Cycle Founder", password_hash=hash_password("browser-test-only-password")))
    session.add(Founder(email="agents-browser@test.local", name="Specialist Founder", password_hash=hash_password("browser-test-only-password")))
    session.commit()
engine.dispose()
import threading
import time
from venture_forge.product.worker import execute_one
application = create_app(Settings(database_url=url, app_origin="http://127.0.0.1:3001"))
def work():
    while True:
        if not execute_one(application.state.session_factory): time.sleep(0.25)
threading.Thread(target=work, daemon=True).start()
uvicorn.run(application, host="127.0.0.1", port=8011)
