"""Temporary: population by wellbeing services county from Statistics Finland."""
import json, traceback, urllib.request
out = open("probe-out.txt", "w", encoding="utf-8")
try:
    u = "https://pxdata.stat.fi/PxWeb/api/v1/fi/StatFin/vaerak/statfin_vaerak_pxt_11ra.px"
    meta = json.load(urllib.request.urlopen(u, timeout=60))
    for v in meta["variables"]:
        vals = list(zip(v["values"], v["valueTexts"]))
        hv = [x for x in vals if "hyvinvointi" in x[1].lower() or x[0].startswith("HV")]
        print(v["code"], v["text"], len(vals), vals[:8], "HV:", hv[:30], file=out)
except Exception:
    print("CRASH", traceback.format_exc(), file=out)
out.close()
