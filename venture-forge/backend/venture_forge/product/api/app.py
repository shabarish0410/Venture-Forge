from datetime import timedelta, timezone
import hashlib
import json
from fastapi import FastAPI, Depends, HTTPException, Request, Response, Header
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy import create_engine, select, delete, event
from sqlalchemy.orm import sessionmaker, Session as DatabaseSession
from venture_forge.shared.config import Settings
from venture_forge.shared.auth import COOKIE_NAME, hash_password, verify_password, token_hash, issue_product_session
from venture_forge.shared.auth_limits import limit_auth
from venture_forge.product.core.models import Founder, Session, Venture, Hypothesis, Activity, IdempotencyRecord, now
from venture_forge.product.core.schemas import Login, FounderView, VentureCreate, HypothesisCreate, VentureView, VentureList, Passport, HypothesisView


def fail(code: str, message: str, status: int = 400):
    raise HTTPException(status, {"code": code, "message": message})


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    app = FastAPI(title="Venture Forge Product API", version="0.1.0")
    engine = create_engine(settings.database_url, pool_pre_ping=True)
    if engine.dialect.name == "sqlite":
        @event.listens_for(engine, "connect")
        def enable_foreign_keys(connection, record):
            connection.execute("PRAGMA foreign_keys=ON")
    factory = sessionmaker(engine, expire_on_commit=False)
    app.state.engine, app.state.session_factory = engine, factory
    dummy_hash = hash_password("invalid-account-placeholder")

    def rate_limit(request, category):
        limit_auth(factory, request, category)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, error):
        # Never reflect submitted passwords or provider secrets in validation errors.
        return JSONResponse(status_code=422, content={"detail": [{"loc": item["loc"], "type": item["type"], "msg": item["msg"]} for item in error.errors()]})

    @app.middleware("http")
    async def protect_origin(request: Request, call_next):
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            if request.headers.get("origin") != settings.app_origin:
                return JSONResponse(status_code=403, content={"detail": {"code": "ORIGIN_DENIED", "message": "Request origin is not permitted."}})
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    def db():
        with factory() as session:
            yield session

    def owner(request: Request, session: DatabaseSession = Depends(db)) -> Founder:
        token = request.cookies.get(COOKIE_NAME, "")
        login = session.get(Session, token_hash(token)) if token else None
        if not login or login.realm != "product" or login.expires_at.replace(tzinfo=timezone.utc) <= now():
            fail("UNAUTHENTICATED", "Sign in to your founder workspace.", 401)
        founder = session.get(Founder, login.founder_id)
        if not founder:
            fail("UNAUTHENTICATED", "Session is no longer valid.", 401)
        if not founder.is_active:
            fail("ACCOUNT_DISABLED", "This Venture Forge account is disabled. Contact support.", 403)
        return founder

    def owned_venture(session: DatabaseSession, founder: Founder, venture_id: str, lock=False):
        query = select(Venture).where(Venture.id == venture_id, Venture.owner_id == founder.id)
        if lock:
            query = query.with_for_update()
        venture = session.scalar(query)
        if not venture:
            fail("NOT_FOUND", "Venture not found.", 404)
        return venture

    def passport(session: DatabaseSession, venture: Venture) -> Passport:
        scope = (Hypothesis.venture_id == venture.id, Hypothesis.owner_id == venture.owner_id)
        hypotheses = session.scalars(select(Hypothesis).where(*scope).order_by(Hypothesis.created_at)).all()
        activity = session.scalars(select(Activity).where(Activity.venture_id == venture.id, Activity.owner_id == venture.owner_id).order_by(Activity.created_at.desc()).limit(30)).all()
        from venture_forge.product.api.workflows import read_workspace
        return Passport(venture=venture, hypotheses=hypotheses, activity=activity, **read_workspace(session, venture))

    def digest(value):
        return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    def replay(session, founder, operation, key, payload):
        if not key or len(key) > 100:
            fail("IDEMPOTENCY_KEY_REQUIRED", "A request key is required.")
        prior = session.scalar(select(IdempotencyRecord).where(IdempotencyRecord.owner_id == founder.id, IdempotencyRecord.operation == operation, IdempotencyRecord.key == key))
        if prior and prior.request_hash != digest(payload):
            fail("IDEMPOTENCY_CONFLICT", "This request key was used with different content.", 409)
        return prior.response if prior else None

    def remember(session, founder, operation, key, payload, response):
        session.add(IdempotencyRecord(owner_id=founder.id, operation=operation, key=key, request_hash=digest(payload), response=response))

    @app.get("/api/v1/health")
    def health():
        from venture_forge.product.agents.gateway import available
        return {"status": "ok", "realm": "product", "milestone": "specialist-pipelines", "specialists": 13, "model_enabled": available(settings)}

    @app.post("/api/v1/auth/login", response_model=FounderView)
    def login(body: Login, response: Response, request: Request, session: DatabaseSession = Depends(db)):
        rate_limit(request, "password")
        founder = session.scalar(select(Founder).where(Founder.email == body.email.lower()))
        valid = verify_password(founder.password_hash if founder and founder.password_hash else dummy_hash, body.password)
        if not founder or not founder.password_hash or not valid:
            fail("INVALID_CREDENTIALS", "Email or password is incorrect.", 401)
        if not founder.is_active:
            fail("ACCOUNT_DISABLED", "This Venture Forge account is disabled. Contact support.", 403)
        issue_product_session(session, founder.id, request, response, settings)
        return founder

    from venture_forge.product.api.public_auth import install_public_auth_routes
    install_public_auth_routes(app, settings, db, owner, rate_limit, fail, dummy_hash)

    from venture_forge.product.api.oauth import install_oauth_routes
    install_oauth_routes(app, settings, db, owner, rate_limit)

    @app.get("/api/v1/auth/me", response_model=FounderView)
    def me(founder: Founder = Depends(owner)):
        return founder

    @app.post("/api/v1/auth/logout", status_code=204)
    def logout(request: Request, response: Response, session: DatabaseSession = Depends(db)):
        session.execute(delete(Session).where(Session.token_hash == token_hash(request.cookies.get(COOKIE_NAME, ""))))
        session.commit()
        response.delete_cookie(COOKIE_NAME, path="/", httponly=True, samesite="strict", secure=settings.cookie_secure)

    @app.get("/api/v1/ventures", response_model=VentureList)
    def ventures(founder: Founder = Depends(owner), session: DatabaseSession = Depends(db)):
        return {"ventures": session.scalars(select(Venture).where(Venture.owner_id == founder.id)).all()}

    @app.post("/api/v1/ventures", response_model=Passport, status_code=201)
    def create_venture(body: VentureCreate, founder: Founder = Depends(owner), session: DatabaseSession = Depends(db), idempotency_key: str | None = Header(default=None)):
        # Serialize creation for this founder, including same-key concurrent retries.
        session.scalar(select(Founder).where(Founder.id == founder.id).with_for_update())
        payload = body.model_dump()
        prior = replay(session, founder, "create_venture", idempotency_key, payload)
        if prior:
            return prior
        if session.scalar(select(Venture.id).where(Venture.owner_id == founder.id)):
            fail("VENTURE_EXISTS", "The foundation supports one venture per founder.", 409)
        venture = Venture(owner_id=founder.id, **body.model_dump(exclude={"first_hypothesis"}))
        founder.onboarding_completed = True
        session.add(venture)
        session.flush()
        session.add(Hypothesis(venture_id=venture.id, owner_id=founder.id, statement=body.first_hypothesis, category="problem"))
        session.add(Activity(venture_id=venture.id, owner_id=founder.id, event_type="venture.created", description="Venture created with its first unvalidated hypothesis."))
        session.flush()
        result = passport(session, venture).model_dump(mode="json")
        remember(session, founder, "create_venture", idempotency_key, payload, result)
        session.commit()
        return result

    @app.get("/api/v1/ventures/{venture_id}/passport", response_model=Passport)
    def get_passport(venture_id: str, founder: Founder = Depends(owner), session: DatabaseSession = Depends(db)):
        return passport(session, owned_venture(session, founder, venture_id))

    @app.get("/api/v1/ventures/{venture_id}/hypotheses", response_model=list[HypothesisView])
    def list_hypotheses(venture_id: str, founder: Founder = Depends(owner), session: DatabaseSession = Depends(db)):
        return passport(session, owned_venture(session, founder, venture_id)).hypotheses

    @app.post("/api/v1/ventures/{venture_id}/hypotheses", response_model=Passport, status_code=201)
    def add_hypothesis(venture_id: str, body: HypothesisCreate, founder: Founder = Depends(owner), session: DatabaseSession = Depends(db), idempotency_key: str | None = Header(default=None)):
        venture = owned_venture(session, founder, venture_id, lock=True)
        operation = f"hypothesis:{venture_id}"
        payload = body.model_dump()
        prior = replay(session, founder, operation, idempotency_key, payload)
        if prior:
            return prior
        if venture.revision != body.expected_revision:
            fail("REVISION_CONFLICT", "Your Passport changed. Reload it before adding this hypothesis.", 409)
        session.add(Hypothesis(venture_id=venture.id, owner_id=founder.id, statement=body.statement, category=body.category))
        venture.revision += 1
        venture.updated_at = now()
        session.add(Activity(venture_id=venture.id, owner_id=founder.id, event_type="hypothesis.created", description=f"A {body.category} hypothesis was recorded as unvalidated."))
        session.flush()
        result = passport(session, venture).model_dump(mode="json")
        remember(session, founder, operation, idempotency_key, payload, result)
        session.commit()
        return result

    @app.api_route("/api/company/v1/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"], include_in_schema=False)
    def company_boundary(path: str):
        fail("REALM_UNAVAILABLE", "Company OS has a separate authority boundary and is not active.", 403)

    from venture_forge.product.api.workflows import install_workflows
    install_workflows(app, db, owner, owned_venture, passport, replay, remember, fail, settings)
    return app


app = create_app()
