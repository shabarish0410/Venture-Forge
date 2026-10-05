"""Behavioral contracts for hybrid routing, privacy, provider transports and provenance."""
import json
from datetime import date
import httpx
import pytest
from pydantic import ValidationError
from fastapi.testclient import TestClient
from venture_forge.shared.config import Settings
from venture_forge.shared.model_config import ModelProfile
from venture_forge.product.agents.registry import REGISTRY
from venture_forge.product.agents.model_router import select_route, RoutingError, catalog
from venture_forge.product.agents.gateway import draft, GatewayError
from venture_forge.product.agents.provider_adapters import ADAPTERS, ProviderResult
from venture_forge.product.agents.runtime import execute_one
from venture_forge.product.api.app import create_app
from test_evidence_cycle import cycle, post, receipt
from test_specialists import parameters, refresh, enqueue
from conftest import ORIGIN, PASSWORD


def profile(name, provider="openai", **values):
    return ModelProfile(name=name, provider=provider, model_id="operator-chosen-model", reasoning="high", context_tokens=128000, tool_calling=True, input_inr_per_million=1, output_inr_per_million=2, **values)


def settings(*items):
    return Settings(_env_file=None, database_url="sqlite://", model_router_policy="hybrid", model_profiles=list(items), model_profiles_file=None, ollama_url="http://127.0.0.1:11434", openai_api_key="private-openai-test-key", anthropic_api_key="private-anthropic-test-key", gemini_api_key="private-gemini-test-key")


def route(config, agent="research", **values):
    return select_route(config, REGISTRY[agent].model_requirements, 5000, {"max_cost_inr": 1}, allow_processing=True, **values)


def test_complex_tasks_prefer_capable_cloud_and_standard_tasks_use_cheapest():
    cloud = profile("cloud", "anthropic")
    local = profile("private-local", "ollama").model_copy(update={"input_inr_per_million": 0, "output_inr_per_million": 0})
    small = profile("small").model_copy(update={"reasoning": "standard", "input_inr_per_million": 0.1, "output_inr_per_million": 0.2})
    config = settings(local, cloud, small)
    decision = route(config)
    assert decision.profile.name == "cloud" and decision.reason == "CLOUD_COMPLEX_TASK"
    assert route(config, "finance").profile.name == "private-local"
    assert route(settings(cloud, small), "home").profile.name == "small"
    assert route(config, preferred_profile="private-local").profile.name == "private-local"
    assert route(config, data_policy="local_only").profile.provider == "ollama"
    assert all(s.model_requirements for s in REGISTRY.values())
    assert all("provider" not in s.model_requirements.model_dump() for s in REGISTRY.values())


@pytest.mark.parametrize("override", [{"reasoning": "standard"}, {"context_tokens": 16000}, {"tool_calling": False}, {"structured_outputs": False}, {"max_output_tokens": 1024}])
def test_unsuitable_profiles_are_rejected_instead_of_degrading_requirements(override):
    config = settings(profile("unsuitable").model_copy(update=override))
    with pytest.raises(RoutingError, match="NO_CAPABLE_MODEL"): route(config)


def test_privacy_cost_disabled_and_missing_credentials_fail_closed():
    config = settings(profile("cloud"))
    with pytest.raises(RoutingError, match="NO_PRIVACY_COMPATIBLE_MODEL"): route(config, data_policy="local_only")
    with pytest.raises(RoutingError, match="MODEL_PERMISSION_REQUIRED"):
        select_route(config, REGISTRY["research"].model_requirements, 5000, {"max_cost_inr": 1}, allow_processing=False)
    with pytest.raises(RoutingError, match="MODEL_COST_CAP"):
        select_route(config, REGISTRY["research"].model_requirements, 5000, {"max_cost_inr": 0}, allow_processing=True)
    assert route(config, mode="RULE").profile is None
    config.model_router_policy = "disabled"
    assert route(config).reason == "NO_MODEL_CONFIGURED"
    with pytest.raises(RoutingError, match="MODEL_NOT_CONFIGURED"): route(config, mode="MODEL")
    config = settings(profile("cloud")); config.openai_api_key = type(config.openai_api_key)("")
    assert not catalog(config)[0]["ready"]
    assert route(config).reason == "NO_MODEL_CONFIGURED"
    with pytest.raises(ValidationError): settings(profile("same"), profile("same", "gemini"))


def test_large_context_routes_to_larger_profile_and_cost_cap_is_checked_before_call():
    normal = profile("normal").model_copy(update={"context_tokens": 64000})
    large = profile("large").model_copy(update={"context_tokens": 256000, "input_inr_per_million": 2})
    decision = select_route(settings(normal, large), REGISTRY["research"].model_requirements, 100000, {"max_cost_inr": 1}, allow_processing=True)
    assert decision.profile.name == "large"
    with pytest.raises(RoutingError, match="NO_CAPABLE_MODEL"):
        select_route(settings(normal), REGISTRY["research"].model_requirements, 100000, {"max_cost_inr": 1}, allow_processing=True)


def test_profile_file_loading_and_invalid_file_errors_do_not_expose_contents(tmp_path):
    source = tmp_path / "models.json"
    source.write_text(json.dumps([profile("configured", "gemini").model_dump()]), encoding="utf-8")
    config = Settings(_env_file=None, database_url="sqlite://", model_profiles=[], model_profiles_file=str(source))
    assert config.model_profiles[0].name == "configured"
    with pytest.raises(ValidationError, match="Use MODEL_PROFILES or MODEL_PROFILES_FILE"):
        Settings(_env_file=None, database_url="sqlite://", model_profiles=[profile("other")], model_profiles_file=str(source))
    source.write_text('{"accidentally-pasted-key":"private-file-secret"}', encoding="utf-8")
    with pytest.raises(ValidationError, match="Invalid model profile file") as failure:
        Settings(_env_file=None, database_url="sqlite://", model_profiles=[], model_profiles_file=str(source))
    assert "private-file-secret" not in str(failure.value)


def test_local_profiles_reject_non_loopback_and_credential_urls():
    config = settings(profile("local", "ollama"))
    for address in ("https://remote.example", "http://private-key@127.0.0.1:11434", "http://127.0.0.1:11434?key=private-key"):
        config.ollama_url = address
        assert not catalog(config)[0]["ready"]
        assert "private-key" not in json.dumps(catalog(config))
        with pytest.raises(RoutingError, match="MODEL_NOT_CONFIGURED"):
            route(config, mode="MODEL", data_policy="local_only")


def test_model_step_cap_is_checked_before_any_provider_request():
    calls = []
    def handler(request):
        calls.append(request)
        raise AssertionError("The model must not be called without an available step")
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(GatewayError, match="STEP_CAP") as failure:
            draft(settings(profile("cloud")), {"evidence_ids": [], "data": {}}, {"max_cost_inr": 1, "max_seconds": 10}, client, requirements=REGISTRY["finance"].model_requirements, remaining_steps=0)
    assert not calls and failure.value.usage is None


def test_auto_without_profiles_needs_only_deterministic_tool_steps(cycle):
    client, app, p = cycle
    count = len(REGISTRY["home"].tools)
    queued = enqueue(client, p, "home", budget={"max_steps": count})
    assert execute_one(app.state.session_factory, settings())
    run = next(r for r in refresh(client, p)["agent_runs"] if r["id"] == queued["id"])
    assert run["status"] == "AWAITING_REVIEW" and len(run["trace"]) == count
    assert run["cost_inr"] == 0 and run["trace"][0]["route"]["reason"] == "NO_MODEL_CONFIGURED"


def response_body(provider, analysis, status="COMPLETE"):
    text = json.dumps(analysis)
    if provider == "openai": return {"status": "completed" if status == "COMPLETE" else "incomplete", "output": [{"type": "message", "content": [{"type": "output_text", "text": text}]}], "usage": {"input_tokens": 100, "output_tokens": 50}}
    if provider == "anthropic": return {"stop_reason": "end_turn" if status == "COMPLETE" else "refusal", "content": [{"type": "text", "text": text}], "usage": {"input_tokens": 100, "output_tokens": 50}}
    if provider == "gemini": return {"candidates": [{"finishReason": "STOP" if status == "COMPLETE" else "SAFETY", "content": {"parts": [{"text": text}]}}], "usageMetadata": {"promptTokenCount": 100, "candidatesTokenCount": 50}}
    return {"done": True, "done_reason": "stop" if status == "COMPLETE" else "length", "message": {"content": text}, "prompt_eval_count": 100, "eval_count": 50}


@pytest.mark.parametrize("provider", ["openai", "anthropic", "gemini", "ollama"])
def test_provider_adapters_normalize_structured_synthesis_quotes_and_usage(provider):
    config = settings(profile("chosen", provider))
    content = "The customer declined the paid pilot and continued using the manual workflow."
    result = {"evidence_ids": ["receipt-1"], "data": {"source_registry": [{"source_id": "receipt-1", "excerpt": content, "locator": "Note 01"}]}}
    analysis = {"explanation": "The available source reports a contrary outcome; further evidence is required.", "synthesis": "A declined pilot is not purchase evidence.", "hypothesis_assessment": "This observation challenges the proposed demand hypothesis.", "questions": ["What caused the refusal?"], "evidence_ids": ["receipt-1"], "claims": [{"statement": "The customer declined the paid pilot.", "source_id": "receipt-1", "quote": "The customer declined the paid pilot", "locator": "Note 01"}], "query_suggestions": ["manual workflow switching barriers"]}
    calls = []
    def handler(request):
        calls.append(request)
        payload = json.loads(request.content)
        assert "tools" not in payload  # Domain execution stays in the bounded server workflow.
        if provider == "openai": assert payload["text"]["format"]["strict"] and payload["store"] is False
        if provider == "anthropic": assert payload["output_config"]["format"]["type"] == "json_schema"
        if provider == "gemini": assert "responseJsonSchema" in payload["generationConfig"] and "key=" not in str(request.url)
        return httpx.Response(200, json=response_body(provider, analysis))
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        output, usage = draft(config, result, {"max_cost_inr": 1, "max_seconds": 10}, client, requirements=REGISTRY["research"].model_requirements)
        assert output["claims"][0]["quote"] in content
        assert usage["cost_inr"] == pytest.approx(0.0002)
        assert usage["route"]["provider"] == provider
        assert usage["cost_status"] == "provider_reported"
        assert not any(secret in json.dumps(usage) for secret in ["private-openai-test-key", "private-anthropic-test-key", "private-gemini-test-key"])
        analysis["claims"][0]["quote"] = "The customer bought a paid pilot"
        with pytest.raises(GatewayError, match="MODEL_UNSUPPORTED_QUOTE") as failure:
            draft(config, result, {"max_cost_inr": 1, "max_seconds": 10}, client, requirements=REGISTRY["research"].model_requirements)
        assert failure.value.usage["cost_inr"] > 0
    assert len(calls) == 2


@pytest.mark.parametrize("provider", ["openai", "anthropic", "gemini", "ollama"])
def test_refusals_and_transport_failures_keep_cost_accounting_without_retry(provider):
    config = settings(profile("chosen", provider))
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(200, json=response_body(provider, {}, "INCOMPLETE"))
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(GatewayError) as failure:
            draft(config, {"evidence_ids": [], "data": {}}, {"max_cost_inr": 1, "max_seconds": 10}, client)
    assert failure.value.usage["cost_status"] == "provider_reported" and len(calls) == 1
    def unavailable(request):
        raise httpx.ReadTimeout("Provider detail with private-secret must not be persisted")
    with httpx.Client(transport=httpx.MockTransport(unavailable)) as client:
        with pytest.raises(GatewayError, match="MODEL_INVALID_OR_UNAVAILABLE") as failure:
            draft(config, {"evidence_ids": [], "data": {}}, {"max_cost_inr": 1, "max_seconds": 10}, client)
    assert "private-secret" not in str(failure.value)
    assert failure.value.usage["cost_status"] == "reserved_estimate_usage_unknown"


@pytest.mark.parametrize("agent,removed,code", [
    ("research", "synthesis", "MODEL_ANALYSIS_INCOMPLETE"),
    ("research", "hypothesis_assessment", "MODEL_ANALYSIS_INCOMPLETE"),
    ("research", "claims", "MODEL_ANALYSIS_UNGROUNDED"),
    ("model", "hypothesis_assessment", "MODEL_ANALYSIS_INCOMPLETE"),
])
def test_task_contract_rejects_generic_or_ungrounded_analysis(agent, removed, code):
    content = "The participant declined the pilot offer and kept the manual workflow."
    result = {"evidence_ids": ["source-1"], "data": {"source_registry": [{"source_id": "source-1", "excerpt": content, "locator": "Note 01"}]}}
    analysis = {"explanation": "The original report challenges the demand assumption.", "synthesis": "A declined offer leaves demand unestablished.", "hypothesis_assessment": "The observation challenges demand; investigate the reason for refusal.", "questions": [], "evidence_ids": ["source-1"], "claims": [{"statement": "The participant declined the pilot offer.", "source_id": "source-1", "locator": "Note 01", "quote": "The participant declined the pilot offer"}]}
    analysis.pop(removed)
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(200, json=response_body("openai", analysis))
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(GatewayError, match=code) as failure:
            draft(settings(profile("cloud")), result, {"max_cost_inr": 1, "max_seconds": 10}, client, requirements=REGISTRY[agent].model_requirements)
    assert len(calls) == 1 and failure.value.usage["cost_inr"] == pytest.approx(0.0002)
    assert failure.value.usage["analysis_policy"] == "synthesis-first-v1"


def test_synthesis_without_original_text_keeps_claims_empty():
    result = {"evidence_ids": ["source-1"], "data": {}}
    context = {"hypothesis": "Founders will commit to a pilot.", "evidence": [{"id": "source-1", "content": "[Scoped receipt metadata; original text not requested]", "locator": "Note 01"}]}
    analysis = {"explanation": "The original evidence is unavailable in this scoped context.", "synthesis": "Only receipt metadata is supplied; no source findings can be established.", "hypothesis_assessment": "The hypothesis needs original observations before a demand assessment.", "questions": ["What did the original participant report?"], "evidence_ids": ["source-1"], "claims": []}
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, json=response_body("anthropic", analysis)))) as client:
        output, _ = draft(settings(profile("cloud", "anthropic")), result, {"max_cost_inr": 1, "max_seconds": 10}, client, requirements=REGISTRY["passport"].model_requirements, context=context)
    assert not output["claims"] and "metadata" in output["synthesis"]


def test_finance_model_cannot_return_replacement_calculations():
    analysis = {"explanation": "Review the authoritative scenario before making a financial decision.", "questions": [], "evidence_ids": [], "financials": {"cac_inr": "0.00", "gross_margin_percent": "100.00"}}
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, json=response_body("openai", analysis)))) as client:
        with pytest.raises(GatewayError, match="MODEL_INVALID_OR_UNAVAILABLE") as failure:
            draft(settings(profile("cloud")), {"evidence_ids": [], "data": {"financials": {"cac_inr": "100.00"}}}, {"max_cost_inr": 1, "max_seconds": 10}, client, requirements=REGISTRY["finance"].model_requirements)
    assert failure.value.usage["cost_inr"] > 0


def test_research_model_requires_synthesis_and_review_without_validating_hypothesis(cycle, monkeypatch):
    old_client, old_app, p = cycle
    p = receipt(old_client, p, relation="contradicts", content="The participant declined the paid pilot and continued the manual workflow.")
    source = p["evidence"][0]
    config = settings(profile("research-cloud", "gemini"))
    config.database_url, config.app_origin = str(old_app.state.engine.url), ORIGIN
    app = create_app(config)
    calls = []
    def model_call(picked, cfg, instructions, payload, schema, cap, client):
        data = json.loads(payload)
        calls.append(data)
        analysis = {"explanation": "The source reports a contrary outcome; demand remains an unverified assumption.", "questions": ["Why was the offer declined?"], "evidence_ids": [source["id"]]}
        if len(calls) > 1:
            analysis.update(synthesis="The participant declined the offer and continued using the manual workflow.", hypothesis_assessment="This contradicts the pilot-commitment hypothesis. Test the switching barrier with another independent participant.", claims=[{"statement": "The participant declined the paid pilot.", "source_id": source["id"], "locator": source["locator"], "quote": "The participant declined the paid pilot"}])
        return ProviderResult(json.dumps(analysis), 100, 50, "COMPLETE")
    monkeypatch.setitem(ADAPTERS, "gemini", model_call)
    with TestClient(app, headers={"Origin": ORIGIN}) as client:
        assert client.post("/api/v1/auth/login", json={"email": "cycle@test.local", "password": PASSWORD}).status_code == 200
        values = {"agent_id": "research", "objective": "Synthesize the contrary source and assess the pilot-commitment hypothesis.", "hypothesis_id": p["hypotheses"][0]["id"], "evidence_ids": [source["id"]], "allow_model_processing": True, "budget": {"max_cost_inr": 1}}
        queued = post(client, p, "/agent-runs", values, expected=202)
        assert execute_one(app.state.session_factory, config)
        p = refresh(client, p)
        failed = next(r for r in p["agent_runs"] if r["id"] == queued["id"])
        assert failed["status"] == "FAILED" and failed["error_code"] == "MODEL_ANALYSIS_INCOMPLETE"
        assert failed["cost_inr"] > 0 and not failed["artifact_id"] and not p["handoffs"]
        queued = post(client, p, "/agent-runs", values, expected=202)
        assert execute_one(app.state.session_factory, config)
        p = refresh(client, p)
        run = next(r for r in p["agent_runs"] if r["id"] == queued["id"])
        assert run["status"] == "AWAITING_REVIEW" and not run["artifact_id"]
        assistance = run["result"]["data"]["model_assistance"]
        assert assistance["status"] == "MODEL_INFERENCE" and assistance["claims"][0]["quote"] in source["content"]
        assert calls[-1]["hypothesis"] == p["hypotheses"][0]["statement"] and calls[-1]["sources"][0]["id"] == source["id"]
        p = post(client, p, f"/agent-runs/{run['id']}/review", {"choice": "accept", "rationale": "Retain the contrary finding and run a follow-up test before claiming demand.", "expected_result_hash": run["result_hash"]}, expected=200)
        assert p["hypotheses"][0]["status"] == "unvalidated" and p["completed_cycles"] == 0
        assert len(calls) == 2 and p["artifacts"][-1]["status"] == "ACCEPTED"
    app.state.engine.dispose()


def test_router_in_api_and_worker_keeps_arithmetic_and_passport_review_in_code(cycle, monkeypatch):
    old_client, _, p = cycle
    p = receipt(old_client, p)
    config = settings(profile("reasoning-cloud", "anthropic"))
    config.database_url = str(cycle[1].state.engine.url)
    config.app_origin = ORIGIN
    app = create_app(config)
    called = []
    def model_call(picked, cfg, instructions, payload, schema, cap, client):
        called.append((picked, json.loads(payload)))
        analysis = {"explanation": "Costs and collections are assumptions; review the authoritative financial tool output.", "questions": ["Which cost is backed by an actual receipt?"], "evidence_ids": [p["evidence"][0]["id"]]}
        return ProviderResult(json.dumps(analysis), 100, 50, "COMPLETE")
    monkeypatch.setitem(ADAPTERS, "anthropic", model_call)
    with TestClient(app, headers={"Origin": ORIGIN}) as client:
        assert client.post("/api/v1/auth/login", json={"email": "cycle@test.local", "password": PASSWORD}).status_code == 200
        public = client.get("/api/v1/agents").json()
        assert public["model"]["default_mode"] == "AUTO" and public["model"]["configured"]
        assert "private-anthropic-test-key" not in json.dumps(public)
        values = {"agent_id": "finance", "objective": "Explain this planning scenario without replacing deterministic arithmetic.", "hypothesis_id": p["hypotheses"][0]["id"], "parameters": {**parameters("finance", None), "acquisition_spend": "500", "new_customers": 5, "average_revenue_per_customer": "100", "customer_lifetime_periods": "12"}, "evidence_ids": [p["evidence"][0]["id"]], "budget": {"max_cost_inr": 1}}
        post(client, p, "/agent-runs", values, expected=422)
        post(client, p, "/agent-runs", {**values, "allow_model_processing": True, "data_policy": "local_only"}, expected=422)
        queued = post(client, p, "/agent-runs", {**values, "allow_model_processing": True}, expected=202)
        assert execute_one(app.state.session_factory, config)
        p = refresh(client, p)
        run = p["agent_runs"][-1]
        assert run["status"] == "AWAITING_REVIEW" and run["result"]["mode"] == "MODEL"
        assert not run["artifact_id"] and not p["handoffs"]
        assert run["result"]["data"]["financials"]["gross_margin_percent"] == "60.00"
        assert run["result"]["data"]["financials"]["cac_inr"] == "100.00" and run["result"]["data"]["financials"]["ltv_gross_profit_inr"] == "720.00"
        assert called[0][1]["tool_result"]["data"]["financials"] == run["result"]["data"]["financials"]
        assert run["trace"][-1]["route"]["provider"] == "anthropic"
        assert "Participant discussed" not in json.dumps(called[0][1])
        p = post(client, p, f"/agent-runs/{queued['id']}/review", {"choice": "accept", "rationale": "Accept the deterministic scenario and investigate the model's questions.", "expected_result_hash": run["result_hash"]}, expected=200)
        assert p["artifacts"][-1]["status"] == "ACCEPTED"
    app.state.engine.dispose()
