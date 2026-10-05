import hashlib
import json
import time
from datetime import timezone
from sqlalchemy import select, update
from pydantic import ValidationError
from venture_forge.product.core.models import Venture, Hypothesis, now
from venture_forge.product.core.workflow_models import Receipt, Artifact, Experiment, Observation
from .models import AgentRun, Stage, Pipeline, Handoff
from .registry import REGISTRY
from .schemas import Result
from .specialists import execute
from .gateway import draft, GatewayError
from .model_router import Route


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str, separators=(",", ":")).encode()).hexdigest()


def scoped(session, model, ident, venture):
    return session.scalar(select(model).where(model.id == ident, model.venture_id == venture.id, model.owner_id == venture.owner_id))


def record_scope(session, model, venture):
    return session.scalars(select(model).where(model.venture_id == venture.id, model.owner_id == venture.owner_id).order_by(model.created_at)).all()


def build_context(session, venture, body):
    from venture_forge.product.api.workflows import encode, experiment_result
    spec = REGISTRY[body.agent_id]
    artifact_ids = list(body.artifact_ids)
    if body.stage_id:
        stage = scoped(session, Stage, body.stage_id, venture)
        if not stage or stage.status not in {"READY", "NEEDS_INPUT", "FAILED", "CANCELLED", "STALE", "REJECTED"}: raise ValueError("STAGE_NOT_READY")
        pipeline = scoped(session, Pipeline, stage.pipeline_id, venture)
        if stage.agent_id != body.agent_id or pipeline.hypothesis_id != body.hypothesis_id: raise ValueError("STAGE_SCOPE")
        for upstream in record_scope(session, Stage, venture):
            if upstream.pipeline_id == stage.pipeline_id and upstream.agent_id in stage.dependencies:
                if upstream.status != "ACCEPTED" or not upstream.artifact_id: raise ValueError("DEPENDENCY_NOT_ACCEPTED")
                artifact_ids.append(upstream.artifact_id)
    artifact_ids = list(dict.fromkeys(artifact_ids))
    artifacts, evidence_ids = [], list(body.evidence_ids)
    for ident in artifact_ids:
        item = scoped(session, Artifact, ident, venture)
        if not item: raise ValueError("RECORD_NOT_FOUND")
        if item.status != "ACCEPTED": raise ValueError("ARTIFACT_NOT_ACCEPTED")
        if item.capability not in spec.receives and body.agent_id != "passport":
            raise ValueError("ARTIFACT_NOT_ALLOWED")
        evidence_ids.extend(item.evidence_ids)
        artifacts.append({"id": item.id, "capability": item.capability, "inputs": item.inputs, "result": item.result, "evidence_ids": item.evidence_ids, "hash": digest({"inputs": item.inputs, "result": item.result})})
    experiments = []
    receipts = record_scope(session, Receipt, venture)
    for ident in body.experiment_ids:
        item = scoped(session, Experiment, ident, venture)
        if not item or item.hypothesis_id != body.hypothesis_id: raise ValueError("RECORD_NOT_FOUND")
        if body.agent_id not in {"experiment", "investor", "passport"}: raise ValueError("EXPERIMENT_NOT_ALLOWED")
        observations = [o for o in record_scope(session, Observation, venture) if o.experiment_id == item.id]
        evidence_ids.extend(o.receipt_id for o in observations)
        experiments.append({"id": item.id, "protocol": item.protocol, "protocol_hash": item.protocol_hash, "result": experiment_result(item, observations, receipts), "observation_hash": digest([encode(o) for o in observations])})
    evidence_ids = list(dict.fromkeys(evidence_ids))
    if len(evidence_ids) > 100: raise ValueError("CONTEXT_TOO_LARGE")
    evidence = []
    for ident in evidence_ids:
        item = scoped(session, Receipt, ident, venture)
        if not item: raise ValueError("RECORD_NOT_FOUND")
        if item.withdrawn: raise ValueError("SOURCE_WITHDRAWN")
        if item.hypothesis_id != body.hypothesis_id: raise ValueError("HYPOTHESIS_SCOPE")
        evidence.append(encode(item))
    # Economics never receives raw interview text; exact provenance still travels with the numbers.
    full_source_agents = {"research", "customer", "competitor", "ecosystem", "passport"}
    if body.agent_id not in full_source_agents:
        def narrow(value):
            if isinstance(value, dict):
                return {k: ("[Original source text omitted]" if k in {"excerpt", "notes", "statement", "content", "answer"} else narrow(v)) for k, v in value.items()}
            if isinstance(value, list): return [narrow(v) for v in value]
            return value
        # Preserve the original artifact fingerprint, while passing only its relevant derived fields.
        for item in artifacts:
            item["result"], item["inputs"] = narrow(item["result"]), narrow(item["inputs"])
    for item in evidence:
        if body.agent_id not in full_source_agents: item["content"] = "[Scoped receipt metadata; original text not requested]"
        else: item["content"] = item["content"][:4000]
    fields = ["idea", "customer_segment", "geography"] if body.agent_id == "home" else ["customer_segment", "geography"]
    hypothesis = scoped(session, Hypothesis, body.hypothesis_id, venture)
    if not hypothesis: raise ValueError("RECORD_NOT_FOUND")
    context = {"concept": {k: getattr(venture, k) for k in fields}, "hypothesis": hypothesis.statement, "objective": body.objective, "evidence": evidence, "artifacts": artifacts, "experiments": experiments}
    fingerprints = {"concept": digest({"idea": venture.idea, "customer_segment": venture.customer_segment, "geography": venture.geography}), "hypothesis": digest(hypothesis.statement), "evidence": {e["id"]: e["content_hash"] for e in evidence}, "artifacts": {a["id"]: a["hash"] for a in artifacts}, "experiments": {e["id"]: digest({"protocol_hash": e["protocol_hash"], "observations": e["observation_hash"]}) for e in experiments}}
    return context, fingerprints


def current(session, run):
    from venture_forge.product.api.workflows import encode
    venture = session.scalar(select(Venture).where(Venture.id == run.venture_id, Venture.owner_id == run.owner_id))
    if not venture: return False
    f = run.fingerprints
    if digest({"idea": venture.idea, "customer_segment": venture.customer_segment, "geography": venture.geography}) != f["concept"]: return False
    h = scoped(session, Hypothesis, run.hypothesis_id, venture)
    if not h or digest(h.statement) != f["hypothesis"]: return False
    for ident, expected in f["evidence"].items():
        row = scoped(session, Receipt, ident, venture)
        if not row or row.withdrawn or row.content_hash != expected: return False
    for ident, expected in f["artifacts"].items():
        row = scoped(session, Artifact, ident, venture)
        if not row or row.status != "ACCEPTED" or digest({"inputs": row.inputs, "result": row.result}) != expected: return False
    for ident, expected in f["experiments"].items():
        row = scoped(session, Experiment, ident, venture)
        observations = [o for o in record_scope(session, Observation, venture) if o.experiment_id == ident]
        if not row or digest({"protocol_hash": row.protocol_hash, "observations": digest([encode(o) for o in observations])}) != expected: return False
    return True


def advance(session, venture, pipeline_id):
    stages = [s for s in record_scope(session, Stage, venture) if s.pipeline_id == pipeline_id]
    states = {s.agent_id: s.status for s in stages}
    for stage in stages:
        if stage.status == "WAITING" and all(states.get(k) == "ACCEPTED" for k in stage.dependencies): stage.status = "READY"
    pipeline = scoped(session, Pipeline, pipeline_id, venture)
    pipeline.status = "COMPLETED" if all(s.status == "ACCEPTED" for s in stages) else "BLOCKED" if any(s.status in {"REJECTED", "STALE"} for s in stages) else "ACTIVE"


def invalidate(session, venture):
    """Propagate changed source/concept/accepted-output versions transitively."""
    from venture_forge.product.core.workflow_models import Decision
    changed = True
    while changed:
        changed = False
        for run in record_scope(session, AgentRun, venture):
            if run.status in {"STALE", "REJECTED", "CANCELLED", "FAILED"} or current(session, run): continue
            run.status = "STALE"
            if run.artifact_id:
                a = scoped(session, Artifact, run.artifact_id, venture)
                if a: a.status = "STALE"
            for h in record_scope(session, Handoff, venture):
                if h.from_run_id == run.id: h.status = "STALE"
            for d in record_scope(session, Decision, venture):
                if d.target_id == run.id: d.stale = True
            if run.stage_id:
                stage = scoped(session, Stage, run.stage_id, venture)
                if stage.run_id == run.id:
                    stage.status = "STALE"
                    advance(session, venture, stage.pipeline_id)
            changed = True
        session.flush()


def execute_one(factory, settings=None):
    from venture_forge.shared.config import Settings
    settings = settings or Settings()
    with factory() as session:
        # Recover an interrupted worker without repeating a potentially billed model request.
        for abandoned in session.scalars(select(AgentRun).where(AgentRun.status == "RUNNING")).all():
            started_at = abandoned.started_at or abandoned.created_at
            if (now() - started_at.replace(tzinfo=timezone.utc)).total_seconds() > abandoned.request["budget"]["max_seconds"] + 120:
                abandoned.status, abandoned.error_code = "FAILED", "WORKER_INTERRUPTED"
                if abandoned.stage_id:
                    stage = session.get(Stage, abandoned.stage_id)
                    if stage.run_id == abandoned.id: stage.status = "FAILED"
        session.commit()
        run = session.scalar(select(AgentRun).where(AgentRun.status == "QUEUED").order_by(AgentRun.created_at).limit(1))
        if not run: return False
        ident = run.id
        claimed = session.execute(update(AgentRun).where(AgentRun.id == ident, AgentRun.status == "QUEUED").values(status="RUNNING", started_at=now()))
        session.commit()
        if not claimed.rowcount: return True
    started, trace, usage = time.monotonic(), [], None
    try:
        with factory() as session:
            run = session.get(AgentRun, ident)
            if not current(session, run): raise GatewayError("STALE_CONTEXT")
            request, context = run.request, run.context
            spec = REGISTRY[run.agent_id]
            parameters = spec.schema.model_validate(request["parameters"]).model_dump(mode="json")
        if len(spec.tools) > request["budget"]["max_steps"]: raise GatewayError("STEP_CAP")
        result, tools = execute(run.agent_id, parameters, context)
        for name in tools:
            trace.append({"mode": "RULE", "tool": name, "policy": "specialist-policy-v1", "duration_ms": round((time.monotonic() - started) * 1000), "cost_inr": 0, "evidence_refs": result.evidence_ids})
        output, cost = result.model_dump(mode="json"), 0
        reason = "REQUIRED_INPUTS_MISSING" if result.status == "NEEDS_INPUT" else "DETERMINISTIC_REQUESTED" if request["mode"] == "RULE" else "NO_MODEL_CONFIGURED"
        route = Route(None, reason, spec.model_requirements, 0, 0).snapshot()
        if request["mode"] != "RULE" and result.status == "PROPOSED":
            remaining = request["budget"]["max_seconds"] - (time.monotonic() - started)
            if remaining <= 0: raise GatewayError("TIME_CAP")
            assistance, usage = draft(settings, output, {**request["budget"], "max_seconds": remaining}, requirements=spec.model_requirements, context=context, mode=request["mode"], data_policy=request.get("data_policy", "cloud_allowed"), allow_processing=request["allow_model_processing"], preferred_profile=request.get("preferred_profile"), remaining_steps=request["budget"]["max_steps"] - len(trace))
            route = usage["route"]
            if assistance is not None:
                output["data"]["model_assistance"] = {"status": "MODEL_INFERENCE", **assistance}
                output["mode"], cost = "MODEL", usage["cost_inr"]
                trace.append({"mode": "MODEL", "tool": "model.analyze", "policy": "validated-analysis-v3", **usage})
        if trace: trace[0]["route"] = route
        if time.monotonic() - started > request["budget"]["max_seconds"]: raise GatewayError("TIME_CAP")
        output = Result.model_validate(output).model_dump(mode="json")
        if output["agent_id"] != spec.id or output["output_type"] != spec.output or output["handoffs"] != list(spec.sends):
            raise GatewayError("INVALID_SPECIALIST_CONTRACT")
        with factory() as session:
            run = session.get(AgentRun, ident)
            if run.status != "RUNNING":
                # Cancellation prevents publication but cannot undo provider usage already incurred.
                run.trace, run.cost_inr = trace + [{"outcome": "RESULT_DISCARDED", "status": run.status}], cost
                session.commit()
                return True
            if not current(session, run): raise GatewayError("STALE_CONTEXT")
            run.result, run.result_hash, run.trace, run.cost_inr = output, digest(output), trace, cost
            run.status = "NEEDS_INPUT" if output["status"] == "NEEDS_INPUT" else "AWAITING_REVIEW"
            if run.stage_id:
                session.get(Stage, run.stage_id).status = run.status
            session.commit()
    except Exception as error:
        code = str(error) if isinstance(error, GatewayError) else "SPECIALIST_EXECUTION_FAILED"
        usage = (error.usage if isinstance(error, GatewayError) else None) or usage
        if trace and isinstance(error, GatewayError) and error.route: trace[0]["route"] = error.route
        if usage: trace.append({"mode": "MODEL", "tool": "model.analyze", "outcome": "FAILED", **usage})
        with factory() as session:
            run = session.get(AgentRun, ident)
            if run.status == "RUNNING":
                run.status, run.error_code, run.trace = "STALE" if code == "STALE_CONTEXT" else "FAILED", code, trace
                if usage: run.cost_inr = usage["cost_inr"]
                if run.stage_id: session.get(Stage, run.stage_id).status = run.status
                session.commit()
            elif usage:
                run.trace, run.cost_inr = trace + [{"outcome": "RESULT_DISCARDED", "status": run.status}], usage["cost_inr"]
                session.commit()
    return True
