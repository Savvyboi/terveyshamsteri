"""Temporary: text of M-Files PDFs (three files, slowly)."""
import io, time, requests
from pypdf import PdfReader
UA = "terveyshamsteri/0.2 (civic archive of wellbeing services county decisions; +https://github.com/Savvyboi/terveyshamsteri)"
s = requests.Session(); s.headers["User-Agent"] = UA
B = "https://mfiles.ekhva.fi/Kokoukset/ekhva"
for u, n in [(f"{B}/21/356/4154/download/358784", 12000), (f"{B}/21/356/4105/download/358780", 6000),
             (f"{B}/21/356/0/download/365452", 7000), (f"{B}/21/393/5530/download/457063", 5000)]:
    time.sleep(4)
    r = s.get(u, timeout=60)
    print(f"\n######## {u} -> {r.status_code} {r.headers.get('content-type')} {r.headers.get('content-disposition')} len={len(r.content)}")
    try:
        t = "\n".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(r.content)).pages)
        print(t[:n])
    except Exception as e:
        print("PDFERR", e, r.content[:300])
