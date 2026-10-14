"""Scrape one region incrementally into the data directory.

Data layout (lives on the `data` branch, not on main):

  {region}/bodies.json
  {region}/meetings/{body_id}/{yyyy-mm-dd}.json
  {region}/state.json            seen meetings with content hashes
  {region}/status.json           result of the last run
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .adapters import ADAPTERS
from .http import Fetcher, RobotsDisallowed
from .models import PARSER_VERSION, Meeting
from .text import excluded

log = logging.getLogger(__name__)

RECHECK_DAYS = 60     # agendas become minutes; personal data is removed after the appeal period


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _hash(obj: Any) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]


def _read(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def _write(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def _active_epochs(region: dict[str, Any]) -> list[dict[str, Any]]:
    return [e for e in region.get("epochs", []) if e.get("enabled", True)]


def scrape_region(region: dict[str, Any], data_dir: Path, *, since: str | None = None,
                  max_meetings: int | None = None, max_minutes: float | None = None,
                  refresh: bool = False, delay: float = 1.0) -> dict[str, Any]:
    rid = region["id"]
    out = data_dir / rid
    state = _read(out / "state.json", {"meetings": {}})
    seen: dict[str, Any] = state.setdefault("meetings", {})
    since = since or region.get("since", "2025-06-01")
    recheck_from = (date.today() - timedelta(days=RECHECK_DAYS)).isoformat()
    started = time.monotonic()
    fetcher = Fetcher(delay=delay)
    status: dict[str, Any] = {"region": rid, "started_at": _now(), "parser_version": PARSER_VERSION,
                              "fetched": 0, "changed": 0, "unchanged": 0, "removed": 0, "errors": [],
                              "complete": True, "result": "ok"}
    bodies_out: dict[str, Any] = {b["id"]: b for b in _read(out / "bodies.json", [])}
    listed_urls: set[str] = set()
    budget_hit = False

    for epoch in _active_epochs(region):
        adapter_cls = ADAPTERS[epoch["platform"]]
        adapter = adapter_cls(region, epoch, fetcher)
        ep_from = epoch.get("valid_from", "0000-01-01")
        ep_to = epoch.get("valid_to", "9999-12-31")
        try:
            bodies = adapter.list_bodies()
        except RobotsDisallowed as e:
            status["result"] = "blocked"
            status["errors"].append(f"robots.txt disallows {e}")
            continue
        except NotImplementedError as e:
            status["result"] = "not-implemented"
            status["errors"].append(str(e))
            continue
        except Exception as e:  # noqa: BLE001 - one broken region must not stop the run
            status["result"] = "error"
            status["errors"].append(f"list_bodies: {e!r}")
            continue

        refs = []
        for body in bodies:
            if excluded(body.name, region.get("exclude_bodies")):
                log.info("[%s] skipping body %s", rid, body.name)
                continue
            try:
                body_refs = adapter.list_meetings(body)
            except Exception as e:  # noqa: BLE001
                status["errors"].append(f"list_meetings {body.name}: {e!r}")
                continue
            bodies_out[body.id] = {"id": body.id, "name": body.name, "type": body.type,
                                   "url": body.url, "language": adapter.language}
            for r in body_refs:
                if since <= r.date and ep_from <= r.date <= ep_to:
                    refs.append(r)
                    listed_urls.add(r.url)

        refs.sort(key=lambda r: r.date, reverse=True)
        for ref in refs:
            prev = seen.get(ref.url)
            due = (refresh or prev is None or ref.date >= recheck_from
                   or prev.get("stage") != ref.stage or prev.get("parser_version") != PARSER_VERSION)
            if not due:
                status["unchanged"] += 1
                continue
            if max_meetings is not None and status["fetched"] >= max_meetings:
                budget_hit = True
                break
            if max_minutes is not None and (time.monotonic() - started) / 60 > max_minutes:
                budget_hit = True
                break
            try:
                meeting = adapter.fetch_meeting(ref)
            except Exception as e:  # noqa: BLE001
                log.exception("[%s] failed %s", rid, ref.url)
                status["errors"].append(f"fetch_meeting {ref.url}: {e!r}")
                continue
            meeting.id = prev["id"] if prev else _meeting_id(meeting, seen)
            body_dict = meeting.to_dict()
            body_dict.pop("provenance", None)
            content_hash = _hash(body_dict)
            meeting.provenance = {
                "source_url": ref.url, "fetched_at": _now(), "content_hash": content_hash,
                "parser_version": PARSER_VERSION, "platform": epoch["platform"],
                "first_seen": prev.get("first_seen") if prev else _now(),
            }
            if prev and prev.get("hash") == content_hash:
                # Keep the old timestamp so an unchanged meeting produces no diff.
                meeting.provenance["fetched_at"] = prev.get("fetched_at", meeting.provenance["fetched_at"])
            else:
                status["changed"] += 1
            _write(out / "meetings" / f"{meeting.id}.json", meeting.to_dict())
            seen[ref.url] = {"id": meeting.id, "date": meeting.date, "stage": meeting.stage,
                             "hash": content_hash, "fetched_at": meeting.provenance["fetched_at"],
                             "first_seen": meeting.provenance["first_seen"],
                             "parser_version": PARSER_VERSION}
            status["fetched"] += 1
            log.info("[%s] %s %s (%d items)", rid, meeting.date, meeting.body_name, len(meeting.items))

    # Mirror removals: a recent meeting that disappeared from the source disappears here too.
    if status["result"] == "ok" and not budget_hit:
        for url, info in list(seen.items()):
            if url not in listed_urls and info.get("date", "") >= recheck_from:
                (out / "meetings" / f"{info['id']}.json").unlink(missing_ok=True)
                del seen[url]
                status["removed"] += 1

    status["complete"] = not budget_hit
    status["requests"] = fetcher.requests_made
    status["finished_at"] = _now()
    status["meetings_total"] = len(seen)
    if status["errors"] and status["result"] == "ok":
        status["result"] = "partial"
    state["last_run"] = status["finished_at"]
    _write(out / "state.json", state)
    _write(out / "bodies.json", sorted(bodies_out.values(), key=lambda b: b["name"]))
    _write(out / "status.json", status)
    return status


def _meeting_id(m: Meeting, seen: dict[str, Any]) -> str:
    base = f"{m.body_id}/{m.date}"
    taken = {v["id"] for v in seen.values()}
    if base not in taken:
        return base
    n = 2
    while f"{base}-{n}" in taken:
        n += 1
    return f"{base}-{n}"

