"""Wellbeing services county finances from the State Treasury's open REST interface.

Every county reports its finances to the State Treasury (Valtiokonttori) in standard XBRL
reports, which the treasury republishes at prodkuntarest.westeurope.cloudapp.azure.com and
on Tutkihallintoa.fi. We use three of them:

- HTAS: the budget for the coming year and the plan for the two after it, plus the current
  year's budget with its amendments.
- HTPE: the year-end forecast each county makes with its half-year report.
- HHKNR: quarterly cumulative account balances. The fourth quarter (period YYYYC12) is the
  year's preliminary outcome; the latest quarter shows the year so far.

Reports give each figure as a numeric code; the treasury's taxonomy files name the codes.
We match lines by their names rather than codes, because codes change between taxonomy
versions while the names stay put.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .http import Fetcher

log = logging.getLogger(__name__)

REST = "https://prodkuntarest.westeurope.cloudapp.azure.com/rest/v1/json"
TAXONOMY = "https://tkdpprodjrpstacc02.blob.core.windows.net/kuntataloudentaksonomia/{report}.json"
SOURCE = "https://www.tutkihallintoa.fi/hyvinvointialueiden-talous/"

# Business IDs (Y-tunnus) of the 21 wellbeing services counties.
YTUNNUS = {
    "ita-uusimaa": "3221339-3",
    "keski-uusimaa": "3221340-6",
    "lansi-uusimaa": "3221347-3",
    "vantaa-kerava": "3221356-1",
    "varsinais-suomi": "3221065-1",
    "satakunta": "3221304-3",
    "kanta-hame": "3221307-8",
    "pirkanmaa": "3221308-6",
    "paijat-hame": "3221309-4",
    "kymenlaakso": "3221311-5",
    "etela-karjala": "3221313-1",
    "etela-savo": "3221315-8",
    "pohjois-savo": "3221316-6",
    "pohjois-karjala": "3221317-4",
    "keski-suomi": "3221318-2",
    "etela-pohjanmaa": "3221323-8",
    "pohjanmaa": "3221324-6",
    "keski-pohjanmaa": "3221325-4",
    "pohjois-pohjanmaa": "3221326-2",
    "kainuu": "3221331-8",
    "lappi": "3221332-6",
}

# Normalised line name -> our key. Budgets say "tulot/menot" where accounts say "tuotot/kulut".
LINES = {
    "toimintatuotot": "income", "toimintatulot": "income",
    "myyntituotot": "sales", "myyntitulot": "sales",
    "maksutuotot": "fees", "maksutulot": "fees",
    "tuet ja avustukset": "grants_in",
    "muut toimintatuotot": "other_income", "muut toimintatulot": "other_income",
    "toimintakulut": "expenses", "toimintamenot": "expenses",
    "henkilöstökulut": "staff", "henkilöstömenot": "staff",
    "palvelujen ostot": "purchases",
    "aineet, tarvikkeet ja tavarat": "materials",
    "avustukset": "grants_out",
    "muut toimintakulut": "other_expenses", "muut toimintamenot": "other_expenses",
    "toimintakate": "operating_margin",
    "valtion rahoitus": "state_funding",
    "rahoitustuotot ja -kulut": "financial", "rahoitustuotot (+) ja -kulut (-)": "financial",
    "rahoitustulot (+) ja -menot (-)": "financial", "rahoitustuotot ja -kulut + (-)": "financial",
    "vuosikate": "annual_margin",
    "poistot ja arvonalentumiset": "depreciation",
    "tilikauden tulos": "result",
    "tilikauden ylijäämä (alijäämä)": "surplus",
    "investointimenot yhteensä (brutto)": "investments",
    "lainakanta 31.12.": "loans",
    "henkilötyövuodet": "person_years",
    # balance sheet (quarterly reports)
    "vastaavaa": "balance_total",
    "oma pääoma": "equity",
    "vieras pääoma": "liabilities",
    "edellisten tilikausien ylijäämä (alijäämä)": "past_surplus",
    "pitkäaikainen (korollinen vieras pääoma)": "loans_long",
    "lyhytaikainen (korollinen vieras pääoma)": "loans_short",
    "rahat ja pankkisaamiset": "cash",
    "investointimenot": "investments",
}
# Top-level lines whose sub-lines share a name with another top-level line ("Avustukset").
TOP_ONLY = {"income", "expenses", "operating_margin", "state_funding", "financial", "annual_margin",
            "depreciation", "result", "surplus", "investments", "loans", "person_years",
            "balance_total", "equity", "liabilities"}

BUDGET_COLUMNS = {
    "laadintakauden talousarvio 202x-1 (mukaan lukien talousarviomuutokset)": -1,
    "talousarvio 202x": 0,
    "taloussuunnitelma 202x+1": 1,
    "taloussuunnitelma 202x+2": 2,
}


def norm(name: str | None) -> str:
    """'   4000-4299 Henkilöstökulut' -> 'henkilöstökulut'; 'TILIKAUDEN TULOS' -> 'tilikauden tulos'."""
    s = re.sub(r"\s+", " ", (name or "")).strip().lower()
    s = re.sub(r"^\d{4}(-\d{4})?\s+", "", s)
    return s.removesuffix(", tili").strip()


def line_key(entry: dict[str, Any]) -> str | None:
    key = LINES.get(norm(entry.get("tunnusluku")))
    if key is None:
        return None
    if key in TOP_ONLY and (entry.get("taso") or 1) > 2 and key not in ("equity", "liabilities"):
        return None
    return key


def _number(v: Any) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def extract(report: str, taxonomy: dict[str, dict[str, Any]], values: list[dict[str, Any]]) -> dict[Any, dict[str, float]]:
    """Pick our lines out of one report. Returns {column: {key: value}} where column is a
    year offset for budgets and None for single-column reports."""
    out: dict[Any, dict[str, float]] = {}
    for v in values:
        t = taxonomy.get(str(v.get("tunnusluku")))
        n = _number(v.get("arvo"))
        if not t or n is None:
            continue
        key = line_key(t)
        if not key:
            continue
        col: Any = None
        if report == "HTAS":
            col = BUDGET_COLUMNS.get(norm(t.get("tehtava")))
            if col is None or t.get("palvelu") or t.get("sektori"):
                continue
        elif report == "HTPE":
            # Totals over all service classes, external items only.
            if norm(t.get("sektori") or t.get("tehtava")) != "ulkoiset" or norm(t.get("palvelu")) != "kaikki palvelu- ja tehtäväluokat":
                continue
        else:  # HHKNR: account balances by counterparty sector; "Ulkoiset" is the external total
            if norm(t.get("sektori")) != "ulkoiset" or t.get("palvelu"):
                continue
        bucket = out.setdefault(col, {})
        # Several taxonomy entries can map to one key (e.g. sub-accounts); keep the top-most.
        level = t.get("taso") or 1
        prev = bucket.get(f"_{key}_level")
        if prev is None or level < prev:
            bucket[key] = n
            bucket[f"_{key}_level"] = level
    for bucket in out.values():
        for k in [k for k in bucket if k.startswith("_")]:
            del bucket[k]
    return out


def derive(lines: dict[str, float]) -> dict[str, float]:
    """Fill in totals that account-based reports leave implicit."""
    d = dict(lines)
    if "annual_margin" not in d and "operating_margin" in d:
        d["annual_margin"] = d["operating_margin"] + d.get("state_funding", 0) + d.get("financial", 0)
    if "result" not in d and "annual_margin" in d and "depreciation" in d:
        d["result"] = d["annual_margin"] - d["depreciation"]
    if "loans" not in d and ("loans_long" in d or "loans_short" in d):
        d["loans"] = d.pop("loans_long", 0) + d.pop("loans_short", 0)
    # The balance sheet's accumulated surplus or deficit, including the current period.
    if "past_surplus" in d and "surplus" in d:
        d["cumulative_surplus"] = d["past_surplus"] + d["surplus"]
    return {k: round(v) for k, v in d.items()}


def _latest(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    return max(rows, key=lambda r: r.get("hyvaksymispvm") or "") if rows else None


def _items(doc: Any) -> list[dict[str, Any]]:
    if isinstance(doc, list):
        return doc
    return next((v for v in doc.values() if isinstance(v, list)), [])


def fetch_finances(data_dir: Path, regions: list[str] | None = None, fetcher: Fetcher | None = None,
                   since: int = 2023) -> dict[str, str]:
    """Write data/finances/{region}.json for each county. Reports already on disk with the
    same approval time are not fetched again."""
    fetcher = fetcher or Fetcher(delay=1.0, timeout=180)
    out_dir = data_dir / "finances"
    out_dir.mkdir(parents=True, exist_ok=True)
    listing = _items(fetcher.get(f"{REST}/aineistot").json())
    taxonomies: dict[str, dict[str, dict[str, Any]]] = {}

    def taxonomy(report: str) -> dict[str, dict[str, Any]]:
        if report not in taxonomies:
            entries = fetcher.get(TAXONOMY.format(report=report)).json()
            taxonomies[report] = {str(e["solutunniste"]): e for e in entries}
        return taxonomies[report]

    results: dict[str, str] = {}
    for region, ytunnus in YTUNNUS.items():
        if regions and region not in regions:
            continue
        path = out_dir / f"{region}.json"
        old = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        old_docs = {d["key"]: d for d in old.get("documents", [])}
        try:
            mine = [r for r in listing if r.get("ytunnus") == ytunnus]
            docs: list[dict[str, Any]] = []
            wanted: list[tuple[str, str]] = []
            for report in ("HTAS", "HTPE"):
                periods = sorted({r["raportointikausi"] for r in mine if r["raportointikokonaisuus"] == report})
                wanted += [(report, p) for p in periods if p[:4].isdigit() and int(p[:4]) >= since]
            quarters = sorted({r["raportointikausi"] for r in mine if r["raportointikokonaisuus"] == "HHKNR"})
            quarters = [q for q in quarters if int(q[:4]) >= since]
            years = sorted({q[:4] for q in quarters})
            wanted += [("HHKNR", q) for q in quarters if q.endswith("C12")]
            if quarters and not quarters[-1].endswith("C12"):
                wanted.append(("HHKNR", quarters[-1]))  # the year so far
            for report, period in wanted:
                row = _latest([r for r in mine if r["raportointikokonaisuus"] == report and r["raportointikausi"] == period])
                if not row:
                    continue
                key = f"{report}/{period}"
                prev = old_docs.get(key)
                if prev and prev.get("approved") == row.get("hyvaksymispvm"):
                    docs.append(prev)
                    continue
                values = _items(fetcher.get(row["tunnusluvut"]).json())
                lines = extract(report, taxonomy(report), values)
                docs.append({
                    "key": key, "report": report, "period": period, "stage": row.get("hyvaksymisvaihe"),
                    "approved": row.get("hyvaksymispvm"), "url": row["tunnusluvut"],
                    "columns": {("" if c is None else str(c)): derive(v) for c, v in lines.items()
                                if any(v.values())},
                })
            doc = {
                "region": region, "ytunnus": ytunnus, "source": SOURCE, "api": REST,
                "fetched_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
                "years": years, "documents": sorted(docs, key=lambda d: d["key"]),
            }
            path.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
            results[region] = f"ok ({len(docs)} reports)"
        except Exception as e:  # noqa: BLE001 - one county's failure must not stop the others
            log.exception("finances for %s failed", region)
            results[region] = f"error: {e!r}"
    return results


# Statistics Finland's codes for the counties, in the same order as YTUNNUS.
POPULATION_API = "https://pxdata.stat.fi/PxWeb/api/v1/fi/StatFin/vaerak/11ra.px"
POPULATION_SOURCE = "https://pxdata.stat.fi/PxWeb/pxweb/fi/StatFin/StatFin__vaerak/statfin_vaerak_pxt_11ra.px/"
HVA = {region: f"HVA{i:02d}" for i, region in enumerate(YTUNNUS, start=1)}


def fetch_population(data_dir: Path, fetcher: Fetcher | None = None, since: int = 2022) -> dict[str, Any]:
    """Write data/finances/population.json: residents on 31 Dec and the share aged 65+, per county and year."""
    fetcher = fetcher or Fetcher(delay=1.0, timeout=60)
    meta = fetcher.get(POPULATION_API).json()
    area = next(v["code"] for v in meta["variables"] if "HVA01" in v["values"])
    time = next(v for v in meta["variables"] if v["code"].startswith("timeperiod") or v["text"] == "Vuosi")
    years = [y for y in time["values"] if int(y) >= since]
    query = {"query": [
        {"code": area, "selection": {"filter": "item", "values": list(HVA.values())}},
        {"code": "contentscode", "selection": {"filter": "item", "values": ["vaerak-vaesto", "vaesto_yli64_p"]}},
        {"code": time["code"], "selection": {"filter": "item", "values": years}},
    ], "response": {"format": "json-stat2"}}
    if not fetcher.allowed(POPULATION_API):
        raise PermissionError(POPULATION_API)
    fetcher._wait("pxdata.stat.fi")
    r = fetcher.session.post(POPULATION_API, json=query, timeout=fetcher.timeout)
    r.raise_for_status()
    doc = r.json()
    ids, sizes, dims, values = doc["id"], doc["size"], doc["dimension"], doc["value"]
    idx = {d: dims[d]["category"]["index"] for d in ids}
    idx = {d: (i if isinstance(i, dict) else {c: n for n, c in enumerate(i)}) for d, i in idx.items()}
    strides = [1] * len(sizes)
    for i in range(len(sizes) - 2, -1, -1):
        strides[i] = strides[i + 1] * sizes[i + 1]

    def value(**pos: str) -> Any:
        return values[sum(idx[d][pos[d]] * strides[k] for k, d in enumerate(ids))]

    code_to_region = {c: r for r, c in HVA.items()}
    out: dict[str, Any] = {"source": POPULATION_SOURCE,
                           "fetched_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
                           "regions": {}}
    for code, region in code_to_region.items():
        out["regions"][region] = {
            y: {"population": value(**{area: code, "contentscode": "vaerak-vaesto", time["code"]: y}),
                "over64_share": value(**{area: code, "contentscode": "vaesto_yli64_p", time["code"]: y})}
            for y in years
        }
    (data_dir / "finances").mkdir(parents=True, exist_ok=True)
    (data_dir / "finances" / "population.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return out
