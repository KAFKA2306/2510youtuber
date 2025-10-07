"""Generate JSON config files for the Tauri frontend from YAML sources."""

from __future__ import annotations

import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1] / "tauri-app"
TARGETS = {
    "package.yaml": "package.json",
    "tsconfig.yaml": "tsconfig.json",
    "tsconfig.node.yaml": "tsconfig.node.json",
}


def write_json(source: Path, destination: Path) -> None:
    data = yaml.safe_load(source.read_text(encoding="utf-8")) or {}
    destination.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    for yaml_name, json_name in TARGETS.items():
        yaml_path = ROOT / yaml_name
        if not yaml_path.exists():
            continue
        write_json(yaml_path, ROOT / json_name)


if __name__ == "__main__":
    main()
