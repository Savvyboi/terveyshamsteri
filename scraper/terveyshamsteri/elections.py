"""Regional election results from Statistics Finland's PxWeb API.

One table per wellbeing services county lists every candidate of the 2025 regional
elections with party, votes and whether they were elected (1), became a deputy (2) or
were not elected (3). We keep elected councillors and deputies by name, because they are
the people who appear in council minutes, and only party totals for everyone else.

Election results are final, so a county's file is fetched once and kept afterwards
unless --refresh is given.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .http import Fetcher

log = logging.getLogger(__name__)

API = "https://pxdata.stat.fi/PxWeb/api/v1/fi/StatFin/alvaa/{table}"
SOURCE = "https://pxdata.stat.fi/PxWeb/pxweb/fi/StatFin/StatFin__alvaa/statfin_alvaa_pxt_{table}/"
YEAR = "2025"

# "Ehdokkaiden äänimäärä ja valintatieto aluevaaleissa, <county>, 2025"
TABLES = {
    "ita-uusimaa": "14z8.px",
    "keski-uusimaa": "14z9.px",
    "lansi-uusimaa": "14za.px",
    "vantaa-kerava": "14zb.px",
    "varsinais-suomi": "14zc.px",
    "satakunta": "14zd.px",
    "kanta-hame": "14ze.px",
    "pirkanmaa": "14zf.px",
    "paijat-hame": "14zg.px",
    "kymenlaakso": "14zh.px",
    "etela-karjala": "14zi.px",
    "etela-savo": "14zj.px",
    "pohjois-savo": "14zk.px",
    "pohjois-karjala": "14zl.px",
    "keski-suomi": "14zm.px",
    "etela-pohjanmaa": "14zn.px",
    "pohjanmaa": "14zp.px",
    "keski-pohjanmaa": "14zq.px",
    "pohjois-pohjanmaa": "14zr.px",
    "kainuu": "14zs.px",
    "lappi": "14zt.px",
}

STATUS = {1: "elected", 2: "deputy", 3: "not-elected"}

# Party abbreviations as Statistics Finland writes them, with names and display colours.
PARTIES: dict[str, dict[str, Any]] = {
    "KOK": {"fi": "Kansallinen Kokoomus", "sv": "Samlingspartiet", "en": "National Coalition Party", "color": "#006288"},
    "SDP": {"fi": "Suomen Sosialidemokraattinen Puolue", "sv": "Finlands Socialdemokratiska Parti", "en": "Social Democratic Party", "color": "#e11931"},
    "PS": {"fi": "Perussuomalaiset", "sv": "Sannfinländarna", "en": "Finns Party", "color": "#c9a400"},
    "KESK": {"fi": "Suomen Keskusta", "sv": "Centern i Finland", "en": "Centre Party", "color": "#01954b"},
    "VIHR": {"fi": "Vihreä liitto", "sv": "Gröna förbundet", "en": "Green League", "color": "#4f9b17"},
    "VAS": {"fi": "Vasemmistoliitto", "sv": "Vänsterförbundet", "en": "Left Alliance", "color": "#c8004f"},
    "RKP": {"fi": "Suomen ruotsalainen kansanpuolue", "sv": "Svenska folkpartiet i Finland", "en": "Swedish People’s Party", "color": "#d49a00"},
    "KD": {"fi": "Suomen Kristillisdemokraatit", "sv": "Kristdemokraterna i Finland", "en": "Christian Democrats", "color": "#18359b"},
    "LIIKE": {"fi": "Liike Nyt", "sv": "Liike Nyt", "en": "Movement Now", "color": "#b5006a"},
    "LIBE": {"fi": "Liberaalipuolue – Vapaus valita", "sv": "Liberalpartiet – Valfrihet", "en": "Liberal Party", "color": "#2a9fd6"},
    "SKP": {"fi": "Suomen Kommunistinen Puolue", "sv": "Finlands Kommunistiska Parti", "en": "Communist Party of Finland", "color": "#8b0000"},
    "EOP": {"fi": "Eläinoikeuspuolue", "sv": "Djurrättspartiet", "en": "Animal Justice Party", "color": "#5a7d2a"},
    "PIR": {"fi": "Piraattipuolue", "sv": "Piratpartiet", "en": "Pirate Party", "color": "#5b2c83"},
    "KRIP": {"fi": "Kristallipuolue", "sv": "Kristallpartiet", "en": "Crystal Party", "color": "#5d7fa3"},
    "VKK": {"fi": "Vapauden liitto", "sv": "Frihetsförbundet", "en": "Freedom Alliance", "color": "#6d6d6d"},
    "KP": {"fi": "Kansalaispuolue", "sv": "Medborgarpartiet", "en": "Citizens’ Party", "color": "#6d6d6d"},
    "SKE": {"fi": "Suomen Kansa Ensin", "sv": "Suomen Kansa Ensin", "en": "Finnish People First", "color": "#6d6d6d"},
    "VL": {"fi": "Valta kuuluu kansalle", "sv": "Valta kuuluu kansalle", "en": "Power Belongs to the People", "color": "#6d6d6d"},
    "KTP": {"fi": "Kommunistinen Työväenpuolue", "sv": "Kommunistiska arbetarpartiet", "en": "Communist Workers’ Party", "color": "#6d6d6d"},
}
OTHER_COLOR = "#7a8494"


def _query() -> dict[str, Any]:
    return {
        "query": [{"code": "timeperiod_y", "selection": {"filter": "item", "values": [YEAR]}}],
        "response": {"format": "json-stat2"},
    }


def parse_jsonstat(doc: dict[str, Any]) -> list[dict[str, Any]]:
    """Turn a json-stat2 candidate table into one dict per candidate.

    The dimensions are year x candidate x content; values are row-major in `id` order."""
    ids: list[str] = doc["id"]
    sizes: list[int] = doc["size"]
    dims = doc["dimension"]
    cand_dim = next(d for d in ids if d.startswith("vaaliehdokas"))
    cont_dim = next(d for d in ids if d == "contentscode" or d.lower().startswith("contents") or d == "Tiedot")
    cand_index = dims[cand_dim]["category"]["index"]
    cand_label = dims[cand_dim]["category"]["label"]
    cont_index = dims[cont_dim]["category"]["index"]
    # index may be a dict {code: position} or a list of codes
    if isinstance(cand_index, list):
        cand_index = {c: i for i, c in enumerate(cand_index)}
    if isinstance(cont_index, list):
        cont_index = {c: i for i, c in enumerate(cont_index)}

    strides = [1] * len(sizes)
    for i in range(len(sizes) - 2, -1, -1):
        strides[i] = strides[i + 1] * sizes[i + 1]
    values = doc["value"]
    ci, ki = ids.index(cand_dim), ids.index(cont_dim)

    def value(cand_pos: int, content: str) -> Any:
        pos = cont_index.get(content)
        if pos is None:
            return None
        return values[cand_pos * strides[ci] + pos * strides[ki]]

    def content_like(word: str) -> str | None:
        return next((c for c in cont_index if word in c), None)

    k_votes, k_share = content_like("aanet_yht"), content_like("osuus")
    k_status, k_prev = content_like("valinta"), content_like("aluevalt")
    out = []
    for code, pos in cand_index.items():
        label = cand_label.get(code, "")
        parts = [p.strip() for p in label.split(" / ")]
        if len(parts) < 2 or not parts[0]:
            continue  # totals or malformed rows
        status = value(pos, k_status) if k_status else None
        prev = value(pos, k_prev) if k_prev else None
        out.append({
            "id": code,
            "name": parts[0],
            "party": parts[1],
            "votes": _int(value(pos, k_votes)) if k_votes else None,
            "share": value(pos, k_share) if k_share else None,
            "status": STATUS.get(_int(status) or 0, "unknown"),
            "incumbent": _int(prev) == 1,
        })
    return out


def _int(v: Any) -> int | None:
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def display_name(official: str) -> str:
    """'Aaltonen Heikki' -> 'Heikki Aaltonen'. Statistics Finland writes surname first.
    Compound surnames keep their hyphen; a few registered names have two surnames
    ('von Bonsdorff Anna'), which is why the particle stays with the surname."""
    parts = official.split()
    if len(parts) < 2:
        return official
    i = 1
    while i < len(parts) - 1 and parts[i - 1].lower() in ("von", "af", "de", "van", "der"):
        i += 1
    return " ".join(parts[i:] + parts[:i])


def summarize(region: str, table: str, candidates: list[dict[str, Any]]) -> dict[str, Any]:
    parties: dict[str, dict[str, Any]] = {}
    total = 0
    for c in candidates:
        p = parties.setdefault(c["party"], {"party": c["party"], "votes": 0, "candidates": 0, "seats": 0})
        p["votes"] += c["votes"] or 0
        p["candidates"] += 1
        p["seats"] += c["status"] == "elected"
        total += c["votes"] or 0
    for p in parties.values():
        p["share"] = round(100 * p["votes"] / total, 1) if total else None
    people = [
        {**{k: c[k] for k in ("id", "party", "votes", "share", "status", "incumbent")},
         "name": display_name(c["name"]), "official_name": c["name"]}
        for c in candidates if c["status"] in ("elected", "deputy")
    ]
    people.sort(key=lambda c: (c["status"] != "elected", -(c["votes"] or 0)))
    return {
        "region": region,
        "year": int(YEAR),
        "source": SOURCE.format(table=table),
        "fetched_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "votes_total": total,
        "seats": sum(p["seats"] for p in parties.values()),
        "parties": sorted(parties.values(), key=lambda p: (-p["seats"], -p["votes"])),
        "people": people,
    }


def fetch_elections(data_dir: Path, regions: list[str] | None = None, refresh: bool = False,
                    fetcher: Fetcher | None = None) -> dict[str, str]:
    """Write data/elections/2025/{region}.json and data/elections/parties.json."""
    fetcher = fetcher or Fetcher(delay=2.0)
    out_dir = data_dir / "elections" / YEAR
    out_dir.mkdir(parents=True, exist_ok=True)
    results: dict[str, str] = {}
    for region, table in TABLES.items():
        if regions and region not in regions:
            continue
        path = out_dir / f"{region}.json"
        if path.exists() and not refresh:
            results[region] = "kept"
            continue
        url = API.format(table=table)
        try:
            if not fetcher.allowed(url):
                raise PermissionError(f"robots.txt disallows {url}")
            fetcher._wait("pxdata.stat.fi")
            r = fetcher.session.post(url, json=_query(), timeout=fetcher.timeout)
            r.raise_for_status()
            candidates = parse_jsonstat(r.json())
            if not candidates:
                raise ValueError("no candidates in response")
            path.write_text(json.dumps(summarize(region, table, candidates), ensure_ascii=False, indent=1) + "\n",
                            encoding="utf-8")
            results[region] = f"ok ({len(candidates)} candidates)"
        except Exception as e:  # noqa: BLE001 - one county's failure must not stop the others
            log.exception("election table %s failed", table)
            results[region] = f"error: {e!r}"
    (data_dir / "elections" / "parties.json").write_text(
        json.dumps({k: {**v, "color": v.get("color", OTHER_COLOR)} for k, v in PARTIES.items()},
                   ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return results

