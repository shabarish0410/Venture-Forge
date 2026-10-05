"""Browser-bound OAuth starts/callbacks and explicit authenticated connections."""
from datetime import timedelta, timezone
from typing import Literal
import logging
import secrets
from fastapi import Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DatabaseSession
from venture_forge.product.core.models import Founder, Session, now
from venture_forge.product.core.auth_models import OAuthAttempt, OAuthIdentity
from venture_forge.shared.auth import COOKIE_NAME, issue_product_session, token_hash
from venture_forge.shared import oauth as transport
from venture_forge.product.api.public_auth import recent_provider_auth

Provider = Literal["google", "github"]
ATTEMPT_SECONDS = 600


class OAuthStart(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: Literal["sign_in", "connect"] = "sign_in"


class AuthorizationView(BaseModel):
    authorization_url: str


class ProviderView(BaseModel):
    id: Provider
    label: str
    available: bool
    connected: bool = False
    email: str | None = None


class ProviderList(BaseModel):
    providers: list[ProviderView]


class CallbackLogFilter(logging.Filter):
    def filter(self, record):
        # Uvicorn access logs must not retain authorization codes or state.
        if isinstance(record.args, tuple) and len(record.args) == 5:
            path = record.args[2]
            if isinstance(path, str) and path.startswith("/api/v1/auth/oauth/"):
                record.args = (*record.args[:2], path.split("?", 1)[0], *record.args[3:])
        return True


def cookie_name(provider):
    return "vf_oauth_" + provider


def install_oauth_routes(app, settings, db, owner, rate_limit):
    access_logger = logging.getLogger("uvicorn.access")
    if not any(isinstance(item, CallbackLogFilter) for item in access_logger.filters):
        access_logger.addFilter(CallbackLogFilter())

    def providers(identities=()):
        linked = {item.provider: item for item in identities}
        return ProviderList(providers=[ProviderView(id=provider, label=label, available=transport.configured(settings, provider), connected=provider in linked, email=linked[provider].email if provider in linked else None) for provider, label in transport.PROVIDERS.items()])

    def redirect(provider, error=None, connected=False):
        suffix = "?auth_error=" + error if error else "?auth_connected=" + provider if connected else ""
        response = RedirectResponse(settings.app_origin + "/" + suffix, status_code=303)
        response.delete_cookie(cookie_name(provider), path=f"/api/v1/auth/oauth/{provider}", httponly=True, secure=settings.cookie_secure, samesite="lax")
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    @app.get("/api/v1/auth/providers", response_model=ProviderList)
    def available_providers():
        return providers()

    @app.get("/api/v1/auth/connections", response_model=ProviderList)
    def connections(founder: Founder = Depends(owner), session: DatabaseSession = Depends(db)):
        return providers(session.scalars(select(OAuthIdentity).where(OAuthIdentity.founder_id == founder.id)).all())

    @app.get("/api/v1/auth/password-status")
    def password_status(request: Request, founder: Founder = Depends(owner), session: DatabaseSession = Depends(db)):
        login = session.get(Session, token_hash(request.cookies[COOKIE_NAME]))
        return {"email": founder.email, "enabled": founder.has_password, "requires_current": founder.has_password and not recent_provider_auth(login), "requires_reauthentication": not founder.has_password and not recent_provider_auth(login)}

    def begin(provider, mode, request, response, session):
        rate_limit(request, "oauth")
        if not transport.configured(settings, provider):
            raise HTTPException(503, {"code": "PROVIDER_NOT_CONFIGURED", "message": f"{transport.PROVIDERS[provider]} sign-in is not available yet. You can use your email and password."})
        founder_id = session_hash = None
        current_token = request.cookies.get(COOKIE_NAME)
        current_session = session.get(Session, token_hash(current_token)) if current_token else None
        if current_session and current_session.expires_at.replace(tzinfo=timezone.utc) > now():
            session_hash = current_session.token_hash
        if mode == "connect":
            founder = owner(request, session)
            founder_id = founder.id
            session_hash = token_hash(request.cookies[COOKIE_NAME])
            if session.scalar(select(OAuthIdentity).where(OAuthIdentity.founder_id == founder_id, OAuthIdentity.provider == provider)):
                raise HTTPException(409, {"code": "ALREADY_CONNECTED", "message": f"Your {transport.PROVIDERS[provider]} account is already connected."})
        state, binding, verifier, nonce = [secrets.token_urlsafe(32) for _ in range(4)]
        session.execute(delete(OAuthAttempt).where(OAuthAttempt.expires_at <= now()))
        old_binding = request.cookies.get(cookie_name(provider))
        if old_binding:
            session.execute(delete(OAuthAttempt).where(OAuthAttempt.provider == provider, OAuthAttempt.browser_hash == token_hash(old_binding)))
        session.add(OAuthAttempt(state_hash=token_hash(state), provider=provider, browser_hash=token_hash(binding), code_verifier=verifier, nonce=nonce, redirect_uri=transport.callback_uri(settings, provider), mode=mode, founder_id=founder_id, session_hash=session_hash, expires_at=now() + timedelta(seconds=ATTEMPT_SECONDS)))
        session.commit()
        response.set_cookie(cookie_name(provider), binding, max_age=ATTEMPT_SECONDS, httponly=True, secure=settings.cookie_secure, samesite="lax", path=f"/api/v1/auth/oauth/{provider}")
        return AuthorizationView(authorization_url=transport.authorization_url(settings, provider, state, verifier, nonce))

    @app.post("/api/v1/auth/oauth/{provider}/start", response_model=AuthorizationView)
    def start(provider: Provider, body: OAuthStart, request: Request, response: Response, session: DatabaseSession = Depends(db)):
        # Retained for the existing UI and origin-protected explicit account linking.
        return begin(provider, body.mode, request, response, session)

    @app.get("/api/v1/auth/oauth/{provider}/start")
    def start_redirect(provider: Provider, request: Request, session: DatabaseSession = Depends(db)):
        if request.query_params or request.headers.get("sec-fetch-site") == "cross-site" or request.headers.get("origin", settings.app_origin) != settings.app_origin:
            raise HTTPException(403, {"code": "ORIGIN_DENIED", "message": "Start sign-in from Venture Forge."})
        response = RedirectResponse(settings.app_origin, status_code=303)
        try:
            authorization = begin(provider, "sign_in", request, response, session)
        except HTTPException as error:
            if error.status_code == 503:
                return redirect(provider, "provider_unavailable")
            raise
        response.headers["location"] = authorization.authorization_url
        return response

    @app.get("/api/v1/auth/oauth/{provider}/callback")
    def callback(provider: Provider, request: Request, session: DatabaseSession = Depends(db)):
        query = request.query_params
        state = query.get("state", "")
        binding = request.cookies.get(cookie_name(provider), "")
        if not state or not binding or len(state) > 128 or len(binding) > 128 or len(query.getlist("state")) != 1 or len(query.getlist("code")) > 1 or len(query.getlist("error")) > 1:
            return redirect(provider, "invalid_state")
        # An atomic DELETE consumes state before any external exchange. Racing or
        # replayed callbacks cannot create a second session or identity.
        attempt = session.execute(delete(OAuthAttempt).where(OAuthAttempt.state_hash == token_hash(state), OAuthAttempt.provider == provider, OAuthAttempt.browser_hash == token_hash(binding)).returning(OAuthAttempt)).scalar_one_or_none()
        session.commit()
        if not attempt:
            return redirect(provider, "invalid_state")
        if attempt.expires_at.replace(tzinfo=timezone.utc) <= now():
            return redirect(provider, "expired_state")
        if attempt.redirect_uri != transport.callback_uri(settings, provider):
            return redirect(provider, "callback_mismatch")
        if query.get("error") and query.get("code"):
            return redirect(provider, "invalid_provider_response")
        if query.get("error"):
            error = query["error"]
            return redirect(provider, "cancelled" if error == "access_denied" else "callback_mismatch" if error in {"redirect_uri_mismatch", "bad_redirect_uri"} else "provider_unavailable" if error in {"server_error", "temporarily_unavailable"} else "invalid_provider_response")
        code = query.get("code", "")
        if not transport.configured(settings, provider):
            return redirect(provider, "provider_unavailable")
        if not code or len(code) > 4096:
            return redirect(provider, "invalid_provider_response")
        try:
            identity = transport.exchange_identity(settings, provider, code, attempt.code_verifier, attempt.nonce)
        except transport.OAuthFailure as error:
            return redirect(provider, error.code)

        existing = session.scalar(select(OAuthIdentity).where(OAuthIdentity.provider == provider, OAuthIdentity.subject == identity.subject))
        if attempt.mode == "connect":
            original_session = session.get(Session, attempt.session_hash)
            if not original_session or original_session.realm != "product" or original_session.founder_id != attempt.founder_id or original_session.expires_at.replace(tzinfo=timezone.utc) <= now():
                return redirect(provider, "link_session_expired")
            founder = session.get(Founder, attempt.founder_id)
            if not founder:
                return redirect(provider, "link_session_expired")
            if existing and existing.founder_id != founder.id:
                return redirect(provider, "identity_in_use")
            linked = session.scalar(select(OAuthIdentity).where(OAuthIdentity.founder_id == founder.id, OAuthIdentity.provider == provider))
            if linked and linked.subject != identity.subject:
                return redirect(provider, "already_connected")
        elif existing:
            founder = session.get(Founder, existing.founder_id)
        else:
            # A matching email never silently connects a pre-existing account.
            if session.scalar(select(Founder).where(Founder.email == identity.email)):
                return redirect(provider, "account_exists")
            founder = Founder(email=identity.email, name=identity.name, avatar_url=identity.avatar_url, password_hash=None)
            session.add(founder)
        if not founder or (founder.id and not founder.is_active):
            return redirect(provider, "account_disabled")
        response = redirect(provider, connected=attempt.mode == "connect")
        try:
            session.flush()
            if not existing:
                existing = OAuthIdentity(founder_id=founder.id, provider=provider, subject=identity.subject)
                session.add(existing)
            existing.email = identity.email
            existing.email_verified = identity.email_verified
            existing.display_name = identity.name
            existing.avatar_url = identity.avatar_url
            existing.last_login_at = now()
            issue_product_session(session, founder.id, request, response, settings, previous_hash=attempt.session_hash, auth_method=provider)
        except IntegrityError:
            session.rollback()
            return redirect(provider, "account_conflict")
        return response
