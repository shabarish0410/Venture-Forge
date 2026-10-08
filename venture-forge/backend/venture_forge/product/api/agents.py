from fastapi import Depends, Header
from pydantic import ValidationError
from venture_forge.product.core.models import Activity, now
from venture_forge.product.core.workflow_models import Artifact, Decision
from venture_forge.product.agents.models import AgentRun, Pipeline, Stage, Handoff
from venture_forge.product.agents.registry import REGISTRY, PIPELINES
from venture_forge.product.agents.schemas import AgentRequest, AgentReview, PipelineCreate
from venture_forge.product.core.workflow_schemas import Command
from venture_forge.product.agents.runtime import build_context, current, digest, advance, invalidate, scoped, record_scope
from venture_forge.product.agents.gateway import available
from venture_forge.product.agents.model_router import catalog, select_route, RoutingError
from venture_forge.product.agents.workspace_library import library
from venture_forge.product.agents.workspace_reports import check_references


def safe_run(run):
    from .workflows import encode
    item = encode(run)
    if run.status == "STALE":
        item["context"], item["request"], item["result"] = {}, {}, {"unknowns": ["An input was corrected or withdrawn. Run this specialist again with current records."]}
    return item


def read_agents(session, venture):
    from .workflows import encode
    pipelines = []
    stages = record_scope(session, Stage, venture)
    for p in record_scope(session, Pipeline, venture):
        pipelines.append({**encode(p), "name": PIPELINES[p.template][0], "stages": [encode(s) for s in sorted(stages, key=lambda s: s.position) if s.pipeline_id == p.id]})
    return {"agent_runs": [safe_run(r) for r in record_scope(session, AgentRun, venture)], "pipelines": pipelines, "handoffs": [encode(h) for h in record_scope(session, Handoff, venture)]}


def install_agents(app, db, owner, owned_venture, passport, begin, finish, fail, settings):
    @app.get("/api/v1/agents")
    def agents(founder=Depends(owner)):
        return {"agents": [{"id": s.id, "name": s.name, "workspace": s.workspace, "description": s.description, "output_type": s.output, "tools": s.tools, "receives": s.receives, "sends": s.sends, "parameters_schema": s.schema.model_json_schema(), "model_requirements": s.model_requirements.model_dump(mode="json"), "mvp": library(s.id)} for s in REGISTRY.values()], "templates": [{"id": k, "name": name, "stages": [{"agent_id": a, "dependencies": d} for a, d in stages]} for k, (name, stages) in PIPELINES.items()], "model": {"provider": "hybrid", "configured": available(settings), "policy": settings.model_router_policy, "default_mode": "AUTO", "profiles": catalog(settings)}, "external_actions": False}

    @app.post("/api/v1/ventures/{venture_id}/pipelines", status_code=201)
    def create_pipeline(venture_id: str, body: PipelineCreate, founder=Depends(owner), session=Depends(db), idempotency_key: str | None = Header(default=None)):
        op = f"pipeline.create:{venture_id}"
        venture, payload, prior = begin(session, founder, venture_id, body, idempotency_key, op)
        if prior is not None: return prior
        from venture_forge.product.core.models import Hypothesis
        if not scoped(session, Hypothesis, body.hypothesis_id, venture): fail("NOT_FOUND", "Hypothesis not found.", 404)
        pipeline = Pipeline(venture_id=venture.id, owner_id=founder.id, template=body.template, objective=body.objective, hypothesis_id=body.hypothesis_id)
        session.add(pipeline)
        session.flush()
        for i, (ident, dependencies) in enumerate(PIPELINES[body.template][1]):
            session.add(Stage(venture_id=venture.id, owner_id=founder.id, pipeline_id=pipeline.id, agent_id=ident, position=i, dependencies=dependencies, status="WAITING" if dependencies else "READY"))
        return finish(session, founder, venture, idempotency_key, payload, op, "Founder chose a specialist pipeline with explicit dependencies and review gates.")

    @app.post("/api/v1/ventures/{venture_id}/agent-runs", status_code=202)
    def enqueue(venture_id: str, body: AgentRequest, founder=Depends(owner), session=Depends(db), idempotency_key: str | None = Header(default=None)):
        op = f"agent.run:{venture_id}"
        venture, payload, prior = begin(session, founder, venture_id, body, idempotency_key, op)
        if prior is not None: return prior
        if body.mode == "RULE" and body.budget.max_cost_inr != 0:
            fail("RULE_COST_ZERO", "A deterministic run must have a zero model cost cap.", 422)
        try:
            parameters = REGISTRY[body.agent_id].schema.model_validate(body.parameters).model_dump(mode="json")
            context, fingerprints = build_context(session, venture, body.model_copy(update={"parameters": parameters}))
            if body.supersedes_artifact_id:
                previous = scoped(session, Artifact, body.supersedes_artifact_id, venture)
                previous_run = next((r for r in record_scope(session, AgentRun, venture) if r.artifact_id == body.supersedes_artifact_id), None)
                if not previous or previous.status != "ACCEPTED" or previous.capability != body.agent_id or not previous_run or previous_run.hypothesis_id != body.hypothesis_id:
                    raise ValueError("VERSION_NOT_CURRENT")
                if body.supersedes_artifact_id in fingerprints["artifacts"]:
                    raise ValueError("VERSION_SELF_DEPENDENCY")
            check_references(parameters, context)
            select_route(settings, REGISTRY[body.agent_id].model_requirements, 1024, body.budget.model_dump(), mode=body.mode, data_policy=body.data_policy, allow_processing=body.allow_model_processing, preferred_profile=body.preferred_profile)
        except RoutingError as error:
            messages = {"NO_CAPABLE_MODEL": "No configured profile meets this specialist's reasoning, context, structured-output or tool requirements.", "NO_PRIVACY_COMPATIBLE_MODEL": "No local profile is available. Local-only requests never use a cloud fallback.", "MODEL_COST_CAP": "No suitable model fits this run's cost cap.", "MODEL_PERMISSION_REQUIRED": "Allow processing of this run's scoped context before using a model.", "MODEL_NOT_CONFIGURED": "Configure a model profile and its server-side credentials first.", "PROFILE_UNAVAILABLE": "The requested model profile is unavailable or outside the processing policy."}
            fail(str(error), messages.get(str(error), "Model routing is unavailable."), 422)
        except ValidationError as error:
            fields = ", ".join(".".join(str(x) for x in e["loc"]) for e in error.errors())
            fail("INVALID_PARAMETERS", "Check the specialist inputs: " + fields, 422)
        except ValueError as error:
            code = str(error)
            fail(code, "The chosen records or pipeline dependencies are unavailable, stale or outside this specialist's scope.", 404 if code == "RECORD_NOT_FOUND" else 409)
        request = body.model_dump(mode="json")
        request["parameters"] = parameters
        run = AgentRun(venture_id=venture.id, owner_id=founder.id, agent_id=body.agent_id, objective=body.objective, hypothesis_id=body.hypothesis_id, stage_id=body.stage_id, request=request, context=context, fingerprints=fingerprints, input_revision=venture.revision + 1)
        session.add(run)
        session.flush()
        if body.stage_id:
            stage = scoped(session, Stage, body.stage_id, venture)
            stage.status, stage.run_id = "QUEUED", run.id
        return finish(session, founder, venture, idempotency_key, payload, op, f"{REGISTRY[body.agent_id].name} queued with a scoped context and bounded tools.", lambda: safe_run(run))

    @app.get("/api/v1/ventures/{venture_id}/agent-runs/{run_id}")
    def get_run(venture_id: str, run_id: str, founder=Depends(owner), session=Depends(db)):
        venture = owned_venture(session, founder, venture_id)
        run = scoped(session, AgentRun, run_id, venture)
        if not run: fail("NOT_FOUND", "Specialist run not found.", 404)
        return safe_run(run)

    @app.post("/api/v1/ventures/{venture_id}/agent-runs/{run_id}/review")
    def review(venture_id: str, run_id: str, body: AgentReview, founder=Depends(owner), session=Depends(db), idempotency_key: str | None = Header(default=None)):
        op = f"agent.review:{run_id}"
        venture, payload, prior = begin(session, founder, venture_id, body, idempotency_key, op)
        if prior is not None: return prior
        run = scoped(session, AgentRun, run_id, venture)
        if not run: fail("NOT_FOUND", "Specialist run not found.", 404)
        if run.status != "AWAITING_REVIEW" or body.expected_result_hash != run.result_hash:
            fail("REVIEW_CONFLICT", "The proposal is no longer reviewable or its content changed.", 409)
        if not current(session, run): fail("STALE_CONTEXT", "An input changed. Run the specialist again before review.", 409)
        run.status = "ACCEPTED" if body.choice == "accept" else "REJECTED"
        if body.choice == "accept":
            supersedes = run.request.get("supersedes_artifact_id")
            if supersedes:
                previous = scoped(session, Artifact, supersedes, venture)
                if not previous or previous.status != "ACCEPTED":
                    fail("VERSION_NOT_CURRENT", "The version being replaced changed. Run the revision again.", 409)
                previous.status = "SUPERSEDED"
                for handoff in record_scope(session, Handoff, venture):
                    if handoff.artifact_id == supersedes: handoff.status = "SUPERSEDED"
            artifact = Artifact(venture_id=venture.id, owner_id=founder.id, capability=run.agent_id, title=f"{REGISTRY[run.agent_id].name}: {run.objective[:200]}", inputs=run.request["parameters"], result=run.result, evidence_ids=run.result["evidence_ids"], venture_revision=venture.revision + 1, status="ACCEPTED", formula_version="specialist-v1")
            session.add(artifact)
            session.flush()
            run.artifact_id = artifact.id
            for ident in run.result["handoffs"]:
                session.add(Handoff(venture_id=venture.id, owner_id=founder.id, from_run_id=run.id, to_agent_id=ident, artifact_id=artifact.id))
        session.add(Decision(venture_id=venture.id, owner_id=founder.id, target_id=run.id, target_type="agent_run", choice=body.choice, rationale=body.rationale, result_snapshot=run.result, evidence_ids=run.result["evidence_ids"]))
        if run.stage_id:
            stage = scoped(session, Stage, run.stage_id, venture)
            stage.status, stage.artifact_id = run.status, run.artifact_id
            advance(session, venture, stage.pipeline_id)
        return finish(session, founder, venture, idempotency_key, payload, op, f"Founder {body.choice}ed the exact {REGISTRY[run.agent_id].name} result; reviewed lineage recorded.")

    @app.post("/api/v1/ventures/{venture_id}/agent-runs/{run_id}/cancel")
    def cancel(venture_id: str, run_id: str, body: Command, founder=Depends(owner), session=Depends(db), idempotency_key: str | None = Header(default=None)):
        op = f"agent.cancel:{run_id}"
        venture, payload, prior = begin(session, founder, venture_id, body, idempotency_key, op)
        if prior is not None: return prior
        run = scoped(session, AgentRun, run_id, venture)
        if not run: fail("NOT_FOUND", "Run not found.", 404)
        if run.status not in {"QUEUED", "RUNNING", "AWAITING_REVIEW", "NEEDS_INPUT", "FAILED"}: fail("CANCEL_CONFLICT", "This run is already closed.", 409)
        run.status = "CANCELLED"
        if run.stage_id: scoped(session, Stage, run.stage_id, venture).status = "CANCELLED"
        return finish(session, founder, venture, idempotency_key, payload, op, "Specialist run cancelled. Any late worker result will be discarded.")

