"""Atomic, shared authentication limits for SQLite and PostgreSQL workers."""
from datetime import datetime, timezone
import hashlib
import time
from fastapi import HTTPException
from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from venture_forge.product.core.auth_models import AuthRateLimit


def limit_auth(factory, request, category):
    timestamp = time.time()
    window = int(timestamp) // 60
    client = request.client.host if request.client else "unknown"
    key = hashlib.sha256(f"{category}:{client}:{window}".encode()).hexdigest()
    expiry = datetime.fromtimestamp((window + 1) * 60, timezone.utc)
    with factory() as session:
        insert = sqlite_insert if session.bind.dialect.name == "sqlite" else postgres_insert
        session.execute(delete(AuthRateLimit).where(AuthRateLimit.expires_at <= datetime.fromtimestamp(timestamp, timezone.utc)))
        statement = insert(AuthRateLimit).values(key=key, attempts=1, expires_at=expiry)
        statement = statement.on_conflict_do_update(index_elements=[AuthRateLimit.key], set_={"attempts": AuthRateLimit.attempts + 1}, where=AuthRateLimit.attempts < 10)
        accepted = session.execute(statement.returning(AuthRateLimit.attempts)).scalar_one_or_none()
        session.commit()
    if accepted is None:
        raise HTTPException(429, {"code": "RATE_LIMITED", "message": "Too many attempts. Try again in a minute."}, headers={"Retry-After": str(max(1, int((window + 1) * 60 - timestamp)))})
