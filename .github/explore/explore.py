"""Temporary: look at M-Files item pages (a few pages, slowly)."""
import re, time, requests
from urllib.parse import urljoin
UA = "terveyshamsteri/0.2 (civic archive of wellbeing services county decisions; +https://github.com/Savvyboi/terveyshamsteri)"
s = requests.Session(); s.headers["User-Agent"] = UA
def show(u, full=20000):
    time.sleep(3)
    r = s.get(u, timeout=40)
    if not r.encoding or r.encoding.lower() == "iso-8859-1":
        r.encoding = r.apparent_encoding
    print(f"\n######## {u} -> {r.status_code} {r.headers.get('content-type')} len={len(r.content)} enc={r.encoding}")
    print(r.text[:full])
    return r.text
B = "https://mfiles.ekhva.fi/Kokoukset/ekhva"
show(f"{B}/html/358784", 40000)
show(f"{B}/html/358780", 15000)
show(f"{B}/21/356/4154/view/365454", 3000)
show(f"{B}/22/391/5514/view/451531", 3000)
