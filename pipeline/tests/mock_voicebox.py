#!/usr/bin/env python3
"""Tiny fake Voicebox for testing awxvideo.py narrate without the real server.
  python mock_voicebox.py <narration.json> <generations.json> <voice_dir> [port]
Serves real clips (from a finished episode) for the matching text. Seed 42 'mishears' sentence #5 to exercise the retry path."""
import json, os, sys, uuid
from http.server import BaseHTTPRequestHandler, HTTPServer

_n = json.load(open(sys.argv[1])); S = [t for g in _n["segments"] for t in g["sentences"]]; G = {g["i"]: g["id"] for g in json.load(open(sys.argv[2]))}; VD = sys.argv[3]
PORT = int(sys.argv[4]) if len(sys.argv) > 4 else 17999
WAV = {i: open(os.path.join(VD, G[i] + ".wav"), "rb").read() for i in G}
JOBS = {}


class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def send(self, obj, code=200, raw=None):
        b = raw if raw is not None else json.dumps(obj).encode()
        self.send_response(code); self.send_header("Content-Type", "audio/wav" if raw else "application/json"); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)

    def do_GET(self):
        p = self.path
        if p == "/health": return self.send({"status": "healthy"})
        if p == "/profiles": return self.send([{"id": "p1", "name": "Venu"}])
        if p.startswith("/history/"):
            j = JOBS[p.split("/")[-1]]; j["polls"] += 1
            return self.send({"id": j["id"], "status": "generating" if j["polls"] < 2 else "completed"})
        if p.startswith("/audio/"): return self.send(None, raw=WAV[JOBS[p.split("/")[-1]]["idx"]])
        self.send({}, 404)

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0)); body = self.rfile.read(n)
        if self.path == "/generate":
            r = json.loads(body); idx = S.index(r["text"]); gid = str(uuid.uuid4())
            JOBS[gid] = {"id": gid, "idx": idx, "seed": r["seed"], "polls": 0}
            return self.send({"id": gid, "status": "generating"})
        if self.path == "/transcribe":
            for i, w in WAV.items():
                if w in body:
                    t = S[i]
                    if i == 5 and b"RIFF" in body and JOBS and any(j["seed"] == 42 and j["idx"] == 5 for j in JOBS.values()) and not getattr(H, "fixed", False):
                        H.fixed = True; t = "Network adapter one is host only so your PC can reach AWX adapter two is for internet"
                    return self.send({"text": t})
            return self.send({"text": ""})
        self.send({}, 404)


HTTPServer(("127.0.0.1", PORT), H).serve_forever()
