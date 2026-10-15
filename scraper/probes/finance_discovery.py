"""Temporary: run the full finance import and emit the result as base64 tar.gz."""
import base64, io, subprocess, sys, tarfile, traceback
out = open("probe-out.txt", "w", encoding="utf-8")
try:
    r = subprocess.run([sys.executable, "-m", "terveyshamsteri", "finances", "--data", "../probe"], cwd="scraper", capture_output=True, text=True)
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as t:
        t.add("probe/finances", arcname="finances")
        t.add("probe/population.json", arcname="population.json")
    print("B64" + base64.b64encode(buf.getvalue()).decode() + "END", file=out)
    print("RC", r.returncode, r.stdout[-1500:], r.stderr[-500:], file=out)
except Exception:
    print("CRASH", traceback.format_exc(), file=out)
out.close()
