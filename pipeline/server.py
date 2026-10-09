#!/usr/bin/env python3
"""Local runner so n8n (even inside Docker) can drive the pipeline over HTTP. No dependencies beyond Python 3.

  python server.py --projects C:\\Users\\you\\Desktop\\YTVideo\\_projects [--host 127.0.0.1] [--port 8787] [--token SECRET]

  GET  /health
  GET  /project?name=ep03            -> {exists, shots:[...], has_music, files:[...]}
  POST /write   {"project":"ep03","files":{"narration.json":{...},"scenes.json":{...}}}   (creates the project from template/ if new)
  POST /run     {"project":"ep03","cmd":"narrate"|"build"|"slides"|"preview"|"render"|"mix"|"package"|"doctor"|"lab-plan"|"lab-build","voicebox":false}
  GET  /file?project=ep03&path=previews/sheet.jpg   (any file inside the project)
  POST /voicebox/ensure {}   -> starts Voicebox if its server is down (Start Menu shortcut, or --voicebox-cmd) and waits until /health answers
Headers: X-Token: <token> when --token is set.  Run commands block until finished (n8n: set a long HTTP timeout).
"""
import argparse, glob, json, os, re, shutil, subprocess, sys, threading, time, urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

HERE = os.path.dirname(os.path.abspath(__file__))
CMDS = {"doctor", "narrate", "build", "slides", "preview", "render", "mix", "package", "lab-plan", "lab-build"}
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


def vb_up(url):
    try:
        urllib.request.urlopen(url.rstrip("/") + "/health", timeout=3).read()
        return True
    except Exception:
        return False


def vb_launch():
    """Start the Voicebox app. --voicebox-cmd wins; otherwise look for its Start Menu shortcut or an installed exe."""
    if ARGS.voicebox_cmd:
        subprocess.Popen(ARGS.voicebox_cmd, shell=True, creationflags=getattr(subprocess, "DETACHED_PROCESS", 0)); return ARGS.voicebox_cmd
    roots = [os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs"), os.path.expandvars(r"%ProgramData%\Microsoft\Windows\Start Menu\Programs")]
    for r in roots:
        for lnk in glob.glob(os.path.join(r, "**", "*oicebox*.lnk"), recursive=True):
            os.startfile(lnk); return lnk
    for pat in (r"%LOCALAPPDATA%\Voicebox\*.exe", r"%LOCALAPPDATA%\Programs\Voicebox\*.exe", r"%ProgramFiles%\Voicebox\*.exe", r"%ProgramFiles(x86)%\Voicebox\*.exe"):
        for exe in glob.glob(os.path.expandvars(pat)):
            if "unins" not in exe.lower():
                subprocess.Popen([exe], creationflags=getattr(subprocess, "DETACHED_PROCESS", 0)); return exe
    raise RuntimeError("Voicebox is not running and I could not find it. Start it by hand once, or restart server.py with --voicebox-cmd \"C:\\path\\to\\Voicebox.exe\"")


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
                return self.reply({"exists": os.path.isdir(d), "has_session": os.path.exists(os.path.join(d, "session.json")) and os.path.exists(os.path.join(d, "recording.webm")), "shots": shots, "has_music": os.path.exists(os.path.join(d, "music.mp3")),
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
            if self.path == "/voicebox/ensure":
                url = body.get("url") or ARGS.voicebox_url
                if vb_up(url): return self.reply({"ok": True, "started": False, "url": url})
                how = vb_launch(); t0 = time.time()
                while time.time() - t0 < ARGS.voicebox_wait:
                    if vb_up(url): return self.reply({"ok": True, "started": True, "via": how, "waited_s": round(time.time() - t0)})
                    time.sleep(3)
                raise RuntimeError("Started Voicebox (%s) but %s/health did not answer within %ds. Open the app and check it finished loading." % (how, url, ARGS.voicebox_wait))
            d = pdir(body.get("project"))
            if self.path == "/write":
                os.makedirs(d, exist_ok=True)   # a Studio session folder may already exist: add what is missing
                for f in ("project.json", "music.mp3"):
                    if not os.path.exists(os.path.join(d, f)):
                        shutil.copy(os.path.join(HERE, "template", f), d)
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
    ap.add_argument("--voicebox-cmd", default=""); ap.add_argument("--voicebox-url", default="http://127.0.0.1:17493"); ap.add_argument("--voicebox-wait", type=int, default=180)
    ARGS = ap.parse_args(); os.makedirs(ARGS.projects, exist_ok=True)
    print(f"AWX pipeline server on http://{ARGS.host}:{ARGS.port}  projects={ARGS.projects}")
    ThreadingHTTPServer((ARGS.host, ARGS.port), H).serve_forever()
