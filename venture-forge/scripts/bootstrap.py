"""Create the local founder after migrations; existing accounts are never changed."""
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from venture_forge.shared.config import Settings
from venture_forge.shared.auth import hash_password
from venture_forge.product.core.models import Founder

settings = Settings()
if len(settings.bootstrap_password) < 16:
    raise SystemExit("Set BOOTSTRAP_PASSWORD to a random secret of at least 16 characters.")
with Session(create_engine(settings.database_url)) as session:
    if session.scalar(select(Founder).where(Founder.email == settings.bootstrap_email.lower())):
        print("Founder already exists; existing password preserved.")
    else:
        session.add(Founder(email=settings.bootstrap_email.lower(), name="Founder", password_hash=hash_password(settings.bootstrap_password)))
        session.commit()
        print("Local founder created. Sign-in details are in .local/sign-in.txt.")
