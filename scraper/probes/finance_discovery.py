"""Temporary: run the finance importer (2 counties) and print population."""
import json, subprocess, sys, traceback
out = open("probe-out.txt", "w", encoding="utf-8")
try:
    r = subprocess.run([sys.executable, "-m", "terveyshamsteri", "finances", "--data", "../probe", "--region", "kainuu", "--region", "pirkanmaa"], cwd="scraper", capture_output=True, text=True)
    print("RC", r.returncode, r.stdout[-1500:], r.stderr[-2500:], file=out)
    print(open("probe/population.json").read()[:3000], file=out)
except Exception:
    print("CRASH", traceback.format_exc(), file=out)
out.close()
