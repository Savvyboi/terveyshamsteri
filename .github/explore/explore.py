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
t = show(f"{B}/21/356", 6000)
docs = re.findall(r'href="/Kokoukset/ekhva/21/356/(\d+)/view/(\d+)">\s*(\d+)\s', t)
print("DOCS", docs)
for _, doc, num in docs[:1]:
    show(f"{B}/html/{doc}", 25000)
# the item whose vote is in an attachment
m = re.search(r'/21/356/4154/view/(\d+)">\s*\d', t)
if m: show(f"{B}/html/{m.group(1)}", 30000)
show(f"{B}/22", 3000)
