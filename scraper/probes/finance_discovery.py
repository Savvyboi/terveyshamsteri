"""Temporary: explore Valtiokonttori's Kuntatalous API for wellbeing-area data."""
import json, re, urllib.request

M = "https://vkf-ipa-p-public-apim.data.azure-api.net"
V = "api-version=2022-04-01-preview"
API = "https://api.tutkihallintoa.fi"

def get(u, n=3_000_000):
    req = urllib.request.Request(u, headers={"User-Agent": "terveyshamsteri-probe", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=90) as r:
        return r.read(n).decode("utf-8", "replace")

def note(title, msg):
    print(f"::notice title={title}::" + msg.replace("\n", " ")[:3900])

apis = json.loads(get(f"{M}/apis?{V}&$top=100"))["value"]
k = [a for a in apis if "kunta" in json.dumps(a).lower()]
note("KUNTA APIS", json.dumps(k)[:3900])
for a in k:
    ops = json.loads(get(f"{M}/apis/{a['name']}/operations?{V}&$top=100"))["value"]
    note(f"OPS {a['name']}", " ;; ".join(f"{(o.get('properties') or o).get('method')} {(o.get('properties') or o).get('urlTemplate')} {((o.get('properties') or o).get('description') or '')[:100]}" for o in ops))
    try:
        spec = get(f"{M}/apis/{a['name']}?{V}&export=true&format=openapi%2Bjson")
        note(f"SPEC {a['name']}", spec[:3900])
    except Exception as e:
        note("SPEC ERR", repr(e))
    path = (a.get("properties") or a).get("path") or a.get("path")
    for op in ["taksonomia"]:
        for ver in ["", "/v1", "/v2"]:
            u = f"{API}/{path}{ver}/{op}"
            try:
                t = get(u); note(f"CALL {u}", t[:3900]); break
            except Exception as e:
                note("CALL ERR", f"{u} {e!r}")
