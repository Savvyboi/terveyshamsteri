"""Temporary: what wellbeing-area reports does the State Treasury REST API hold?"""
import json, re, urllib.request
from collections import Counter, defaultdict

R = "https://prodkuntarest.westeurope.cloudapp.azure.com/rest/v1/json"
def get(u, n=80_000_000):
    req = urllib.request.Request(u, headers={"User-Agent": "terveyshamsteri-probe", "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=240) as r:
        return r.read(n).decode("utf-8-sig", "replace")
def note(title, msg):
    print(f"::notice title={title}::" + msg.replace("\n", " ")[:3900])

import sys, traceback
def hook(t, v, tb): note("CRASH", "".join(traceback.format_exception(t, v, tb))[-3000:])
sys.excepthook = hook
rows = json.loads(get(f"{R}/aineistot"))
note("ROWS", f"{len(rows)} keys={sorted(rows[0])}")
h = [r for r in rows if (r.get("raportointikokonaisuus") or "").upper().startswith("H")]
c = Counter((r["raportointikokonaisuus"], r["raportointikausi"][:4]) for r in h)
note("H REPORTS", str(sorted(c.items())))
ids = Counter(r["ytunnus"] for r in h)
note("H YTUNNUS", str(sorted(ids.items())))
stages = Counter(r["hyvaksymisvaihe"] for r in h)
note("H STAGES", str(stages))
pick = defaultdict(list)
for r in h: pick[r["raportointikokonaisuus"]].append(r)
for rep in ["HHTPP", "HTAS", "HHKNR", "HTPE", "HHTPA", "HHTR"]:
    if not pick[rep]: continue
    r = sorted(pick[rep], key=lambda r: r["raportointikausi"])[-1]
    try:
        d = json.loads(get((r.get("tunnusluvut") or next(v for k, v in r.items() if str(v).startswith("http")))))
        items = d if isinstance(d, list) else next((v for v in d.values() if isinstance(v, list)), d)
        note(f"DOC {rep} {r['ytunnus']} {r['raportointikausi']} n={len(items) if isinstance(items, list) else '?'}",
             json.dumps(items[:6] if isinstance(items, list) else items, ensure_ascii=False)[:3800])
    except Exception as e:
        note(f"DOC {rep} ERR", repr(e))
