"""Print chunks [a, b) of probe-out.txt as notices (Actions allows ~10 per step)."""
import sys
text = open("probe-out.txt", encoding="utf-8").read()
a, b = int(sys.argv[1]), int(sys.argv[2])
for i in range(a, b):
    chunk = text[i * 3900:(i + 1) * 3900]
    if chunk:
        print(f"::notice title=P{i:03d}::" + chunk.replace("\n", "⏎").replace("%", "%25"))
