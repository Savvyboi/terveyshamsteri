"""Temporary: run the finance importer for all counties; look for population by wellbeing area."""
import json, subprocess, sys, traceback, urllib.request
out = open("probe-out.txt", "w", encoding="utf-8")
try:
    r = subprocess.run([sys.executable, "-m", "terveyshamsteri", "finances", "--data", "../probe"], cwd="scraper", capture_output=True, text=True)
    print("RC", r.returncode, r.stdout[-2500:], r.stderr[-1500:], file=out)
    import glob
    for f in sorted(glob.glob("probe/finances/*.json")):
        d = json.load(open(f))
        docs = {x["key"]: x for x in d["documents"]}
        a = docs.get("HHKNR/2025C12", {}).get("columns", {}).get("", {})
        b = docs.get("HTAS/2026", {}).get("columns", {}).get("0", {})
        fc = docs.get("HTPE/2026", {}).get("columns", {}).get("", {})
        ytd = [k for k in docs if k.startswith("HHKNR/2026")]
        print(f"{d['region']:18} keys={len(docs)} 2025: exp={a.get('expenses')} state={a.get('state_funding')} surplus={a.get('surplus')} cum={a.get('cumulative_surplus')} loans={a.get('loans')} | 2026 budget surplus={b.get('surplus')} forecast={fc.get('surplus')} ytd={ytd}", file=out)
    # population tables
    api = "https://pxdata.stat.fi/PxWeb/api/v1/fi/StatFin/vaerak"
    tabs = json.load(urllib.request.urlopen(api, timeout=60))
    print("\\nVAERAK:", "; ".join(f"{t['id']}={t['text']}" for t in tabs), file=out)
except Exception:
    print("CRASH", traceback.format_exc(), file=out)
out.close()
