"""Temporary: map State Treasury figure codes to names for wellbeing-area reports."""
import json, sys, traceback, urllib.request
from collections import Counter, defaultdict

R = "https://prodkuntarest.westeurope.cloudapp.azure.com/rest/v1/json"
T = "https://tkdpprodjrpstacc02.blob.core.windows.net/kuntataloudentaksonomia"
def get(u):
    req = urllib.request.Request(u, headers={"User-Agent": "terveyshamsteri-probe"})
    with urllib.request.urlopen(req, timeout=240) as r:
        return json.loads(r.read().decode("utf-8-sig"))
def note(title, msg):
    print(f"::notice title={title}::" + msg.replace("\n", " ")[:3950])
sys.excepthook = lambda t, v, tb: note("CRASH", "".join(traceback.format_exception(t, v, tb))[-3000:])

Y = "3221313-1"
for rep, period, groups in [("HHKNR", "2025C12", None), ("HTAS", "2026", None)]:
    tax = {str(t["solutunniste"]): t for t in get(f"{T}/{rep}.json")}
    doc = get(f"{R}/dokumentti/lopullinen/{rep}/{Y}/{period}")
    if isinstance(doc, dict): doc = next(v for v in doc.values() if isinstance(v, list))
    miss = sum(1 for d in doc if d["tunnusluku"] not in tax)
    by = defaultdict(list)
    for d in doc:
        t = tax.get(d["tunnusluku"], {})
        by[(d["osakokonaisuus"], t.get("tunnusluku_kayttokohde"))].append((t, d))
    note(f"{rep} {period} n={len(doc)} missing={miss}", " ;; ".join(f"{k[0]}|{(k[1] or '')[:90]}|{len(v)}" for k, v in sorted(by.items(), key=lambda kv: str(kv[0]))))
    # the rows with no service/sector breakdown, i.e. the plain statement lines
    for (osa, use), rows in sorted(by.items(), key=lambda kv: str(kv[0])):
        plain = [(t, d) for t, d in rows if not t.get("palvelu") and not t.get("sektori")]
        if not plain: continue
        plain.sort(key=lambda td: (td[0].get("tehtava_jarjestys") or 0, td[0].get("tunnusluku_jarjestys") or 0))
        s = " ;; ".join(f"{d['tunnusluku']}={t.get('tunnusluku_sisennys') or t.get('tunnusluku')}[{(t.get('tehtava') or '')[:40]}]:{float(d['arvo']):.0f}" for t, d in plain)
        for i in range(0, min(len(s), 7800), 3900):
            note(f"{rep} {osa} {(use or '')[:50]} ({len(plain)}) {i}", s[i:i + 3900])
