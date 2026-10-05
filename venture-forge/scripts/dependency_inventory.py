"""Inventory installed direct dependency licenses without remote lookups."""
from pathlib import Path
import json
from importlib.metadata import metadata, version, requires
from packaging.requirements import Requirement

root = Path(__file__).resolve().parents[1]
rows = []
names = set()
for manifest in [root / "package.json", root / "apps/web/package.json"]:
    package = json.loads(manifest.read_text(encoding="utf-8"))
    names.update(package.get("dependencies", {}))
    names.update(package.get("devDependencies", {}))
for name in sorted(names):
    manifest = json.loads((root / "node_modules" / name / "package.json").read_text(encoding="utf-8"))
    license_name = manifest.get("license", "See package LICENSE")
    if isinstance(license_name, dict):
        license_name = license_name.get("type", "See package LICENSE")
    rows.append(f"| npm | {name} | {manifest['version']} | {license_name} |")
for name in sorted({Requirement(item).name for item in requires("venture-forge") or []}):
    package = metadata(name)
    license_name = package.get("License-Expression") or package.get("License") or "See installed METADATA/LICENSE"
    if len(license_name) > 100 or "\n" in license_name:
        classifiers = [item.rsplit(" :: ", 1)[-1] for item in package.get_all("Classifier", []) if item.startswith("License ::")]
        license_name = ", ".join(classifiers) or "See installed METADATA/LICENSE"
    rows.append(f"| Python | {name} | {version(name)} | {license_name} |")
(root / "docs/dependencies.md").write_text(
    "# Direct dependency inventory\n\nGenerated from installed package metadata. Lockfiles capture transitive versions; installed license files govern the full dependency tree.\n\n"
    "| Ecosystem | Package | Installed version | Declared license |\n| --- | --- | --- | --- |\n" + "\n".join(rows) + "\n",
    encoding="utf-8",
)
print("Generated docs/dependencies.md")
