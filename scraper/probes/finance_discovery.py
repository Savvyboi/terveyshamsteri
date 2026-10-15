"""Temporary: run the finance importer for two counties and show what it found and missed."""
import json, subprocess, sys, traceback
sys.path.insert(0, "scraper")
out = open("probe-out.txt", "w", encoding="utf-8")
try:
    r = subprocess.run([sys.executable, "-m", "terveyshamsteri", "finances", "--data", "../probe",
                        "--region", "etela-karjala", "--region", "kainuu"], cwd="scraper", capture_output=True, text=True)
    print("RC", r.returncode, r.stdout[-1500:], r.stderr[-2500:], file=out)
    from terveyshamsteri.finances import REST, TAXONOMY, norm, LINES, _items
    from terveyshamsteri.http import Fetcher
    for reg in ["etela-karjala"]:
        d = json.load(open(f"probe/finances/{reg}.json"))
        for doc in d["documents"]:
            print(doc["key"], doc["stage"], json.dumps(doc["columns"], ensure_ascii=False), file=out)
    # names in the quarterly report we do not map (external totals, top levels)
    f = Fetcher(delay=0.5, timeout=180)
    tax = {str(e["solutunniste"]): e for e in f.get(TAXONOMY.format(report="HHKNR")).json()}
    vals = _items(f.get(f"{REST}/dokumentti/lopullinen/HHKNR/3221313-1/2025C12").json())
    seen = {}
    for v in vals:
        t = tax.get(v["tunnusluku"], {})
        if norm(t.get("sektori")) == "ulkoiset" and (t.get("taso") or 9) <= 4:
            seen[(t.get("osakokonaisuus"), t.get("taso"), norm(t.get("tunnusluku")))] = float(v["arvo"])
    print("\\nHHKNR Ulkoiset lines:", file=out)
    for k, v in sorted(seen.items(), key=lambda kv: (str(kv[0][0]), kv[0][1] or 0)):
        print(("  " if k[2] in LINES else "? ") + f"{k[0]} {k[1]} {k[2]} = {v:.0f}", file=out)
except Exception:
    print("CRASH", traceback.format_exc(), file=out)
out.close()
