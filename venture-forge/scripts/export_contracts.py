from pathlib import Path
import json
from venture_forge.product.api.app import app

destination = Path(__file__).resolve().parents[1] / "docs" / "openapi.json"
destination.parent.mkdir(exist_ok=True)
destination.write_text(json.dumps(app.openapi(), indent=2) + "\n", encoding="utf-8")
print("Exported docs/openapi.json")
