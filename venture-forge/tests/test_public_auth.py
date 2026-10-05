"""Public signup and account continuity using isolated databases/provider mocks."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from urllib.parse import parse_qs, urlsplit
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import select, func
from venture_forge.product.api.app import create_app
from venture_forge.product.core.models import Founder, Session, now
from venture_forge.product.core.auth_models import OAuthAttempt, OAuthIdentity
from venture_forge.shared.auth import COOKIE_NAME, token_hash, verify_password
from venture_forge.shared.config import Settings
from test_oauth import auth, provider_http, signing_key, begin, callback, ORIGIN, PASSWORD

SIGNUP = {"email": "New.Founder@example.com", "password": "a long founder passphrase", "name": " New Founder "}
VENTURE = {"name": "Shared Passport", "idea": "Help founders learn from customer interviews before building.", "customer_segment": "First-time founders", "geography": "India", "first_hypothesis": "Founders need structured support for customer interviews."}


def password_login(auth):
    response = auth.client.post("/api/v1/auth/login", json={"email": "existing@forge.test", "password": PASSWORD})
    assert response.status_code == 200
    return response


def test_public_registration_login_logout_and_onboarding(auth):
    response = auth.client.post("/api/v1/auth/register", json=SIGNUP)
    assert response.status_code == 201
    profile = response.json()
    assert profile["email"] == "new.founder@example.com" and profile["name"] == "New Founder"
    assert profile["has_password"] and not profile["onboarding_completed"]
    assert profile["last_login_at"] and profile["created_at"]
    assert "password_hash" not in response.text and SIGNUP["password"] not in response.text
    token = auth.client.cookies.get(COOKIE_NAME)
    assert "HttpOnly" in response.headers["set-cookie"] and "SameSite=strict" in response.headers["set-cookie"]
    with auth.app.state.session_factory() as db:
        founder = db.get(Founder, profile["id"])
        assert verify_password(founder.password_hash, SIGNUP["password"])
        assert db.get(Session, token_hash(token))
    passport = auth.client.post("/api/v1/ventures", json=VENTURE, headers={"Idempotency-Key": "signup-venture"})
    assert passport.status_code == 201
    assert auth.client.get("/api/v1/auth/me").json()["onboarding_completed"] is True
    assert auth.client.post("/api/v1/auth/logout").status_code == 204
    assert auth.client.get("/api/v1/auth/me").status_code == 401
    with auth.app.state.session_factory() as db:
        assert db.get(Session, token_hash(token)) is None
    login = auth.client.post("/api/v1/auth/login", json={"email": SIGNUP["email"], "password": SIGNUP["password"]})
    assert login.status_code == 200 and login.json()["id"] == profile["id"]
    assert auth.client.cookies.get(COOKIE_NAME) != token
    assert auth.client.get("/api/v1/ventures").json()["ventures"][0]["id"] == passport.json()["venture"]["id"]


@pytest.mark.parametrize("changes", [{"email": "invalid-address"}, {"password": "too-short"}, {"password": "x" * 129}, {"name": " "}, {"is_active": True}])
def test_registration_validates_on_server_without_echoing_secrets(auth, changes):
    body = {**SIGNUP, **changes}
    response = auth.client.post("/api/v1/auth/register", json=body)
    assert response.status_code == 422
    assert body["password"] not in response.text
    assert auth.client.get("/api/v1/auth/me").status_code == 401


def test_registration_origin_collision_and_concurrent_uniqueness(auth):
    assert auth.client.post("/api/v1/auth/register", json=SIGNUP, headers={"Origin": "https://attacker.test"}).status_code == 403
    def register(_):
        with TestClient(auth.app, headers={"Origin": ORIGIN}) as client:
            return client.post("/api/v1/auth/register", json=SIGNUP).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(register, range(2))) == [201, 409]
    password_login(auth)
    prior = auth.client.cookies.get(COOKIE_NAME)
    assert auth.client.post("/api/v1/auth/register", json={**SIGNUP, "email": "new.founder@example.com"}).status_code == 409
    assert auth.client.cookies.get(COOKIE_NAME) == prior
    assert auth.client.get("/api/v1/auth/me").json()["id"] == auth.founder_id


@pytest.mark.parametrize("provider", ["google", "github"])
def test_get_start_public_signup_metadata_and_existing_login(auth, provider_http, provider):
    response = auth.client.get(f"/api/v1/auth/oauth/{provider}/start")
    assert response.status_code == 303
    values = {key: value[0] for key, value in parse_qs(urlsplit(response.headers["location"]).query).items()}
    assert values["redirect_uri"] == ORIGIN + f"/api/v1/auth/oauth/{provider}/callback"
    assert values["scope"] == ("openid email profile" if provider == "google" else "user:email")
    assert values["code_challenge_method"] == "S256"
    provider_http.nonce = values.get("nonce", "")
    provider_http.claims["picture"] = "https://example.com/avatar.png"
    assert callback(auth, values, provider).status_code == 303
    user = auth.client.get("/api/v1/auth/me").json()
    assert not user["has_password"] and not user["onboarding_completed"]
    first_login = user["last_login_at"]
    with auth.app.state.session_factory() as db:
        identity = db.scalar(select(OAuthIdentity))
        assert identity.subject == ("google-stable-subject" if provider == "google" else "2468")
        assert identity.email_verified and identity.display_name and identity.last_login_at
        if provider == "google":
            assert identity.avatar_url == user["avatar_url"] == "https://example.com/avatar.png"
    old_token = auth.client.cookies.get(COOKIE_NAME)
    values, _ = begin(auth, provider)
    provider_http.nonce = values.get("nonce", "")
    # Rotation also revokes the initiating session when Strict cookies are absent.
    auth.client.cookies.delete(COOKIE_NAME)
    callback(auth, values, provider)
    profile = auth.client.get("/api/v1/auth/me").json()
    assert profile["id"] == user["id"] and profile["last_login_at"] >= first_login
    with auth.app.state.session_factory() as db:
        assert db.get(Session, token_hash(old_token)) is None
        assert db.scalar(select(func.count()).select_from(OAuthIdentity)) == 1


def test_get_start_cannot_link_or_accept_an_external_redirect(auth):
    password_login(auth)
    for query in ("?mode=connect", "?redirect_uri=https://attacker.test", "?return_to=https://attacker.test"):
        assert auth.client.get("/api/v1/auth/oauth/google/start" + query).status_code == 403
    assert auth.client.get("/api/v1/auth/oauth/google/start", headers={"Sec-Fetch-Site": "cross-site"}).status_code == 403
    assert auth.client.get("/api/v1/auth/oauth/google/start", headers={"Origin": "https://attacker.test"}).status_code == 403


def test_separate_oauth_attempts_cannot_duplicate_provider_identity(auth, provider_http):
    first, _ = begin(auth, "github")
    second, _ = begin(auth, "github")
    # Use separate browsers so both state records remain independently valid.
    from venture_forge.product.api.oauth import cookie_name
    with auth.app.state.session_factory() as db:
        # begin() deliberately retires a prior attempt in the same browser.
        assert db.get(OAuthAttempt, token_hash(first["state"])) is None
    auth.client.cookies.delete(cookie_name("github"))
    third, _ = begin(auth, "github")
    def complete(values):
        with TestClient(auth.app, follow_redirects=False) as client:
            client.cookies.set(cookie_name("github"), values["binding"])
            return client.get("/api/v1/auth/oauth/github/callback", params={"state": values["state"], "code": "unique-code-" + values["state"]}).headers["location"]
    with ThreadPoolExecutor(max_workers=2) as pool:
        destinations = list(pool.map(complete, (second, third)))
    assert ORIGIN + "/" in destinations
    assert all(destination in {ORIGIN + "/", ORIGIN + "/?auth_error=account_conflict"} for destination in destinations)
    with auth.app.state.session_factory() as db:
        assert db.scalar(select(func.count()).select_from(Founder)) == 2
        assert db.scalar(select(func.count()).select_from(OAuthIdentity)) == 1


def test_unconfigured_get_start_preserves_authenticated_session(auth):
    from pydantic import SecretStr
    password_login(auth)
    before = auth.client.cookies.get(COOKIE_NAME)
    auth.settings.google_client_secret = SecretStr("")
    response = auth.client.get("/api/v1/auth/oauth/google/start")
    assert response.headers["location"] == ORIGIN + "/?auth_error=provider_unavailable"
    assert auth.client.cookies.get(COOKIE_NAME) == before
    assert auth.client.get("/api/v1/auth/me").json()["id"] == auth.founder_id


def test_both_providers_and_password_open_same_passport(auth, provider_http):
    password_login(auth)
    response = auth.client.post("/api/v1/ventures", json=VENTURE, headers={"Idempotency-Key": "shared-passport"})
    assert response.status_code == 201
    passport = response.json()
    passport = auth.client.get(f"/api/v1/ventures/{passport['venture']['id']}/passport").json()
    for provider in ("google", "github"):
        values, _ = begin(auth, provider, mode="connect")
        provider_http.nonce = values.get("nonce", "")
        assert callback(auth, values, provider).headers["location"].endswith("auth_connected=" + provider)
    assert all(item["connected"] for item in auth.client.get("/api/v1/auth/connections").json()["providers"])
    for provider in ("google", "github", "password"):
        auth.client.post("/api/v1/auth/logout")
        if provider == "password":
            password_login(auth)
        else:
            values, _ = begin(auth, provider)
            provider_http.nonce = values.get("nonce", "")
            callback(auth, values, provider)
        assert auth.client.get("/api/v1/auth/me").json()["id"] == auth.founder_id
        assert auth.client.get(f"/api/v1/ventures/{passport['venture']['id']}/passport").json() == passport
    with auth.app.state.session_factory() as db:
        assert db.scalar(select(func.count()).select_from(Founder)) == 1
        assert db.scalar(select(func.count()).select_from(OAuthIdentity)) == 2


@pytest.mark.parametrize("failure", ["cancelled", "invalid_state", "expired_state", "provider_unavailable", "email_unavailable", "account_exists", "callback_mismatch", "invalid_provider_response"])
def test_callback_failures_preserve_existing_session_and_passport(auth, provider_http, failure):
    password_login(auth)
    passport = auth.client.post("/api/v1/ventures", json=VENTURE, headers={"Idempotency-Key": "failure-passport"}).json()
    passport = auth.client.get(f"/api/v1/ventures/{passport['venture']['id']}/passport").json()
    before = auth.client.cookies.get(COOKIE_NAME)
    values, _ = begin(auth)
    provider_http.nonce = values["nonce"]
    extra = {}
    if failure == "cancelled": extra["error"] = "access_denied"
    if failure == "invalid_state": values["state"] = "wrong-state"
    if failure in {"expired_state", "callback_mismatch"}:
        with auth.app.state.session_factory() as db:
            attempt = db.get(OAuthAttempt, token_hash(values["state"]))
            if failure == "expired_state": attempt.expires_at = now() - timedelta(seconds=1)
            else: attempt.redirect_uri = "https://old.example.com/api/v1/auth/oauth/google/callback"
            db.commit()
    if failure == "provider_unavailable": provider_http.http_error = True
    if failure == "email_unavailable": provider_http.claims["email"] = None
    if failure == "account_exists": provider_http.claims["email"] = "existing@forge.test"
    if failure == "invalid_provider_response": extra.update(error="access_denied", code="ambiguous-code")
    response = callback(auth, values, **extra)
    assert response.headers["location"] == ORIGIN + "/?auth_error=" + failure
    assert auth.client.cookies.get(COOKIE_NAME) == before
    assert not any(COOKIE_NAME in cookie for cookie in response.headers.get_list("set-cookie"))
    assert auth.client.get(f"/api/v1/ventures/{passport['venture']['id']}/passport").json() == passport


@pytest.mark.parametrize("provider", ["google", "github"])
def test_disabled_user_cannot_login_or_link_but_other_session_survives(auth, provider_http, provider):
    values, _ = begin(auth, provider)
    provider_http.nonce = values.get("nonce", "")
    callback(auth, values, provider)
    disabled_id = auth.client.get("/api/v1/auth/me").json()["id"]
    with auth.app.state.session_factory() as db:
        db.get(Founder, disabled_id).is_active = False
        db.commit()
    assert auth.client.get("/api/v1/auth/me").status_code == 403
    assert auth.client.get("/api/v1/ventures").status_code == 403
    assert auth.client.post(f"/api/v1/auth/oauth/{provider}/start", json={"mode": "connect"}).status_code == 403
    password_login(auth)
    before = auth.client.cookies.get(COOKIE_NAME)
    values, _ = begin(auth, provider)
    provider_http.nonce = values.get("nonce", "")
    assert callback(auth, values, provider).headers["location"].endswith("auth_error=account_disabled")
    assert auth.client.cookies.get(COOKIE_NAME) == before
    assert auth.client.get("/api/v1/auth/me").json()["id"] == auth.founder_id
    with auth.app.state.session_factory() as db:
        db.get(Founder, auth.founder_id).is_active = False
        db.commit()
    response = auth.client.post("/api/v1/auth/login", json={"email": "existing@forge.test", "password": PASSWORD})
    assert response.status_code == 403 and response.json()["detail"]["code"] == "ACCOUNT_DISABLED"


def test_password_creation_after_oauth_and_change_rotates_sessions(auth, provider_http):
    values, _ = begin(auth)
    provider_http.nonce = values["nonce"]
    callback(auth, values)
    profile = auth.client.get("/api/v1/auth/me").json()
    assert auth.client.get("/api/v1/auth/password-status").json()["enabled"] is False
    original = auth.client.cookies.get(COOKIE_NAME)
    with auth.app.state.session_factory() as db:
        db.add(Session(token_hash=token_hash("another-session"), founder_id=profile["id"], expires_at=now() + timedelta(hours=1)))
        db.commit()
    response = auth.client.post("/api/v1/auth/password", json={"password": SIGNUP["password"]})
    assert response.status_code == 200 and response.json()["has_password"]
    with auth.app.state.session_factory() as db:
        assert db.get(Session, token_hash(original)) is None
        assert db.get(Session, token_hash("another-session")) is None
    assert auth.client.post("/api/v1/auth/password", json={"password": "a different long passphrase", "current_password": "wrong"}).status_code == 401
    assert auth.client.post("/api/v1/auth/password", json={"password": "a different long passphrase", "current_password": SIGNUP["password"]}).status_code == 200
    auth.client.post("/api/v1/auth/logout")
    response = auth.client.post("/api/v1/auth/login", json={"email": profile["email"], "password": "a different long passphrase"})
    assert response.status_code == 200 and response.json()["id"] == profile["id"]


def test_stale_provider_session_cannot_add_password(auth, provider_http):
    values, _ = begin(auth)
    provider_http.nonce = values["nonce"]
    callback(auth, values)
    with auth.app.state.session_factory() as db:
        db.get(Session, token_hash(auth.client.cookies.get(COOKIE_NAME))).authenticated_at = now() - timedelta(minutes=11)
        db.commit()
    assert auth.client.get("/api/v1/auth/password-status").json()["requires_reauthentication"]
    assert auth.client.post("/api/v1/auth/password", json={"password": SIGNUP["password"]}).status_code == 403


def test_authentication_limits_are_shared_across_workers(auth):
    another_app = create_app(auth.settings)
    try:
        with TestClient(another_app, headers={"Origin": ORIGIN}, follow_redirects=False) as other:
            for index in range(10):
                client = auth.client if index % 2 else other
                assert client.post("/api/v1/auth/oauth/google/start", json={}).status_code == 200
            response = auth.client.post("/api/v1/auth/oauth/google/start", json={})
            assert response.status_code == 429 and 1 <= int(response.headers["retry-after"]) <= 60
    finally:
        another_app.state.engine.dispose()


@pytest.mark.parametrize("values", [{"app_origin": "http://public.example.com"}, {"app_origin": "https://public.example.com", "cookie_secure": False}, {"app_env": "production", "app_origin": ORIGIN, "cookie_secure": True}, {"session_hours": 0}])
def test_insecure_production_configuration_is_rejected(values):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, database_url="sqlite://", **values)


def test_production_callbacks_and_secure_sessions(auth):
    auth.settings.app_origin = "https://forge.example.com"
    auth.settings.cookie_secure = True
    auth.client.headers["Origin"] = auth.settings.app_origin
    for provider in ("google", "github"):
        response = auth.client.get(f"/api/v1/auth/oauth/{provider}/start")
        values = parse_qs(urlsplit(response.headers["location"]).query)
        assert values["redirect_uri"] == [f"https://forge.example.com/api/v1/auth/oauth/{provider}/callback"]
        assert "Secure" in response.headers["set-cookie"]
    response = auth.client.post("/api/v1/auth/register", json=SIGNUP)
    assert response.status_code == 201 and "Secure" in response.headers["set-cookie"]


def test_migration_preserves_linked_identity_session_and_passport(tmp_path):
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import Session as DatabaseSession
    from conftest import ROOT
    config = Config(str(ROOT / "alembic.ini"))
    url = f"sqlite:///{(tmp_path / 'public_migration.sqlite3').as_posix()}"
    config.attributes["database_url"] = url
    command.upgrade(config, "0005")
    engine = create_engine(url)
    created = now() - timedelta(days=10)
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO founders (id,email,name,password_hash,created_at) VALUES (:id,:email,:name,:hash,:created)"), {"id": "existing-founder", "email": "founder@example.com", "name": "Preserved", "hash": "existing-password-hash", "created": created})
        connection.execute(text("INSERT INTO ventures (id,owner_id,name,idea,customer_segment,geography,stage,revision,created_at,updated_at) VALUES ('existing-venture','existing-founder','Preserved Passport','An existing idea','Founders','India','idea',1,:created,:created)"), {"created": created})
        connection.execute(text("INSERT INTO oauth_identities (id,founder_id,provider,subject,email,created_at) VALUES ('existing-identity','existing-founder','google','immutable-id','verified@example.com',:created)"), {"created": created})
        connection.execute(text("INSERT INTO product_sessions (token_hash,founder_id,realm,expires_at) VALUES (:hash,'existing-founder','product',:expires)"), {"hash": token_hash("old-session"), "expires": now() + timedelta(hours=1)})
    command.upgrade(config, "head")
    command.check(config)
    with DatabaseSession(engine) as db:
        founder = db.get(Founder, "existing-founder")
        assert founder.onboarding_completed and founder.is_active
        assert founder.password_hash == "existing-password-hash"
        identity = db.get(OAuthIdentity, "existing-identity")
        assert identity.subject == "immutable-id" and identity.email_verified
        login = db.get(Session, token_hash("old-session"))
        assert login.founder_id == founder.id and login.authenticated_at.replace(tzinfo=created.tzinfo) == created
    command.downgrade(config, "0005")
    command.upgrade(config, "head")
    command.check(config)
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT owner_id FROM ventures WHERE id='existing-venture'")) == "existing-founder"
        assert connection.scalar(text("SELECT subject FROM oauth_identities WHERE id='existing-identity'")) == "immutable-id"
    engine.dispose()
