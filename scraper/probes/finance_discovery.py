"""Temporary: names for the Y-tunnus of wellbeing-area reporters (PRH open data)."""
import json, traceback, urllib.request
out = open("probe-out.txt", "w", encoding="utf-8")
IDS = ['0201256-6', '1567535-0', '2126106-6', '2483868-4', '3221065-1', '3221304-3', '3221307-8', '3221308-6', '3221309-4', '3221311-5', '3221313-1', '3221315-8', '3221316-6', '3221317-4', '3221318-2', '3221323-8', '3221324-6', '3221325-4', '3221326-2', '3221331-8', '3221332-6', '3221339-3', '3221340-6', '3221347-3', '3221356-1']
for y in IDS:
    try:
        req = urllib.request.Request(f"https://avoindata.prh.fi/opendata-ytj-api/v3/companies?businessId={y}", headers={"User-Agent": "terveyshamsteri-probe"})
        d = json.load(urllib.request.urlopen(req, timeout=60))
        names = [n["name"] for c in d.get("companies", []) for n in c.get("names", []) if not n.get("endDate")]
        print(y, names, file=out)
    except Exception as e:
        print(y, "ERR", repr(e)[:200], file=out)
out.close()
