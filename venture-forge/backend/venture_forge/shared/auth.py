import hashlib
import secrets
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, InvalidHashError

hasher = PasswordHasher()
COOKIE_NAME = "vf_product_session"


def hash_password(password: str) -> str:
    return hasher.hash(password)


def verify_password(encoded: str, password: str) -> bool:
    try:
        return hasher.verify(encoded, password)
    except (VerificationError, InvalidHashError):
        return False


def new_session_token() -> str:
    return secrets.token_urlsafe(32)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def issue_product_session(db, founder_id, request, response, settings, previous_hash=None, auth_method="password"):
    """Rotate the opaque session for password and provider sign-in alike."""
    from datetime import timedelta
    from sqlalchemy import delete
    from venture_forge.product.core.models import Founder, Session, now
    old_token = request.cookies.get(COOKIE_NAME)
    hashes = [value for value in (previous_hash, token_hash(old_token) if old_token else None) if value]
    if hashes:
        db.execute(delete(Session).where(Session.token_hash.in_(hashes)))
    token = new_session_token()
    timestamp = now()
    founder = db.get(Founder, founder_id)
    founder.last_login_at = timestamp
    db.add(Session(token_hash=token_hash(token), founder_id=founder_id, expires_at=timestamp + timedelta(hours=settings.session_hours), authenticated_at=timestamp, auth_method=auth_method))
    db.commit()
    response.set_cookie(COOKIE_NAME, token, max_age=settings.session_hours * 3600, httponly=True, secure=settings.cookie_secure, samesite="strict", path="/")
