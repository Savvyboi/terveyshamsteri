"""Region config files: regions/{id}.yaml."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def load_regions(regions_dir: Path) -> dict[str, dict[str, Any]]:
    regions: dict[str, dict[str, Any]] = {}
    for path in sorted(regions_dir.glob("*.yaml")):
        cfg = yaml.safe_load(path.read_text(encoding="utf-8"))
        cfg.setdefault("id", path.stem)
        for e in cfg.get("epochs", []):
            for k in ("valid_from", "valid_to"):
                if k in e and not isinstance(e[k], str):
                    e[k] = e[k].isoformat()   # YAML parses bare dates
        if "since" in cfg and not isinstance(cfg["since"], str):
            cfg["since"] = cfg["since"].isoformat()
        regions[cfg["id"]] = cfg
    return regions
