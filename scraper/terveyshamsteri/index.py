"""Write the top-level files the site reads: regions.json and status.json."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def build_index(regions: dict[str, dict[str, Any]], data_dir: Path) -> None:
    out = []
    for rid, cfg in sorted(regions.items()):
        status_path = data_dir / rid / "status.json"
        status = json.loads(status_path.read_text(encoding="utf-8")) if status_path.exists() else None
        meetings = list((data_dir / rid / "meetings").rglob("*.json"))
        out.append({
            "id": rid,
            "name": cfg.get("name", {}),
            "short": cfg.get("short", {}),
            "homepage": cfg.get("homepage"),
            "enabled": bool(cfg.get("enabled")),
            "platforms": sorted({e["platform"] for e in cfg.get("epochs", [])}),
            "sources": [{"platform": e["platform"], "url": e.get("entry_url", e["base_url"]),
                         "valid_from": e.get("valid_from"), "valid_to": e.get("valid_to")}
                        for e in cfg.get("epochs", [])],
            "since": cfg.get("since"),
            "notes": cfg.get("notes", {}),
            "meetings": len(meetings),
            "status": status,
        })
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "regions.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n",
                                           encoding="utf-8")
    (data_dir / "status.json").write_text(json.dumps({
        "updated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "regions": {r["id"]: (r["status"] or {}).get("result", "never-run") for r in out if r["enabled"]},
    }, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
