"""Stands in for je_server/tts_worker.py: same line protocol, no model."""
import json
import os
import sys
import time

print(json.dumps({"ready": True}), flush=True)
for line in sys.stdin:
    req = json.loads(line)
    log = os.path.join(os.path.dirname(req["out"]), "calls.txt")
    with open(log, "a", encoding="utf-8") as f:
        f.write(req["text"] + "\n")
    with open(os.path.join(os.path.dirname(req["out"]), "rates.txt"), "a", encoding="utf-8") as f:
        f.write(f"{req['lang']} {req.get('rate')}\n")
    time.sleep(0.05)
    if req["text"] == "FAIL":
        print(json.dumps({"id": req["id"], "ok": False, "error": "RuntimeError"}), flush=True)
        continue
    if req["text"] == "DIE":
        sys.exit(1)
    with open(req["out"], "wb") as f:
        f.write(b"fake")
    print(json.dumps({"id": req["id"], "ok": True, "seconds": 1.0}), flush=True)
