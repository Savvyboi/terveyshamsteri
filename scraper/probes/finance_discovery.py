"""Temporary: list the State Treasury REST endpoints and try the wellbeing-area ones."""
import json, re, urllib.request
from collections import Counter

R = "https://prodkuntarest.westeurope.cloudapp.azure.com"
def get(u, n=60_000_000):
    req = urllib.request.Request(u, headers={"User-Agent": "terveyshamsteri-probe", "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=180) as r:
        return r.read(n).decode("utf-8", "replace")
def note(title, msg):
    print(f"::notice title={title}::" + msg.replace("\n", " ")[:3900])

home = get(R + "/")
eps = sorted(set(re.findall(r"/rest/(?:&lt;versio&gt;|v1)/(?:&lt;formaatti&gt;|json)/([a-z0-9-]+)", home)))
note("ENDPOINTS", " ".join(eps))
text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", home))
note("HOME TEXT", text[:3900])
note("HOME TEXT 2", text[3900:7800])
for ep in [e for e in eps if e.endswith("aineistot")] + ["hhtpp-aineistot", "htas-aineistot", "hhtr-aineistot", "hhkr-aineistot", "hhknr-aineistot", "htpe-aineistot", "hhtpa-aineistot"]:
    try:
        d = json.loads(get(f"{R}/rest/v1/json/{ep}"))
        rows = d if isinstance(d, list) else next((v for v in d.values() if isinstance(v, list)), [])
        c = Counter((r.get("raportointikokonaisuus"), r.get("raportointikausi")) for r in rows)
        note(f"{ep} ({len(rows)})", f"{sorted(c.items())[-40:]} first={json.dumps(rows[:2], ensure_ascii=False)[:900]}")
    except Exception as e:
        note(f"{ep} ERR", repr(e))
