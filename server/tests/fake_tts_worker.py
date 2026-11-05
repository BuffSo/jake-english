"""Stands in for je_server/tts_worker.py: same line protocol, no model."""
import json
import os
import sys
import time

# argv[1] stands for the TTS module path. "slow-second:<file>" makes the second launch slow to get ready,
# counting launches in <file>, for the restart that times out.
if sys.argv[1].startswith("slow-second:"):
    count = sys.argv[1].split(":", 1)[1]
    n = (int(open(count).read()) if os.path.exists(count) else 0) + 1
    with open(count, "w") as f:
        f.write(str(n))
    if n == 2:
        time.sleep(1.0)
print(json.dumps({"ready": True}), flush=True)
for line in sys.stdin:
    req = json.loads(line)
    log = os.path.join(os.path.dirname(req["out"]), "calls.txt")
    with open(log, "a", encoding="utf-8") as f:
        f.write(req["text"] + "\n")
    with open(os.path.join(os.path.dirname(req["out"]), "rates.txt"), "a", encoding="utf-8") as f:
        f.write(f"{req['voice']} {req['lang']} {req.get('rate')}\n")
    time.sleep(0.05)
    if req["text"] == "FAIL":
        print(json.dumps({"id": req["id"], "ok": False, "error": "RuntimeError"}), flush=True)
        continue
    if req["text"] == "DIE":
        sys.exit(1)
    with open(req["out"], "wb") as f:
        f.write(b"fake")
    print(json.dumps({"id": req["id"], "ok": True, "seconds": 1.0}), flush=True)
