"""Temporary: list the APIs in Valtiokonttori's Azure API Management developer portal."""
import json, re, urllib.request

def get(u, n=2_000_000):
    req = urllib.request.Request(u, headers={"User-Agent": "terveyshamsteri-probe", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read(n).decode("utf-8", "replace")

def note(title, msg):
    print(f"::notice title={title}::" + msg.replace("\n", " ")[:3800])

base = "https://avoindata.tutkihallintoa.fi"
cfg = {}
for p in ["/config.json", "/config.design.json"]:
    try:
        t = get(base + p); note("CFG " + p, t[:1500]); cfg.update(json.loads(t))
    except Exception as e:
        note("CFG ERR", f"{p} {e!r}")
mgmt = cfg.get("managementApiUrl") or cfg.get("backendUrl") or ""
apis = None
for u in [f"{mgmt}/apis?api-version=2022-04-01-preview", f"{mgmt}/apis?api-version=2021-08-01",
          f"{mgmt}/developer/apis?api-version=2022-04-01-preview", f"{base}/developer/apis?api-version=2022-04-01-preview",
          f"{mgmt}/subscriptions/sid/resourceGroups/rg/providers/Microsoft.ApiManagement/service/sid/apis?api-version=2022-04-01-preview"]:
    try:
        t = get(u); d = json.loads(t)
        apis = d.get("value", d)
        note("APIS OK", u); break
    except Exception as e:
        note("APIS ERR", f"{u} {e!r}")
if apis:
    rows = []
    for a in apis:
        pr = a.get("properties", a)
        rows.append(f"{a.get('name')}|{pr.get('displayName')}|path={pr.get('path')}|{(pr.get('description') or '')[:80]}")
    for i in range(0, len(rows), 25):
        note(f"API LIST {i}", " ;; ".join(rows[i:i + 25]))
    for a in apis:
        pr = a.get("properties", a)
        if re.search(r"hyvinvointi|kunta|wellbeing|municipal", json.dumps(pr), re.I):
            try:
                ops = json.loads(get(f"{mgmt}/apis/{a['name']}/operations?api-version=2022-04-01-preview"))
                note(f"OPS {a['name']}", " ;; ".join(f"{o.get('properties',o).get('method')} {o.get('properties',o).get('urlTemplate')}" for o in ops.get("value", []))[:3800])
            except Exception as e:
                note(f"OPS ERR {a['name']}", repr(e))
