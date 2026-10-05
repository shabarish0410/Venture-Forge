"""Start a persistent local workspace with an optional bootstrap founder."""
import os
import secrets
import subprocess
import sys
import time
from pathlib import Path
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from venture_forge.product.core.models import Founder
from venture_forge.shared.auth import hash_password

ROOT = Path(__file__).resolve().parents[1]
local = ROOT / ".local"
local.mkdir(exist_ok=True)
os.chdir(ROOT)
database = local / "venture-forge.sqlite3"
url = "sqlite:///" + database.as_posix()
os.environ["DATABASE_URL"] = url
os.environ["APP_ORIGIN"] = "http://127.0.0.1:3000"
os.environ["APP_ENV"] = "development"
os.environ["COOKIE_SECURE"] = "false"
os.environ["FORGE_DIST_DIR"] = ".next-local"
config = Config(str(ROOT / "alembic.ini"))
config.attributes["database_url"] = url
command.upgrade(config, "head")
engine = create_engine(url)
with Session(engine) as session:
    email = "founder@ventureforge.local"
    if not session.scalar(select(Founder).where(Founder.email == email)):
        password = secrets.token_urlsafe(24)
        session.add(Founder(email=email, name="Founder", password_hash=hash_password(password)))
        session.commit()
        (local / "local-sign-in.txt").write_text(f"URL: http://127.0.0.1:3000\nEmail: {email}\nPassword: {password}\n", encoding="utf-8")
engine.dispose()
print("Venture Forge: http://127.0.0.1:3000", flush=True)
print("Sign-in details: .local/local-sign-in.txt (private local file)", flush=True)
children = []
try:
    children.append(subprocess.Popen([sys.executable, "-m", "uvicorn", "venture_forge.product.api.app:app", "--host", "127.0.0.1", "--port", "8010"]))
    children.append(subprocess.Popen([sys.executable, "-m", "venture_forge.product.worker"]))
    node = "node"
    children.append(subprocess.Popen([node, str(ROOT / "node_modules" / "next" / "dist" / "bin" / "next"), "dev", "--hostname", "127.0.0.1", "--port", "3000"], cwd=ROOT / "apps" / "web"))
    while all(p.poll() is None for p in children):
        time.sleep(1)
    raise SystemExit("A service stopped. Check the output above; local data is preserved.")
except KeyboardInterrupt:
    pass
finally:
    for process in children:
        if process.poll() is None:
            process.terminate()
    for process in children:
        try: process.wait(timeout=10)
        except subprocess.TimeoutExpired: process.kill()
