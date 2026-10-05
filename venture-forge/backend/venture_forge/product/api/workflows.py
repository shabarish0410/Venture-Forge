import hashlib
import json
from decimal import Decimal
from datetime import date
from fastapi import Depends, Header
from sqlalchemy import select
from pydantic import ValidationError
from venture_forge.product.core.models import Activity, Hypothesis, now
from venture_forge.product.core.workflow_models import Receipt, Artifact, Experiment, Observation, Decision, Run
from venture_forge.product.core.workflow_schemas import Command, ConceptUpdate, ReceiptCreate, ArtifactCreate, FinanceInputs, MarketInputs, WorksheetInputs, ExperimentCreate, ObservationCreate, DecisionCreate, RunCreate
from venture_forge.product.core.tools import CAPABILITIES, calculate, money


def encode(row):
    result = {}
    for col in row.__table__.columns:
        if col.name == "owner_id":
            continue
        value = getattr(row, col.name)
        result[col.name] = value.isoformat() if hasattr(value, "isoformat") else value
    return result


def rows(session, model, venture):
    return session.scalars(select(model).where(model.venture_id == venture.id, model.owner_id == venture.owner_id).order_by(model.created_at)).all()


def experiment_result(experiment, observations, receipts):
    available = {r.id for r in receipts if not r.withdrawn}
    valid = [o for o in observations if o.receipt_id in available and o.instrument_valid and not o.deviation]
    n = len(valid)
    successes = sum(o.success for o in valid)
    rate = Decimal(successes) / n * 100 if n else Decimal(0)
    threshold = Decimal(experiment.protocol["threshold_percent"])
    # Any instrumentation failure or protocol deviation requires review, not a pass.
    inconclusive = len(valid) != len(observations) or n < experiment.protocol["minimum_n"]
    outcome = "INCONCLUSIVE" if inconclusive else "THRESHOLD_MET" if rate >= threshold else "THRESHOLD_NOT_MET"
    return {"n": n, "recorded_n": len(observations), "successes": successes, "rate_percent": money(rate) if n else None, "threshold_percent": str(threshold), "outcome": outcome, "minimum_n": experiment.protocol["minimum_n"]}


def read_workspace(session, venture):
    from .agents import read_agents
    receipts = rows(session, Receipt, venture)
    decisions = rows(session, Decision, venture)
    experiments = []
    for item in rows(session, Experiment, venture):
        observations = [o for o in rows(session, Observation, venture) if o.experiment_id == item.id]
        experiments.append({**encode(item), "observations": [encode(o) for o in observations], "result": experiment_result(item, observations, receipts)})
    # Withdrawn originals remain private in storage; public read/export views redact them.
    evidence = [{**encode(r), "content": "[Withdrawn source]" if r.withdrawn else r.content, "locator": "[Withdrawn]" if r.withdrawn else r.locator, "participant_code": None if r.withdrawn else r.participant_code} for r in receipts]
    artifacts = [{**encode(r), "inputs": {} if r.status == "STALE" else r.inputs, "result": {"notice": "Dependent source or concept changed. Rebuild this worksheet."} if r.status == "STALE" else r.result} for r in rows(session, Artifact, venture)]
    safe_decisions = [{**encode(r), "result_snapshot": {"notice": "An input changed or a source was withdrawn."} if r.stale else r.result_snapshot} for r in decisions]
    return {"evidence": evidence, "evidence_count": sum(not r.withdrawn for r in receipts), "artifacts": artifacts, "experiments": experiments, "decisions": safe_decisions, "decision_count": len(decisions), "runs": [encode(r) for r in rows(session, Run, venture)], "completed_cycles": sum(d.target_type == "experiment" and not d.stale and d.result_snapshot.get("outcome") in {"THRESHOLD_MET", "THRESHOLD_NOT_MET"} for d in decisions), **read_agents(session, venture)}


def install_workflows(app, db, owner, owned_venture, passport, replay, remember, fail, settings):
    def scoped(session, model, record_id, venture):
        record = session.scalar(select(model).where(model.id == record_id, model.venture_id == venture.id, model.owner_id == venture.owner_id))
        if record is None:
            fail("NOT_FOUND", "Record not found in this venture.", 404)
        return record

    def evidence_scope(session, ids, venture):
        for ident in ids:
            receipt = scoped(session, Receipt, ident, venture)
            if receipt.withdrawn:
                fail("SOURCE_WITHDRAWN", "A linked source has been withdrawn.", 409)

    def begin(session, founder, venture_id, body, key, operation):
        venture = owned_venture(session, founder, venture_id, lock=True)
        payload = body.model_dump(mode="json")
        prior = replay(session, founder, operation, key, payload)
        if prior is not None:
            return venture, payload, prior
        if body.expected_revision != venture.revision:
            fail("REVISION_CONFLICT", "Your Passport changed. Refresh before saving.", 409)
        return venture, payload, None

    def finish(session, founder, venture, key, payload, operation, description, result=None):
        from venture_forge.product.agents.runtime import invalidate
        session.flush()
        invalidate(session, venture)
        venture.revision += 1
        venture.updated_at = now()
        session.add(Activity(venture_id=venture.id, owner_id=founder.id, event_type=operation.split(":")[0], description=description))
        session.flush()
        response = result() if result else passport(session, venture).model_dump(mode="json")
        remember(session, founder, operation, key, payload, response)
        session.commit()
        return response

    @app.get("/api/v1/capabilities")
    def capabilities(founder=Depends(owner)):
        return [{"id": ident, "name": name, "specialist": specialist, "engine": engine, "mode": "RULE", "external_actions": False} for ident, name, specialist, engine in CAPABILITIES]

    @app.post("/api/v1/ventures/{venture_id}/intake")
    def edit_concept(venture_id: str, body: ConceptUpdate, founder=Depends(owner), session=Depends(db), idempotency_key: str | None = Header(default=None)):
        op = f"concept.update:{venture_id}"
        venture, payload, prior = begin(session, founder, venture_id, body, idempotency_key, op)
        if prior is not None: return prior
        before = {field: getattr(venture, field) for field in ["name", "idea", "customer_segment", "geography"]}
        after = body.model_dump(exclude={"expected_revision"})
        for record in rows(session, Artifact, venture):
            if record.capability not in {"home", "academy"}: record.status = "STALE"
        for run in rows(session, Run, venture):
            run.status, run.proposal = "NEEDS_INPUT", {"unknowns": ["Founder corrected the concept. Start a new mission."]}
        for field, value in after.items(): setattr(venture, field, value)
        session.add(Artifact(venture_id=venture.id, owner_id=founder.id, capability="home", title="Founder concept correction", inputs=before, result=after, venture_revision=venture.revision + 1, status="ACCEPTED"))
        return finish(session, founder, venture, idempotency_key, payload, op, "Founder corrected the concept; dependent worksheets need a new review.")

    @app.post("/api/v1/ventures/{venture_id}/evidence", status_code=201)
    def capture(venture_id: str, body: ReceiptCreate, founder=Depends(owner), session=Depends(db), idempotency_key: str | None = Header(default=None)):
        op = f"evidence.capture:{venture_id}"
        venture, payload, prior = begin(session, founder, venture_id, body, idempotency_key, op)
        if prior is not None: return prior
        scoped(session, Hypothesis, body.hypothesis_id, venture)
        values = body.model_dump(mode="json", exclude={"expected_revision"})
        session.add(Receipt(venture_id=venture.id, owner_id=founder.id, **values, content_hash=hashlib.sha256(body.content.encode()).hexdigest()))
        return finish(session, founder, venture, idempotency_key, payload, op, "Source captured with provenance and explicit limitations.")

    @app.post("/api/v1/ventures/{venture_id}/evidence/{receipt_id}/withdraw")
    def withdraw(venture_id: str, receipt_id: str, body: Command, founder=Depends(owner), session=Depends(db), idempotency_key: str | None = Header(default=None)):
        op = f"evidence.withdraw:{receipt_id}"
        venture, payload, prior = begin(session, founder, venture_id, body, idempotency_key, op)
        if prior is not None: return prior
        receipt = scoped(session, Receipt, receipt_id, venture)
        receipt.withdrawn, receipt.withdrawn_at = True, now()
        for artifact in rows(session, Artifact, venture):
            if receipt_id in artifact.evidence_ids: artifact.status = "STALE"
        for decision in rows(session, Decision, venture):
            if receipt_id in decision.evidence_ids: decision.stale = True
        for run in rows(session, Run, venture):
            if receipt_id in run.evidence_ids:
                run.status, run.proposal = "NEEDS_INPUT", {"unknowns": ["A source was withdrawn. Create a new run with current sources."]}
        return finish(session, founder, venture, idempotency_key, payload, op, "Source withdrawn; linked proposals and decisions marked stale.")

    @app.post("/api/v1/ventures/{venture_id}/artifacts", status_code=201)
    def artifact(venture_id: str, body: ArtifactCreate, founder=Depends(owner), session=Depends(db), idempotency_key: str | None = Header(default=None)):
        op = f"artifact.create:{venture_id}"
        venture, payload, prior = begin(session, founder, venture_id, body, idempotency_key, op)
        if prior is not None: return prior
        evidence_scope(session, body.evidence_ids, venture)
        try:
            schema = FinanceInputs if body.capability in {"finance", "simulation"} else MarketInputs if body.capability == "market" else WorksheetInputs
            inputs = schema.model_validate(body.inputs)
        except ValidationError:
            fail("INVALID_INPUTS", "Check the units, values and required fields for this tool.", 422)
        if body.capability in {"market", "finance", "simulation"}:
            result = calculate(body.capability, inputs)
        else:
            result = {"fields": inputs.fields, "status": "ASSUMPTIONS", "unknowns": [k for k, v in inputs.fields.items() if not v.strip() or v.strip().lower() == "unknown"]}
        if body.capability == "ecosystem":
            result["notice"] = "Founder-entered programme notes; verify the official call and eligibility before applying. No live opportunity feed."
        session.add(Artifact(venture_id=venture.id, owner_id=founder.id, capability=body.capability, title=body.title, inputs=inputs.model_dump(mode="json"), result=result, evidence_ids=body.evidence_ids, venture_revision=venture.revision + 1, formula_version=result.get("formula_version", "rules-v1")))
        return finish(session, founder, venture, idempotency_key, payload, op, f"{body.capability.title()} worksheet saved as a versioned proposal.")

    @app.post("/api/v1/ventures/{venture_id}/experiments", status_code=201)
    def lock_experiment(venture_id: str, body: ExperimentCreate, founder=Depends(owner), session=Depends(db), idempotency_key: str | None = Header(default=None)):
        op = f"experiment.lock:{venture_id}"
        venture, payload, prior = begin(session, founder, venture_id, body, idempotency_key, op)
        if prior is not None: return prior
        scoped(session, Hypothesis, body.hypothesis_id, venture)
        if body.protocol.end_date < date.today(): fail("PAST_END_DATE", "Choose a current or future end date.", 422)
        protocol = body.protocol.model_dump(mode="json")
        digest = hashlib.sha256(json.dumps(protocol, sort_keys=True).encode()).hexdigest()
        session.add(Experiment(venture_id=venture.id, owner_id=founder.id, hypothesis_id=body.hypothesis_id, title=body.title, protocol=protocol, protocol_hash=digest))
        return finish(session, founder, venture, idempotency_key, payload, op, "Experiment protocol locked before observations. Changes require a new experiment.")

    @app.post("/api/v1/ventures/{venture_id}/experiments/{experiment_id}/observations", status_code=201)
    def observe(venture_id: str, experiment_id: str, body: ObservationCreate, founder=Depends(owner), session=Depends(db), idempotency_key: str | None = Header(default=None)):
        op = f"experiment.observe:{experiment_id}"
        venture, payload, prior = begin(session, founder, venture_id, body, idempotency_key, op)
        if prior is not None: return prior
        experiment = scoped(session, Experiment, experiment_id, venture)
        if any(d.target_type == "experiment" and d.target_id == experiment.id for d in rows(session, Decision, venture)):
            fail("EXPERIMENT_REVIEWED", "This experiment has been reviewed. Start a new protocol for more observations.", 409)
        receipt = scoped(session, Receipt, body.receipt_id, venture)
        evidence_scope(session, [receipt.id], venture)
        if receipt.hypothesis_id != experiment.hypothesis_id or receipt.kind == "source":
            fail("OBSERVATION_REQUIRED", "Link a real interview or observation for this hypothesis.", 422)
        if receipt.participant_code and receipt.participant_code != body.participant_code:
            fail("PARTICIPANT_MISMATCH", "Participant code must match the source receipt.", 422)
        if receipt.collected_on < experiment.locked_at.date().isoformat():
            fail("PRELOCK_OBSERVATION", "The source observation predates the locked protocol.", 422)
        observations = [o for o in rows(session, Observation, venture) if o.experiment_id == experiment_id]
        if any(o.participant_code == body.participant_code or o.receipt_id == receipt.id for o in observations):
            fail("DUPLICATE_PARTICIPANT", "This participant or receipt is already counted.", 409)
        session.add(Observation(venture_id=venture.id, owner_id=founder.id, experiment_id=experiment_id, **body.model_dump(exclude={"expected_revision"})))
        return finish(session, founder, venture, idempotency_key, payload, op, "Observed result appended to the locked experiment.")

    @app.post("/api/v1/ventures/{venture_id}/decisions", status_code=201)
    def decide(venture_id: str, body: DecisionCreate, founder=Depends(owner), session=Depends(db), idempotency_key: str | None = Header(default=None)):
        op = f"decision.create:{venture_id}"
        venture, payload, prior = begin(session, founder, venture_id, body, idempotency_key, op)
        if prior is not None: return prior
        model = {"artifact": Artifact, "experiment": Experiment, "run": Run}[body.target_type]
        target = scoped(session, model, body.target_id, venture)
        if any(d.target_id == target.id and d.target_type == body.target_type for d in rows(session, Decision, venture)):
            fail("ALREADY_REVIEWED", "This record already has a founder decision.", 409)
        if body.target_type == "experiment":
            if body.choice not in {"continue", "revise", "stop"}: fail("INVALID_DECISION", "Choose continue, revise or stop.", 422)
            observations = [o for o in rows(session, Observation, venture) if o.experiment_id == target.id]
            snapshot = experiment_result(target, observations, rows(session, Receipt, venture))
            refs = [o.receipt_id for o in observations]
        else:
            if body.choice not in {"accept", "reject"}: fail("INVALID_DECISION", "Choose accept or reject.", 422)
            if target.status not in {"PROPOSED", "AWAITING_REVIEW"}: fail("NOT_REVIEWABLE", "The proposal needs current inputs before review.", 409)
            refs = target.evidence_ids
            evidence_scope(session, refs, venture)
            snapshot = target.result if body.target_type == "artifact" else target.proposal
            target.status = "ACCEPTED" if body.choice == "accept" else "REJECTED"
            if body.target_type == "artifact" and target.capability == "model" and body.choice == "accept":
                for record in rows(session, Artifact, venture):
                    if record.id != target.id and record.capability in {"market", "finance", "simulation", "investor"}: record.status = "STALE"
        session.add(Decision(venture_id=venture.id, owner_id=founder.id, target_type=body.target_type, target_id=target.id, choice=body.choice, rationale=body.rationale, result_snapshot=snapshot, evidence_ids=refs))
        return finish(session, founder, venture, idempotency_key, payload, op, "Founder decision recorded with rationale and an immutable result snapshot.")

    @app.post("/api/v1/ventures/{venture_id}/runs", status_code=202)
    def enqueue(venture_id: str, body: RunCreate, founder=Depends(owner), session=Depends(db), idempotency_key: str | None = Header(default=None)):
        op = f"run.create:{venture_id}"
        venture, payload, prior = begin(session, founder, venture_id, body, idempotency_key, op)
        if prior is not None: return prior
        scoped(session, Hypothesis, body.hypothesis_id, venture)
        evidence_scope(session, body.evidence_ids, venture)
        if any(scoped(session, Receipt, ident, venture).hypothesis_id != body.hypothesis_id for ident in body.evidence_ids):
            fail("HYPOTHESIS_SCOPE", "Use evidence linked to this hypothesis.", 422)
        run = Run(venture_id=venture.id, owner_id=founder.id, hypothesis_id=body.hypothesis_id, capability=body.capability, objective=body.objective, evidence_ids=body.evidence_ids, input_revision=venture.revision + 1)
        session.add(run)
        return finish(session, founder, venture, idempotency_key, payload, op, "Bounded evidence run queued for the local worker.", lambda: encode(run))

    @app.get("/api/v1/runs/{run_id}")
    def get_run(run_id: str, founder=Depends(owner), session=Depends(db)):
        run = session.scalar(select(Run).where(Run.id == run_id, Run.owner_id == founder.id))
        if run is None: fail("NOT_FOUND", "Run not found.", 404)
        return encode(run)

    from .agents import install_agents
    install_agents(app, db, owner, owned_venture, passport, begin, finish, fail, settings)
