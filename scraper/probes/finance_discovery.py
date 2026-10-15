"""Temporary: reporter names from the non-numeric fields of their reports."""
import json, traceback, urllib.request
R = "https://prodkuntarest.westeurope.cloudapp.azure.com/rest/v1/json"
out = open("probe-out.txt", "w", encoding="utf-8")
def get(u):
    req = urllib.request.Request(u, headers={"User-Agent": "terveyshamsteri-probe"})
    with urllib.request.urlopen(req, timeout=240) as r:
        return json.loads(r.read().decode("utf-8-sig"))
def items(d): return d if isinstance(d, list) else next(v for v in d.values() if isinstance(v, list))
try:
    listing = get(f"{R}/aineistot")["aineistot"]
    ids = sorted({r["ytunnus"] for r in listing if r["raportointikokonaisuus"] == "HHKNR"})
    for y in ids:
        r = next(r for r in listing if r["ytunnus"] == y and r["raportointikokonaisuus"] == "HHKNR" and r["raportointikausi"] == "2025C12")
        texts = []
        for d in items(get(r["tunnusluvut"])):
            a = d.get("arvo") or ""
            try: float(a)
            except ValueError: texts.append(f"{d['tunnusluku']}={a[:80]}")
        print(y, texts[:12], file=out)
except Exception:
    print("CRASH", traceback.format_exc(), file=out)
out.close()
