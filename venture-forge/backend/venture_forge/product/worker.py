"""Single local worker: durable records, bounded rule execution, no external actions."""
import time
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from venture_forge.shared.config import Settings
from venture_forge.product.core.models import Venture
from venture_forge.product.core.workflow_models import Run, Receipt


def execute_one(factory):
    from venture_forge.product.agents.runtime import execute_one as execute_specialist
    if execute_specialist(factory): return True
    started = time.monotonic()
    with factory() as session:
        run = session.scalar(select(Run).where(Run.status == "QUEUED").order_by(Run.created_at).limit(1).with_for_update())
        if run is None: return False
        run.status = "RUNNING"
        session.commit()
        ident = run.id
    with factory() as session:
        run = session.get(Run, ident)
        if run.status != "RUNNING": return True
        venture = session.scalar(select(Venture).where(Venture.id == run.venture_id, Venture.owner_id == run.owner_id).with_for_update())
        receipts = session.scalars(select(Receipt).where(Receipt.id.in_(run.evidence_ids), Receipt.venture_id == run.venture_id, Receipt.owner_id == run.owner_id, Receipt.withdrawn.is_(False))).all()
        unknowns = []
        if not receipts: unknowns.append("No permitted evidence supplied. Gather a source or customer observation first.")
        if len(receipts) != len(set(run.evidence_ids)): unknowns.append("A linked source is unavailable or withdrawn.")
        if venture.revision != run.input_revision: unknowns.append("Passport changed after this run was queued. Create a new run.")
        support = sum(r.relation == "supports" for r in receipts)
        contrary = sum(r.relation == "contradicts" for r in receipts)
        run.proposal = {
            "status": "needs_input" if unknowns else "proposed",
            "objective": run.objective,
            "receipts": [{"id": r.id, "title": r.title, "relation": r.relation, "content_hash": r.content_hash} for r in receipts],
            "supporting_sources": support, "contrary_sources": contrary,
            "unknowns": unknowns + ["Source links do not independently verify a claim. Founder review is required."],
            "suggested_missions": ["Investigate the contrary source" if contrary else "Collect an independent observation", "Predeclare a real-world experiment"],
            "limitations": ["Rules count founder-labelled relationships; no model synthesis or live web search was performed."],
            "cost_inr": "0.00", "mode": "RULE", "schema_version": "1.0",
        }
        run.steps = [{"mode": "RULE", "policy": "scoped-evidence-v1", "duration_ms": round((time.monotonic() - started) * 1000), "cost_inr": "0.00", "evidence_refs": run.evidence_ids, "actor": "local-worker"}]
        run.status = "NEEDS_INPUT" if unknowns else "AWAITING_REVIEW"
        session.commit()
    return True


def main():
    from sqlalchemy.orm import sessionmaker
    engine = create_engine(Settings().database_url)
    factory = sessionmaker(engine, expire_on_commit=False)
    print("Venture Forge worker ready (13 specialists and evidence pipelines).", flush=True)
    try:
        while True:
            if not execute_one(factory): time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        engine.dispose()


if __name__ == "__main__": main()
