"""Public email registration and password management using existing founders."""
from datetime import timedelta, timezone
from fastapi import Depends, Request, Response
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DatabaseSession
from venture_forge.product.core.models import Founder, Session, now
from venture_forge.product.core.schemas import FounderView, Register, PasswordUpdate
from venture_forge.shared.auth import COOKIE_NAME, hash_password, verify_password, issue_product_session, token_hash


def recent_provider_auth(login):
    return login and login.auth_method in {"google", "github"} and login.authenticated_at.replace(tzinfo=timezone.utc) > now() - timedelta(minutes=10)


def install_public_auth_routes(app, settings, db, owner, rate_limit, fail, dummy_hash):
    @app.post("/api/v1/auth/register", response_model=FounderView, status_code=201)
    def register(body: Register, request: Request, response: Response, session: DatabaseSession = Depends(db)):
        rate_limit(request, "registration")
        # Hash before collision handling; an existing password is never replaced.
        encoded = hash_password(body.password)
        if session.scalar(select(Founder.id).where(Founder.email == str(body.email).lower())):
            fail("ACCOUNT_EXISTS", "An account already uses this email. Sign in with your existing password or connected provider.", 409)
        founder = Founder(email=str(body.email).lower(), name=body.name, password_hash=encoded)
        session.add(founder)
        try:
            session.flush()
            issue_product_session(session, founder.id, request, response, settings)
        except IntegrityError:
            session.rollback()
            fail("ACCOUNT_EXISTS", "An account already uses this email. Sign in with your existing password or connected provider.", 409)
        return founder

    @app.post("/api/v1/auth/password", response_model=FounderView)
    def set_password(body: PasswordUpdate, request: Request, response: Response, founder: Founder = Depends(owner), session: DatabaseSession = Depends(db)):
        rate_limit(request, "password_update")
        login = session.get(Session, token_hash(request.cookies[COOKIE_NAME]))
        if not recent_provider_auth(login):
            if not founder.password_hash:
                fail("REAUTHENTICATION_REQUIRED", "Sign in with your connected provider again before adding a password.", 403)
            if not verify_password(founder.password_hash or dummy_hash, body.current_password or ""):
                fail("INVALID_CREDENTIALS", "Your current password is incorrect.", 401)
        founder.password_hash = hash_password(body.password)
        # A changed credential revokes all prior sessions and pending connections.
        session.execute(delete(Session).where(Session.founder_id == founder.id))
        issue_product_session(session, founder.id, request, response, settings)
        return founder
