"""Isolated OAuth tests with real JWT signatures and mocked provider HTTP."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import logging
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit
import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from sqlalchemy import select, func
from venture_forge.product.api.app import create_app
from venture_forge.product.api.oauth import CallbackLogFilter, cookie_name
from venture_forge.product.core.models import Base, Founder, Session, now
from venture_forge.product.core.auth_models import OAuthAttempt, OAuthIdentity
from venture_forge.shared import oauth
from venture_forge.shared.auth import COOKIE_NAME, hash_password, token_hash
from venture_forge.shared.config import Settings

ORIGIN = "http://127.0.0.1:3000"
PASSWORD = "isolated-oauth-test-password"


@pytest.fixture(scope="module")
def signing_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture
def auth(tmp_path):
    settings = Settings(_env_file=None, database_url=f"sqlite:///{(tmp_path / 'auth_test.sqlite3').as_posix()}", app_origin=ORIGIN,
        model_router_policy="disabled", model_profiles=[], model_profiles_file=None,
        google_client_id="google-client-test", google_client_secret="google-secret-test",
        github_client_id="github-client-test", github_client_secret="github-secret-test")
    app = create_app(settings)
    Base.metadata.create_all(app.state.engine)
    with app.state.session_factory() as db:
        founder = Founder(email="existing@forge.test", name="Existing founder", password_hash=hash_password(PASSWORD))
        db.add(founder); db.commit()
        founder_id = founder.id
    with TestClient(app, headers={"Origin": ORIGIN}, follow_redirects=False) as client:
        yield SimpleNamespace(app=app, client=client, settings=settings, founder_id=founder_id)
    app.state.engine.dispose()


def begin(auth, provider="google", mode="sign_in"):
    response = auth.client.post(f"/api/v1/auth/oauth/{provider}/start", json={"mode": mode})
    assert response.status_code == 200, response.text
    values = {key: value[0] for key, value in parse_qs(urlsplit(response.json()["authorization_url"]).query).items()}
    values["binding"] = auth.client.cookies.get(cookie_name(provider))
    return values, response


def callback(auth, values, provider="google", **extra):
    code = {} if "error" in extra else {"code": "one-use-code"}
    return auth.client.get(f"/api/v1/auth/oauth/{provider}/callback", params={"state": values["state"], **code, **extra})


@pytest.fixture
def provider_http(monkeypatch, signing_key):
    context = SimpleNamespace(claims={}, requests=[], nonce="", signer=signing_key, token_error=False, http_error=False,
        algorithm="RS256", github_id=2468, emails=[{"email": "new@verified.test", "verified": True, "primary": True}])
    public_key = jwt.algorithms.RSAAlgorithm.to_jwk(signing_key.public_key(), as_dict=True)
    public_key.update(kid="test-key", alg="RS256", use="sig")
    original_client = httpx.Client

    def handler(request):
        context.requests.append(request)
        if context.http_error:
            return httpx.Response(503, json={"error": "temporary provider failure"})
        if str(request.url) in oauth.TOKEN.values():
            if context.token_error:
                return httpx.Response(200, json={"error": "invalid_grant", "error_description": "upstream-sensitive-description"})
            if request.url.host == "github.com":
                return httpx.Response(200, json={"access_token": "test-github-token", "token_type": "bearer"})
            issued = int(now().timestamp())
            claims = {"iss": "https://accounts.google.com", "aud": "google-client-test", "sub": "google-stable-subject", "email": "new@verified.test", "email_verified": True, "iat": issued, "exp": issued + 300, "nonce": context.nonce, "name": "Verified Founder", **context.claims}
            signer = context.signer if context.algorithm == "RS256" else "test-hmac-secret-with-at-least-thirty-two-bytes"
            encoded = jwt.encode(claims, signer, algorithm=context.algorithm, headers={"kid": "test-key"})
            return httpx.Response(200, json={"id_token": encoded, "access_token": "unused-google-token"})
        if str(request.url) == oauth.GOOGLE_JWKS:
            return httpx.Response(200, json={"keys": [public_key]})
        if request.url.host == "api.github.com":
            assert request.headers["authorization"] == "Bearer test-github-token"
            if request.url.path == "/user":
                return httpx.Response(200, json={"id": context.github_id, "login": "verified-founder", "email": "untrusted-profile@bad.test"})
            if request.url.path == "/user/emails":
                return httpx.Response(200, json=context.emails)
        raise AssertionError("Unexpected provider endpoint")

    monkeypatch.setattr(oauth.httpx, "Client", lambda **kwargs: original_client(transport=httpx.MockTransport(handler), **kwargs))
    return context


def assert_no_new_account(auth):
    assert auth.client.get("/api/v1/auth/me").status_code == 401
    with auth.app.state.session_factory() as db:
        assert db.scalar(select(func.count()).select_from(Founder)) == 1
        assert db.scalar(select(func.count()).select_from(OAuthIdentity)) == 0


def test_start_uses_pkce_bound_cookie_and_public_configuration(auth):
    public = auth.client.get("/api/v1/auth/providers")
    assert all(provider["available"] for provider in public.json()["providers"])
    assert "secret" not in public.text and "client-test" not in public.text
    assert auth.client.get("/api/v1/auth/connections").status_code == 401
    values, response = begin(auth)
    assert values["redirect_uri"] == ORIGIN + "/api/v1/auth/oauth/google/callback"
    assert values["scope"] == "openid email profile" and values["code_challenge_method"] == "S256"
    assert "HttpOnly" in response.headers["set-cookie"] and "SameSite=lax" in response.headers["set-cookie"]
    assert "Max-Age=600" in response.headers["set-cookie"]
    with auth.app.state.session_factory() as db:
        attempt = db.get(OAuthAttempt, token_hash(values["state"]))
        assert attempt.browser_hash == token_hash(values["binding"])
        assert values["code_challenge"] == oauth.code_challenge(attempt.code_verifier)
        assert attempt.code_verifier not in response.text
    assert auth.client.post("/api/v1/auth/oauth/google/start", headers={"Origin": "https://attacker.test"}, json={}).status_code == 403
    assert auth.client.post("/api/v1/auth/oauth/google/start", json={"mode": "connect"}).status_code == 401
    assert auth.client.post("/api/v1/auth/oauth/google/start", json={"return_to": "https://attacker.test"}).status_code == 422


@pytest.mark.parametrize("provider", ["google", "github"])
def test_provider_creates_session_then_returns_to_same_founder(auth, provider_http, provider):
    values, _ = begin(auth, provider)
    provider_http.nonce = values.get("nonce", "")
    response = callback(auth, values, provider)
    assert response.status_code == 303 and response.headers["location"] == ORIGIN + "/"
    assert response.headers["referrer-policy"] == "no-referrer"
    profile = auth.client.get("/api/v1/auth/me").json()
    assert profile["email"] == "new@verified.test" and profile["id"] != auth.founder_id
    assert "password" not in profile and "token" not in response.headers["location"]
    cookies = response.headers.get_list("set-cookie")
    assert any(COOKIE_NAME in cookie and "HttpOnly" in cookie and "SameSite=strict" in cookie for cookie in cookies)
    exchange = parse_qs(provider_http.requests[0].content.decode())
    assert exchange["redirect_uri"] == [values["redirect_uri"]]
    assert oauth.code_challenge(exchange["code_verifier"][0]) == values["code_challenge"]
    with auth.app.state.session_factory() as db:
        assert db.scalar(select(func.count()).select_from(OAuthAttempt)) == 0
    auth.client.post("/api/v1/auth/logout")
    values, _ = begin(auth, provider)
    provider_http.nonce = values.get("nonce", "")
    # Stable provider subject controls identity even when the provider email changes.
    provider_http.claims["email"] = "changed@verified.test"
    provider_http.emails[0]["email"] = "changed@verified.test"
    assert callback(auth, values, provider).headers["location"] == ORIGIN + "/"
    assert auth.client.get("/api/v1/auth/me").json()["id"] == profile["id"]


@pytest.mark.parametrize("problem", ["no_cookie", "wrong_cookie", "wrong_state", "expired", "provider_mixup", "duplicate_state"])
def test_invalid_callbacks_do_not_exchange_codes(auth, provider_http, problem):
    values, _ = begin(auth)
    provider = "google"
    if problem in {"no_cookie", "wrong_cookie"}:
        auth.client.cookies.delete(cookie_name("google"))
        if problem == "wrong_cookie": auth.client.cookies.set(cookie_name("google"), "another-browser")
    if problem == "wrong_state": values["state"] = "wrong-state"
    if problem == "expired":
        with auth.app.state.session_factory() as db:
            db.get(OAuthAttempt, token_hash(values["state"])).expires_at = now() - timedelta(seconds=1)
            db.commit()
    if problem == "provider_mixup":
        provider = "github"
        auth.client.cookies.set(cookie_name("github"), values["binding"])
    if problem == "duplicate_state":
        response = auth.client.get("/api/v1/auth/oauth/google/callback", params=[("state", values["state"]), ("state", "other"), ("code", "one-use-code")])
    else:
        response = callback(auth, values, provider)
    expected = "expired_state" if problem == "expired" else "invalid_state"
    assert response.headers["location"] == ORIGIN + "/?auth_error=" + expected
    assert not provider_http.requests
    assert_no_new_account(auth)


def test_cancelled_and_replayed_callbacks_are_consumed(auth, provider_http):
    values, _ = begin(auth)
    response = callback(auth, values, error="access_denied", error_description="<script>untrusted</script>")
    assert response.headers["location"] == ORIGIN + "/?auth_error=cancelled"
    auth.client.cookies.set(cookie_name("google"), values["binding"])
    assert callback(auth, values).headers["location"].endswith("auth_error=invalid_state")
    assert not provider_http.requests
    assert_no_new_account(auth)


@pytest.mark.parametrize("claims", [
    {"nonce": "wrong-nonce"}, {"aud": "wrong-client"}, {"iss": "https://attacker.test"},
    {"exp": 1}, {"iat": 9999999999}, {"sub": ""}, {"email_verified": False},
    {"email_verified": "true"}, {"email": "not-an-email"}, {"azp": "wrong-client"},
    {"aud": ["google-client-test", "another-client"]},
])
def test_google_rejects_invalid_identity_claims(auth, provider_http, claims):
    values, _ = begin(auth)
    provider_http.nonce = values["nonce"]
    provider_http.claims.update(claims)
    response = callback(auth, values)
    assert "auth_error=" in response.headers["location"]
    assert_no_new_account(auth)


@pytest.mark.parametrize("problem", ["signature", "algorithm", "token_error", "upstream_error"])
def test_bad_signatures_and_upstream_errors_never_authenticate(auth, provider_http, problem):
    values, _ = begin(auth)
    provider_http.nonce = values["nonce"]
    if problem == "signature": provider_http.signer = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    if problem == "algorithm": provider_http.algorithm = "HS256"
    if problem == "token_error": provider_http.token_error = True
    if problem == "upstream_error": provider_http.http_error = True
    response = callback(auth, values)
    expected = "provider_unavailable" if problem == "upstream_error" else "invalid_provider_response"
    assert response.headers["location"] == ORIGIN + "/?auth_error=" + expected
    assert "upstream-sensitive" not in response.text
    assert_no_new_account(auth)


def test_github_requires_verified_email_and_valid_subject(auth, provider_http):
    for emails, subject in [([{"email": "unverified@forge.test", "verified": False}], 2468), ([], 2468), (provider_http.emails, True)]:
        values, _ = begin(auth, "github")
        provider_http.emails, provider_http.github_id = emails, subject
        assert "auth_error=" in callback(auth, values, "github").headers["location"]
        assert_no_new_account(auth)


def test_existing_email_requires_explicit_connection_and_preserves_owner(auth, provider_http):
    values, _ = begin(auth)
    provider_http.nonce = values["nonce"]
    provider_http.claims["email"] = "existing@forge.test"
    assert callback(auth, values).headers["location"].endswith("auth_error=account_exists")
    assert_no_new_account(auth)
    login = auth.client.post("/api/v1/auth/login", json={"email": "existing@forge.test", "password": PASSWORD})
    assert login.status_code == 200
    original_token = auth.client.cookies.get(COOKIE_NAME)
    values, _ = begin(auth, mode="connect")
    provider_http.nonce = values["nonce"]
    # SameSite=Strict product cookies are not sent on the provider's callback.
    auth.client.cookies.delete(COOKIE_NAME)
    response = callback(auth, values)
    assert response.headers["location"] == ORIGIN + "/?auth_connected=google"
    assert auth.client.get("/api/v1/auth/me").json()["id"] == auth.founder_id
    linked = auth.client.get("/api/v1/auth/connections").json()["providers"]
    assert linked[0]["connected"] and linked[0]["email"] == "existing@forge.test"
    with auth.app.state.session_factory() as db:
        assert db.get(Session, token_hash(original_token)) is None
        assert db.scalar(select(func.count()).select_from(Founder)) == 1
    assert auth.client.post("/api/v1/auth/oauth/google/start", json={"mode": "connect"}).status_code == 409
    auth.client.post("/api/v1/auth/logout")
    values, _ = begin(auth)
    provider_http.nonce = values["nonce"]
    callback(auth, values)
    assert auth.client.get("/api/v1/auth/me").json()["id"] == auth.founder_id


def test_logout_revokes_pending_account_connection(auth, provider_http):
    auth.client.post("/api/v1/auth/login", json={"email": "existing@forge.test", "password": PASSWORD})
    values, _ = begin(auth, mode="connect")
    auth.client.post("/api/v1/auth/logout")
    response = callback(auth, values)
    assert response.headers["location"].endswith("auth_error=invalid_state")
    assert not provider_http.requests
    assert_no_new_account(auth)


def test_provider_identity_cannot_move_to_another_founder(auth, provider_http):
    values, _ = begin(auth)
    provider_http.nonce = values["nonce"]
    callback(auth, values)
    new_id = auth.client.get("/api/v1/auth/me").json()["id"]
    auth.client.post("/api/v1/auth/logout")
    auth.client.post("/api/v1/auth/login", json={"email": "existing@forge.test", "password": PASSWORD})
    values, _ = begin(auth, mode="connect")
    provider_http.nonce = values["nonce"]
    assert callback(auth, values).headers["location"].endswith("auth_error=identity_in_use")
    assert auth.client.get("/api/v1/auth/me").json()["id"] == auth.founder_id
    with auth.app.state.session_factory() as db:
        assert db.scalar(select(OAuthIdentity)).founder_id == new_id


def test_concurrent_callbacks_create_exactly_one_account(auth, provider_http):
    values, _ = begin(auth)
    provider_http.nonce = values["nonce"]
    def send(_):
        with TestClient(auth.app, follow_redirects=False) as client:
            client.cookies.set(cookie_name("google"), values["binding"])
            return client.get("/api/v1/auth/oauth/google/callback", params={"state": values["state"], "code": "one-use-code"}).headers["location"]
    with ThreadPoolExecutor(max_workers=2) as pool:
        destinations = list(pool.map(send, range(2)))
    assert sorted(destinations) == sorted([ORIGIN + "/", ORIGIN + "/?auth_error=invalid_state"])
    with auth.app.state.session_factory() as db:
        assert db.scalar(select(func.count()).select_from(Founder)) == 2
        assert db.scalar(select(func.count()).select_from(OAuthIdentity)) == 1
        assert db.scalar(select(func.count()).select_from(Session)) == 1


def test_missing_configuration_rate_limit_and_secure_cookies(auth):
    from pydantic import SecretStr
    auth.settings.google_client_secret = SecretStr("")
    assert auth.client.get("/api/v1/auth/providers").json()["providers"][0]["available"] is False
    assert auth.client.post("/api/v1/auth/oauth/google/start", json={}).status_code == 503
    auth.settings.cookie_secure = True
    response = auth.client.post("/api/v1/auth/oauth/github/start", json={})
    assert "Secure" in response.headers["set-cookie"]
    for _ in range(8): auth.client.post("/api/v1/auth/oauth/github/start", json={})
    assert auth.client.post("/api/v1/auth/oauth/github/start", json={}).status_code == 429


def test_callback_logging_redacts_authorization_codes():
    record = logging.LogRecord("uvicorn.access", logging.INFO, "", 0, '%s - "%s %s HTTP/%s" %d',
        ("127.0.0.1", "GET", "/api/v1/auth/oauth/google/callback?code=private-code&state=private-state", "1.1", 303), None)
    assert CallbackLogFilter().filter(record)
    assert "private-code" not in record.getMessage() and "private-state" not in record.getMessage()


def test_oauth_migration_preserves_existing_founder_and_passport(tmp_path):
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine, inspect, text
    from uuid import uuid4
    from sqlalchemy.orm import Session as DatabaseSession
    from venture_forge.product.core.models import Venture
    from conftest import ROOT
    config = Config(str(ROOT / "alembic.ini"))
    url = f"sqlite:///{(tmp_path / 'oauth_migration_test.sqlite3').as_posix()}"
    config.attributes["database_url"] = url
    command.upgrade(config, "0004")
    engine = create_engine(url)
    assert "oauth_identities" not in inspect(engine).get_table_names()
    with DatabaseSession(engine) as db:
        founder_id = str(uuid4())
        db.execute(text("INSERT INTO founders (id, email, name, password_hash, created_at) VALUES (:id, :email, :name, :password_hash, :created_at)"), {"id": founder_id, "email": "preserved@forge.test", "name": "Preserved Founder", "password_hash": "existing-password-hash", "created_at": now()})
        venture = Venture(owner_id=founder_id, name="Preserved Passport", idea="An existing venture with private founder context.", customer_segment="Existing founders", geography="India")
        db.add(venture); db.flush()
        venture_id = venture.id
        db.commit()
    command.upgrade(config, "head")
    command.check(config)
    with DatabaseSession(engine) as db:
        assert db.get(Founder, founder_id).password_hash == "existing-password-hash"
        assert db.get(Venture, venture_id).name == "Preserved Passport"
    command.downgrade(config, "0004")
    assert "oauth_identities" not in inspect(engine).get_table_names()
    command.upgrade(config, "head")
    with DatabaseSession(engine) as db:
        assert db.get(Venture, venture_id).owner_id == founder_id
    engine.dispose()
