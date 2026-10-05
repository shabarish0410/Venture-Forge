from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from venture_forge.product.api.app import create_app
from venture_forge.product.core.models import Hypothesis, Session, now
from venture_forge.shared.config import Settings
from venture_forge.shared.auth import COOKIE_NAME, token_hash
from conftest import PASSWORD, ORIGIN

VENTURE = {"name":"Fixture venture", "idea":"Help independent founders investigate real customer problems.", "customer_segment":"Independent founders", "geography":"Bengaluru", "first_hypothesis":"Independent founders struggle to find their first five interview participants."}


def create(client, key="create-one"):
    return client.post("/api/v1/ventures", json=VENTURE, headers={"Idempotency-Key":key})


def test_authentication_origin_and_logout(client):
    assert client.get("/api/v1/ventures").status_code == 401
    assert client.post("/api/v1/auth/login", json={"email":"one@test.local","password":"wrong"}).status_code == 401
    assert client.post("/api/v1/auth/login", json={"email":"one@test.local","password":PASSWORD}, headers={"Origin":"https://untrusted.example"}).status_code == 403
    login = client.post("/api/v1/auth/login", json={"email":"one@test.local","password":PASSWORD})
    assert login.status_code == 200
    assert "HttpOnly" in login.headers["set-cookie"] and "SameSite=strict" in login.headers["set-cookie"]
    token = client.cookies.get(COOKIE_NAME)
    assert "password" not in login.text
    assert client.post("/api/v1/auth/logout").status_code == 204
    client.cookies.set(COOKIE_NAME, token)
    assert client.get("/api/v1/auth/me").status_code == 401


def test_expired_session_rejected(authenticated, application):
    with application.state.session_factory() as db:
        session = db.get(Session, token_hash(authenticated.cookies.get(COOKIE_NAME)))
        session.expires_at = now() - timedelta(seconds=1)
        db.commit()
    assert authenticated.get("/api/v1/ventures").status_code == 401


def test_founder_assumption_persists_after_app_restart(authenticated, database_url):
    result = create(authenticated)
    assert result.status_code == 201
    passport = result.json()
    assert passport["hypotheses"][0]["status"] == "unvalidated"
    assert passport["hypotheses"][0]["origin"] == "founder_asserted"
    assert passport["evidence_count"] == passport["decision_count"] == 0
    fresh = create_app(Settings(database_url=database_url, app_origin=ORIGIN))
    with TestClient(fresh, headers={"Origin":ORIGIN}) as restarted:
        restarted.cookies.update(authenticated.cookies)
        saved = restarted.get(f'/api/v1/ventures/{passport["venture"]["id"]}/passport')
        assert saved.status_code == 200
        assert saved.json() == passport
    fresh.state.engine.dispose()


def test_wrong_owner_reads_and_writes_denied(authenticated, application):
    venture = create(authenticated).json()["venture"]
    with TestClient(application, headers={"Origin":ORIGIN}) as other:
        other.post("/api/v1/auth/login", json={"email":"two@test.local", "password":PASSWORD})
        assert other.get("/api/v1/ventures").json() == {"ventures":[]}
        assert other.get(f'/api/v1/ventures/{venture["id"]}/passport').status_code == 404
        assert other.post(f'/api/v1/ventures/{venture["id"]}/hypotheses', headers={"Idempotency-Key":"wrong-owner"}, json={"statement":"A sufficiently long malicious statement.", "category":"problem", "expected_revision":1}).status_code == 404


def test_database_rejects_cross_owner_relationship(authenticated, application):
    venture = create(authenticated).json()["venture"]
    with application.state.session_factory() as db:
        db.add(Hypothesis(venture_id=venture["id"], owner_id="00000000-0000-0000-0000-000000000002", statement="Wrong-owner relationship.", category="problem"))
        with pytest.raises(IntegrityError):
            db.commit()


def test_idempotency_and_one_venture_limit(authenticated):
    first = create(authenticated)
    assert create(authenticated).json() == first.json()
    changed = {**VENTURE,"name":"A changed name"}
    assert authenticated.post("/api/v1/ventures", json=changed, headers={"Idempotency-Key":"create-one"}).status_code == 409
    assert create(authenticated,"different-key").status_code == 409
    assert authenticated.post("/api/v1/ventures", json=VENTURE).status_code == 400


def test_revision_conflict_and_transactional_history(authenticated):
    venture = create(authenticated).json()["venture"]
    url = f'/api/v1/ventures/{venture["id"]}/hypotheses'
    body = {"statement":"Founders will pay for an evidence-backed discovery workflow.","category":"pricing","expected_revision":1}
    added = authenticated.post(url,json=body,headers={"Idempotency-Key":"add-one"})
    assert added.status_code == 201
    result = added.json()
    assert result["venture"]["revision"] == 2
    assert len(result["hypotheses"]) == len(result["activity"]) == 2
    assert authenticated.post(url,json=body,headers={"Idempotency-Key":"add-one"}).json() == result
    assert authenticated.post(url,json=body,headers={"Idempotency-Key":"stale-update"}).status_code == 409


def test_cannot_promote_assumption_or_assign_owner(authenticated):
    assert authenticated.post("/api/v1/ventures",json={**VENTURE,"owner_id":"another"},headers={"Idempotency-Key":"owner-injection"}).status_code == 422
    venture = create(authenticated).json()["venture"]
    body = {"statement":"An assertion the model claims is supported.","category":"problem","expected_revision":1,"status":"supported"}
    assert authenticated.post(f'/api/v1/ventures/{venture["id"]}/hypotheses',json=body,headers={"Idempotency-Key":"promotion"}).status_code == 422


def test_company_realm_unavailable_to_product_session(authenticated):
    assert authenticated.get("/api/company/v1/brief").status_code == 403
    assert authenticated.post("/api/company/v1/actions",json={}).status_code == 403


def test_concurrent_replay_creates_one_hypothesis(authenticated, application):
    venture = create(authenticated).json()["venture"]
    token = authenticated.cookies.get(COOKIE_NAME)
    def send():
        with TestClient(application, headers={"Origin":ORIGIN}) as parallel:
            parallel.cookies.set(COOKIE_NAME,token)
            return parallel.post(f'/api/v1/ventures/{venture["id"]}/hypotheses',headers={"Idempotency-Key":"concurrent"},json={"statement":"Founders want one clear assumption to investigate.","category":"customer","expected_revision":1})
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _:send(),range(2)))
    assert [result.status_code for result in results] == [201,201]
    assert results[0].json() == results[1].json()
    assert len(results[0].json()["hypotheses"]) == 2
