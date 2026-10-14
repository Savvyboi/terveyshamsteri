"""Temporary: map State Treasury figure codes to names for wellbeing-area reports."""
import json, traceback, urllib.request
from collections import defaultdict

R = "https://prodkuntarest.westeurope.cloudapp.azure.com/rest/v1/json"
T = "https://tkdpprodjrpstacc02.blob.core.windows.net/kuntataloudentaksonomia"
out = open("probe-out.txt", "w", encoding="utf-8")
def get(u):
    req = urllib.request.Request(u, headers={"User-Agent": "terveyshamsteri-probe"})
    with urllib.request.urlopen(req, timeout=240) as r:
        return json.loads(r.read().decode("utf-8-sig"))
def p(*a): print(*a, file=out)

try:
    listing = get(f"{R}/aineistot")["aineistot"]
    Y = "3221313-1"
    for rep, period in [("HHKNR", "2025C12"), ("HTAS", "2026"), ("HTPE", "2026"), ("HHTPA", "2025")]:
        row = next(r for r in listing if r["ytunnus"] == Y and r["raportointikokonaisuus"] == rep and r["raportointikausi"] == period)
        tax = {str(t["solutunniste"]): t for t in get(f"{T}/{rep}.json")}
        doc = get(row["tunnusluvut"])
        if isinstance(doc, dict): doc = next(v for v in doc.values() if isinstance(v, list))
        p(f"\n##### {rep} {period} {row['tunnusluvut']} n={len(doc)}")
        groups = defaultdict(list)
        for d in doc:
            t = tax.get(d["tunnusluku"], {})
            groups[(d["osakokonaisuus"], t.get("tunnusluku_kayttokohde"))].append((t, d))
        for (osa, use), rows in sorted(groups.items(), key=lambda kv: str(kv[0])):
            p(f"\n=== {osa} | {use} | {len(rows)}")
            rows.sort(key=lambda td: (td[0].get("tehtava_jarjestys") or 0, td[0].get("tunnusluku_jarjestys") or 0))
            for t, d in rows:
                v = float(d["arvo"] or 0)
                if v == 0: continue
                dims = "/".join(filter(None, [t.get("tehtava"), t.get("sektori"), t.get("palvelu")]))[:70]
                p(f"{d['tunnusluku']}\t{t.get('taso')}\t{(t.get('tunnusluku_sisennys') or t.get('tunnusluku') or '?')[:60]}\t{dims}\t{v:.0f}")
except Exception:
    p("CRASH " + traceback.format_exc())
out.close()
print(open("probe-out.txt").read()[:300])
