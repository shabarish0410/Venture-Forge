from pathlib import Path
import json
from venture_forge.product.api.app import app
from venture_forge.product.agents.registry import REGISTRY
from venture_forge.product.agents.outputs import OUTPUTS, DraftExperiment, LockedExperimentReview, SimulationResult, MissingSimulation
from venture_forge.product.agents.workspace_library import library

destination = Path(__file__).resolve().parents[1] / "docs" / "openapi.json"
destination.parent.mkdir(exist_ok=True)
destination.write_text(json.dumps(app.openapi(), indent=2) + "\n", encoding="utf-8")
print("Exported docs/openapi.json")

variants = {**{key: [value] for key, value in OUTPUTS.items()}, "experiment": [DraftExperiment, LockedExperimentReview], "simulation": [SimulationResult, MissingSimulation]}
specialists = {ident: {"input": spec.schema.model_json_schema(), "output_variants": [model.model_json_schema() for model in variants[ident]], "receives": spec.receives, "sends": spec.sends, "mvp": library(ident)} for ident, spec in REGISTRY.items()}
destination.with_name("specialist-contracts.json").write_text(json.dumps(specialists, indent=2) + "\n", encoding="utf-8")
print("Exported docs/specialist-contracts.json")
