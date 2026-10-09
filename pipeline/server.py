#!/usr/bin/env python3
"""Local runner so n8n (even inside Docker) can drive the pipeline over HTTP. No dependencies beyond Python 3.

  python server.py --projects C:\\Users\\you\\Desktop\\YTVideo\\_projects [--host 127.0.0.1] [--port 8787] [--token SECRET]

  GET  /health
  GET  /project?name=ep03            -> {exists, shots:[...], has_music, files:[...]}
  POST /write   {"project":"ep03","files":{"narration.json":{...},"scenes.json":{...}}}   (creates the project from template/ if new)
  POST /run     {"project":"ep03","cmd":"narrate"|"build"|"slides"|"preview"|"render"|"mix"|"package"|"doctor","voicebox":false}
  GET  /file?project=ep03&path=previews/sheet.jpg   (any file inside the project)
Headers: X-Token: <token> when --token is set.  Run commands block until finished (n8n: set a long HTTP timeout).
"""
import argparse, json, os, re, shutil, subprocess, sys, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

HERE = os.path.dirname(os.path.abspath(__file__))
CMDS = {"doctor", "narrate", "build", "slides", "preview", "render", "mix", "package"}
LOCK = threading.Lock()  # one pipeline job at a time (Voicebox queue and CPU are shared)
ARGS = None


def pdir(name):
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,60}", name or "") or name in (".", ".."):
        raise ValueError("bad project name")
    return os.path.join(ARGS.projects, name)


def safe_in(root, rel):
    p = os.path.abspath(os.path.join(root, rel))
    if not p.startswith(os.path.abspath(root) + os.sep):
        raise ValueError("path escapes project")
    return p


class H(BaseHTTPRequestHandler):
    def log_message(self, f, *a):
        sys.stderr.write("[server] " + f % a + "\n")

    def reply(self, obj, code=200, raw=None, ctype="application/json"):
        b = raw if raw is not None else json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code); self.send_header("Content-Type", ctype); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)

    def authed(self):
        if ARGS.token and self.headers.get("X-Token") != ARGS.token:
            self.reply({"error": "bad token"}, 401); return False
        return True

    def do_GET(self):
        if not self.authed(): return
        u = urlparse(self.path); q = {k: v[0] for k, v in parse_qs(u.query).items()}
        try:
            if u.path == "/health":
                return self.reply({"ok": True, "projects": ARGS.projects})
            if u.path == "/project":
                d = pdir(q.get("name"))
                shots = sorted(os.listdir(os.path.join(d, "shots"))) if os.path.isdir(os.path.join(d, "shots")) else []
                return self.reply({"exists": os.path.isdir(d), "shots": shots, "has_music": os.path.exists(os.path.join(d, "music.mp3")),
                                   "files": sorted(os.listdir(d)) if os.path.isdir(d) else []})
            if u.path == "/file":
                p = safe_in(pdir(q.get("project")), q.get("path", ""))
                ct = {"jpg": "image/jpeg", "png": "image/png", "mp4": "video/mp4", "json": "application/json", "srt": "text/plain", "txt": "text/plain"}.get(p.rsplit(".", 1)[-1], "application/octet-stream")
                return self.reply(None, raw=open(p, "rb").read(), ctype=ct)
            self.reply({"error": "not found"}, 404)
        except Exception as e:
            self.reply({"error": str(e)}, 400)

    def do_POST(self):
        if not self.authed(): return
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
            d = pdir(body.get("project"))
            if self.path == "/write":
                if not os.path.isdir(d):
                    os.makedirs(d); shutil.copy(os.path.join(HERE, "template", "project.json"), d); shutil.copy(os.path.join(HERE, "template", "music.mp3"), d)
                    os.makedirs(os.path.join(d, "shots"), exist_ok=True)
                for name, content in body["files"].items():
                    if name not in ("narration.json", "scenes.json", "project.json"):
                        raise ValueError("only narration.json / scenes.json / project.json may be written")
                    json.dump(content, open(os.path.join(d, name), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
                return self.reply({"ok": True, "project": d})
            if self.path == "/run":
                cmd = body.get("cmd")
                if cmd not in CMDS: raise ValueError("unknown cmd")
                args = [sys.executable, os.path.join(HERE, "awxvideo.py"), cmd, d]
                if cmd == "doctor" and body.get("voicebox"): args.append("--voicebox")
                with LOCK:
                    r = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace")
                lines = [l for l in r.stdout.splitlines() if l.strip().startswith("{")]
                try: result = json.loads(lines[-1]) if lines else {}
                except Exception: result = {}
                return self.reply({"exit_code": r.returncode, "result": result, "status": result.get("status", "fail" if r.returncode else "ok"), "log_tail": (r.stdout + r.stderr)[-3000:]})
            self.reply({"error": "not found"}, 404)
        except Exception as e:
            self.reply({"error": str(e)}, 400)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--projects", required=True); ap.add_argument("--host", default="127.0.0.1"); ap.add_argument("--port", type=int, default=8787); ap.add_argument("--token", default="")
    ARGS = ap.parse_args(); os.makedirs(ARGS.projects, exist_ok=True)
    print(f"AWX pipeline server on http://{ARGS.host}:{ARGS.port}  projects={ARGS.projects}")
    ThreadingHTTPServer((ARGS.host, ARGS.port), H).serve_forever()
