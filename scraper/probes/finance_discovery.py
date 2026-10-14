"""Temporary: find Statistics Finland tables on wellbeing services county finances."""
import json, re, sys, urllib.request

API = "https://pxdata.stat.fi/PxWeb/api/v1/fi/StatFin"
def get(u):
    with urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "terveyshamsteri-probe"}), timeout=60) as r:
        return json.load(r)

dbs = get(API)
hits = [d for d in dbs if re.search(r"hyvinvointi|kunt|julkis|sosiaali|terveyd", d["text"], re.I)]
print("::notice title=DBS::" + "; ".join(f"{d['id']}={d['text']}" for d in hits))
for d in hits:
    try:
        tabs = get(f"{API}/{d['id']}")
    except Exception as e:
        print(f"::notice title=DB {d['id']}::error {e}"); continue
    rel = [t for t in tabs if re.search(r"hyvinvointialue", t["text"], re.I)] or tabs[:6]
    msg = "; ".join(f"{t['id']}={t['text']}" for t in rel)[:3500]
    print(f"::notice title=DB {d['id']} ({len(tabs)})::{msg}")
