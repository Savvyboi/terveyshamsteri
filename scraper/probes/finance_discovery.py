"""Temporary: find the total-sector lines in quarterly reports (HHKNR) and HTPE/HTAS line codes across counties."""
import json, traceback, urllib.request
from collections import Counter, defaultdict

R = "https://prodkuntarest.westeurope.cloudapp.azure.com/rest/v1/json"
T = "https://tkdpprodjrpstacc02.blob.core.windows.net/kuntataloudentaksonomia"
out = open("probe-out.txt", "w", encoding="utf-8")
def get(u):
    req = urllib.request.Request(u, headers={"User-Agent": "terveyshamsteri-probe"})
    with urllib.request.urlopen(req, timeout=240) as r:
        return json.loads(r.read().decode("utf-8-sig"))
def p(*a): print(*a, file=out)
def items(d): return d if isinstance(d, list) else next(v for v in d.values() if isinstance(v, list))

try:
    listing = get(f"{R}/aineistot")["aineistot"]
    tax = {str(t["solutunniste"]): t for t in get(f"{T}/HHKNR.json")}
    p("SEKTORI values:", Counter(t.get("sektori") for t in tax.values()).most_common(60))
    p("TEHTAVA values:", Counter(t.get("tehtava") for t in tax.values()).most_common(20))
    p("KAYTTOKOHDE:", Counter(t.get("tunnusluku_kayttokohde") for t in tax.values()).most_common(20))
    for c in ["5752390", "3319283", "3418067", "1562", "699", "7241339", "6652982", "6854040"]:
        t = tax.get(c, {})
        p("CODE", c, json.dumps({k: t.get(k) for k in ("taso", "tunnusluku", "tehtava", "sektori", "palvelu", "tekstitunniste", "osakokonaisuus")}, ensure_ascii=False))
    Y = "3221313-1"
    row = next(r for r in listing if r["ytunnus"] == Y and r["raportointikokonaisuus"] == "HHKNR" and r["raportointikausi"] == "2025C12")
    doc = items(get(row["tunnusluvut"]))
    vals = {d["tunnusluku"]: float(d["arvo"] or 0) for d in doc}
    # lines whose sector is a total
    p("\nTOTAL-ISH LINES (sektori None or containing 'yhteensä'/'Kaikki'):")
    for code, v in vals.items():
        t = tax.get(code, {})
        s = (t.get("sektori") or "")
        if v and (not s or "yhteens" in s.lower() or "kaikki" in s.lower() or s.lower().startswith("sektori")):
            p(f"{code}\t{t.get('osakokonaisuus')}\t{t.get('taso')}\t{(t.get('tunnusluku_sisennys') or '')[:60]}\t{s[:60]}\t{v:.0f}")
    # h-t09 balance-sheet level-1 lines with sectors
    p("\nBALANCE level<=2:")
    for code, v in vals.items():
        t = tax.get(code, {})
        if t.get("osakokonaisuus") == "h-t09" and (t.get("taso") or 9) <= 2 and v:
            p(f"{code}\t{t.get('taso')}\t{(t.get('tunnusluku_sisennys') or '')[:60]}\t{(t.get('sektori') or '')[:60]}\t{v:.0f}")
    # Are HTAS codes the same across counties and years?
    seen = defaultdict(set)
    for r in listing:
        if r["raportointikokonaisuus"] == "HTAS" and r["raportointikausi"] in ("2025", "2026") and r["ytunnus"] in ("3221313-1", "3221356-1"):
            for d in items(get(r["tunnusluvut"])):
                seen[(r["raportointikausi"], r["ytunnus"])].add(d["tunnusluku"])
    ks = list(seen)
    p("\nHTAS code overlap:", {str(k): len(v) for k, v in seen.items()}, "common all:", len(set.intersection(*seen.values())) if seen else 0)
    t5 = get(f"{T}/HTAS.json")
    p("HTAS tax size", len(t5), "TEHTAVA:", Counter(t.get("tehtava") for t in t5).most_common(10), "versio:", Counter((t.get("versio"), t.get("tekninen_versio")) for t in t5).most_common(10))
except Exception:
    p("CRASH " + traceback.format_exc())
out.close()
