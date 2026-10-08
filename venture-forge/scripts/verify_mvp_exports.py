"""Generate synthetic export specimens for visual QA, without touching a database."""
from pathlib import Path
from venture_forge.product.agents.registry import REGISTRY
from venture_forge.product.agents.specialists import execute
from venture_forge.product.core.mvp_exports import render_export

out = Path(__file__).resolve().parents[1] / ".local" / "mvp-export-qa"
out.mkdir(parents=True, exist_ok=True)
parameters = REGISTRY["model"].schema.model_validate({"workspace": {"options": [{"name": "Subscription pilot", "relationship": "b2b", "operating": "direct_service", "delivery": "saas", "pricing": "subscription", "payer": "Independent founder", "price_inr": "100", "units_per_period": 10}, {"name": "Manual service", "relationship": "b2b", "operating": "direct_service", "delivery": "managed_service", "pricing": "one_time"}], "selected_option": "Subscription pilot", "decision_reason": "Compare recurring paid use against a manual service.", "pricing_behavior": "Payment for a dated pilot", "pricing_threshold": "Three of ten participants", "canvas": [{"block": "customer_segments", "value": "Independent founders"}, {"block": "value_propositions", "value": "Save time copying source records"}]}}).model_dump(mode="json")
context = {"concept": {"customer_segment": "Independent founders", "geography": "India"}, "hypothesis": "Founders will pay for a pilot that saves time.", "objective": "Review the business model and price test.", "evidence": [], "artifacts": [], "experiments": []}
result, _ = execute("model", parameters, context)
payload = {"venture": {"id": "synthetic-export-fixture", "name": "Model review", "revision": 1}, "purpose": "Review model options and prepare a price test", "sources": [], "artifacts": [{"id": "synthetic-model-v1", "title": "Model Studio decision memo", "application": "model", "classification": result.evidence_class, "sections": result.data["workspace"]["sections"], "gaps": result.data["workspace"]["gaps"]}]}
for format in ["pdf", "docx", "csv", "json"]:
    path = out / ("model-review." + format)
    path.write_bytes(render_export(payload, format)[0])
    print(path)
