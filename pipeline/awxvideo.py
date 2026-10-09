#!/usr/bin/env python3
"""AWX from Zero - episode pipeline CLI (the same stages used to make Ep 1 and Ep 2).

  python awxvideo.py doctor   <project> [--voicebox]
  python awxvideo.py narrate  <project> [--strict]      Voicebox clip per sentence -> Whisper check -> seed retries -> verify_report.json
  python awxvideo.py build    <project>                  voiceover_raw.wav, sentence_times.json, timeline.json, video.srt, chapters.txt
  python awxvideo.py slides   <project>                  slides/*.png from scenes.json
  python awxvideo.py preview  <project>                  previews/*.jpg + previews/sheet.jpg (look at these before the long render)
  python awxvideo.py render   <project>                  final_silent.mp4 (resumable, rendered in parts)
  python awxvideo.py mix      <project>                  loudnorm voice + ducked music -> <output_name>.mp4
  python awxvideo.py package  <project>                  .srt + youtube_description.txt next to the mp4
  python awxvideo.py lab-plan <project>                  LAB episodes: Studio session -> edit/edited.mp4 (cuts, retakes, time-lapses, callouts) + lab_steps.json + narration.json
  python awxvideo.py lab-build <project>                 LAB: title card + edited video (freeze-frame holds so each step's narration fits) + end card, voice placed per step
  python awxvideo.py all      <project>                  narrate, build, slides, render, mix, package
Every command ends with one JSON line (status + paths) so n8n can read it.

<project> folder: project.json, narration.json, scenes.json, music.mp3, shots/ (browser screenshots).
"""
import argparse, difflib, hashlib, json, math, os, re, shutil, subprocess, sys, time, wave
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
SR = 24000
FPS = 30


def jl(path):
    return json.load(open(path, encoding="utf-8"))


def jd(obj, path):
    json.dump(obj, open(path, "w", encoding="utf-8"), indent=1, ensure_ascii=False)


def out(status, **kw):
    print(json.dumps({"status": status, **kw}, ensure_ascii=False))


class P:
    def __init__(self, d):
        self.d = os.path.abspath(d)
        if os.path.isdir(self.d):
            tpl = os.path.join(HERE, "template")
            for f in ("project.json", "music.mp3"):   # Studio session folders start without these
                if not os.path.exists(self.p(f)) and os.path.exists(os.path.join(tpl, f)):
                    shutil.copy(os.path.join(tpl, f), self.p(f))
        self.cfg = jl(self.p("project.json"))
        self.narr = jl(self.p("narration.json")) if os.path.exists(self.p("narration.json")) else {"segments": []}
        self.spec = jl(self.p("scenes.json")) if os.path.exists(self.p("scenes.json")) else {}

    def p(self, *a):
        return os.path.join(self.d, *a)

    @property
    def sentences(self):
        return [(seg["id"], i, t) for seg in self.narr["segments"] for i, t in enumerate(seg["sentences"])]


# ------------------------------------------------------------------ doctor
def cmd_doctor(pr, a):
    import importlib
    res = {}
    for m in ("numpy", "cv2", "PIL", "requests"):
        try:
            importlib.import_module(m); res[m] = "ok"
        except Exception as e:
            res[m] = f"MISSING ({e})"
    for b in ("ffmpeg", "ffprobe"):
        res[b] = shutil.which(b) or "MISSING"
    res["fonts"] = "ok" if all(os.path.exists(os.path.join(HERE, "fonts", f)) for f in ("Inter-Regular.otf", "Inter-SemiBold.otf", "Inter-Bold.otf", "DejaVuSansMono.ttf")) else "MISSING"
    res["music"] = "ok" if os.path.exists(pr.p(pr.cfg.get("music", "music.mp3"))) else "MISSING (mix will be voice only)"
    if a.voicebox:
        try:
            vb = VB(pr.cfg["voicebox"])
            res["voicebox"] = vb.health()
            res["voicebox_profile"] = vb.profile_id()
        except Exception as e:
            res["voicebox"] = f"UNREACHABLE: {e}"
    bad = [k for k, v in res.items() if "MISSING" in str(v) or "UNREACHABLE" in str(v)]
    out("fail" if bad else "ok", checks=res, problems=bad)
    return 1 if bad else 0


# ------------------------------------------------------------------ Voicebox
class VB:
    def __init__(self, c):
        import requests
        self.r = requests
        self.c = c
        self.url = c.get("url", "http://127.0.0.1:17493").rstrip("/")
        self._pid = None

    def health(self):
        return self.r.get(self.url + "/health", timeout=10).json()

    def profile_id(self):
        if self._pid:
            return self._pid
        want = self.c.get("profile", "Venu").lower()
        ps = self.r.get(self.url + "/profiles", timeout=20).json()
        for p in ps:
            if p["name"].lower() == want:
                self._pid = p["id"]
                return self._pid
        raise SystemExit(f"Voicebox profile '{self.c.get('profile')}' not found. Have: {[p['name'] for p in ps]}")

    def generate(self, text, seed, dest):
        body = {"profile_id": self.profile_id(), "text": text, "language": self.c.get("language", "en"), "seed": seed,
                "model_size": self.c.get("model_size", "0.6B"), "engine": self.c.get("engine", "qwen")}
        body.update(self.c.get("extra", {}))
        g = self.r.post(self.url + "/generate", json=body, timeout=60)
        g.raise_for_status()
        gid = g.json()["id"]
        t0 = time.time()
        tmo = self.c.get("timeout_s", 240)
        while True:
            h = self.r.get(f"{self.url}/history/{gid}", timeout=20).json()
            st = h.get("status", "completed")
            if st == "completed":
                break
            if st in ("failed", "cancelled", "error"):
                raise RuntimeError(f"generation {gid} {st}: {h.get('error')}")
            if time.time() - t0 > tmo:
                try:
                    self.r.post(f"{self.url}/generate/{gid}/cancel", timeout=10)
                except Exception:
                    pass
                raise TimeoutError(f"generation {gid} still '{st}' after {tmo}s (queue blocked? check Voicebox)")
            time.sleep(1.0)
        a = self.r.get(f"{self.url}/audio/{gid}", timeout=60)
        a.raise_for_status()
        open(dest, "wb").write(a.content)
        return gid

    def transcribe(self, path):
        with open(path, "rb") as f:
            r = self.r.post(self.url + "/transcribe", files={"file": (os.path.basename(path), f, "audio/wav")}, timeout=180)
        r.raise_for_status()
        j = r.json()
        return j.get("text", "") if isinstance(j, dict) else str(j)


NUM = {"0": "zero", "1": "one", "2": "two", "3": "three", "4": "four", "5": "five", "6": "six", "7": "seven", "8": "eight", "9": "nine"}


def norm_words(s):
    s = s.lower().replace("-", " ").replace("’", "'")
    s = re.sub(r"[^a-z0-9' ]", " ", s)
    w = []
    for tok in s.split():
        if tok.isdigit():
            w += [NUM[c] for c in tok]
        else:
            w.append(tok)
    return w


def score(expected, heard):
    a, b = norm_words(expected), norm_words(heard)
    if not a:
        return 1.0
    return difflib.SequenceMatcher(None, a, b).ratio()


def cmd_narrate(pr, a):
    vd = pr.p("voice")
    os.makedirs(vd, exist_ok=True)
    gp = pr.p("generations.json")
    gens = {g["i"]: g for g in (jl(gp) if os.path.exists(gp) else [])}
    vb = VB(pr.cfg["voicebox"])
    vb.health()
    seeds = pr.cfg["voicebox"].get("seeds", [42, 7, 1234, 99])
    thr = pr.cfg["voicebox"].get("threshold", 0.9)
    report, flagged = [], []
    for k, (seg, i, text) in enumerate(pr.sentences):
        h = hashlib.sha1(text.encode()).hexdigest()[:10]
        old = gens.get(k)
        if old and old.get("hash") == h and os.path.exists(os.path.join(vd, old["id"] + ".wav")):
            report.append({"k": k, "seg": seg, "i": i, "text": text, "heard": old.get("heard", ""), "score": old.get("score", 1.0), "status": old.get("status", "ok"), "attempts": 0, "cached": True})
            if old.get("status") == "flagged":
                flagged.append(k)
            continue
        best = None
        tries = []
        for seed in seeds:
            tmp = os.path.join(vd, f"_tmp_{k}_{seed}.wav")
            try:
                gid = vb.generate(text, seed, tmp)
                heard = vb.transcribe(tmp)
            except Exception as e:
                tries.append({"seed": seed, "error": str(e)})
                continue
            sc = score(text, heard)
            tries.append({"seed": seed, "score": round(sc, 3), "heard": heard})
            fn = os.path.join(vd, gid + ".wav")
            os.replace(tmp, fn)
            if best is None or sc > best["score"]:
                best = {"id": gid, "score": sc, "heard": heard, "seed": seed}
            if sc >= thr:
                break
        if best is None:
            report.append({"k": k, "seg": seg, "i": i, "text": text, "status": "failed", "tries": tries})
            flagged.append(k)
            continue
        status = "ok" if best["score"] >= thr else "flagged"
        if status == "flagged":
            flagged.append(k)
        gens[k] = {"i": k, "id": best["id"], "hash": h, "score": round(best["score"], 3), "heard": best["heard"], "status": status}
        jd([gens[x] for x in sorted(gens)], gp)
        report.append({"k": k, "seg": seg, "i": i, "text": text, "heard": best["heard"], "score": round(best["score"], 3), "status": status, "seed": best["seed"], "attempts": len(tries), "tries": tries})
        print(f"[{k + 1}/{len(pr.sentences)}] {status} {best['score']:.2f} {text[:60]}", flush=True)
    jd(report, pr.p("verify_report.json"))
    failed = [r for r in report if r["status"] == "failed"]
    st = "ok" if not flagged else "needs_review"
    out(st, sentences=len(report), flagged=[{"k": r["k"], "text": r["text"], "heard": r.get("heard", ""), "score": r.get("score")} for r in report if r["status"] in ("flagged", "failed")], report=pr.p("verify_report.json"))
    return 2 if (a.strict and flagged) or failed else 0


# ------------------------------------------------------------------ build
def load_wav(path):
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-f", "s16le", "-ac", "1", "-ar", str(SR), "-"], capture_output=True, check=True).stdout
    return np.frombuffer(r, np.int16).astype(np.float32) / 32768


def trim(x, thr_db=-42, pad=0.06):
    env = np.convolve(np.abs(x), np.ones(240) / 240, mode="same")
    idx = np.where(env > 10 ** (thr_db / 20))[0]
    if not len(idx):
        return x
    return x[max(0, idx[0] - int(pad * SR)):min(len(x), idx[-1] + int(pad * SR))]


def ts(t):
    h, r = divmod(t, 3600); m, s = divmod(r, 60)
    return f"{int(h):02d}:{int(m):02d}:{int(s):02d},{int(round((s % 1) * 1000)) % 1000:03d}"


def chunks(text, maxc=62):
    out_, cur = [], ""
    for w in text.split():
        if len(cur) + len(w) + 1 > maxc and cur:
            out_.append(cur); cur = w
        else:
            cur = (cur + " " + w).strip()
    out_.append(cur)
    if len(out_) > 1 and len(out_[-1]) < 14:
        last = out_.pop(); out_[-1] += " " + last
    return out_


def check_length(pr, duration):
    mx = float(pr.cfg.get("max_minutes", 15))
    if duration > mx * 60:
        out("fail", error=f"video would be {duration / 60:.1f} min, over the {mx:.0f} min limit (project.json max_minutes). Shorten the narration or, for lab episodes, cut/speed up more in Studio.", duration_s=round(duration, 1))
        return False
    return True


def cmd_build(pr, a):
    spec, narr = pr.spec, pr.narr
    gaps = {"lead": .7, "sentence": .32, "segment": .85, "tail": 5.0, "after_seg": {}, "extra": []}
    gaps.update(spec.get("gaps", {}))
    extra = {(g["seg"], g["i"]): g["s"] for g in gaps["extra"]}
    gens = {g["i"]: g for g in jl(pr.p("generations.json"))}
    n = len(pr.sentences)
    missing = [k for k in range(n) if k not in gens]
    if missing:
        raise SystemExit(f"missing clips for sentences {missing}; run narrate first")
    times, t, buf = [], gaps["lead"], [np.zeros(int(gaps["lead"] * SR), np.float32)]
    k = 0
    for si, seg in enumerate(narr["segments"]):
        for i, text in enumerate(seg["sentences"]):
            c = trim(load_wav(pr.p("voice", gens[k]["id"] + ".wav")))
            d = len(c) / SR
            times.append({"k": k, "seg": seg["id"], "i": i, "text": text, "start": round(t, 3), "end": round(t + d, 3)})
            buf.append(c); t += d
            if i == len(seg["sentences"]) - 1:
                gap = gaps["tail"] if si == len(narr["segments"]) - 1 else gaps["after_seg"].get(seg["id"], gaps["segment"])
            else:
                gap = gaps["sentence"] + extra.get((seg["id"], i), 0)
            buf.append(np.zeros(int(gap * SR), np.float32)); t += gap; k += 1
    voice = np.concatenate(buf)
    duration = len(voice) / SR
    with wave.open(pr.p("voiceover_raw.wav"), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((np.clip(voice, -1, 1) * 32767).astype(np.int16).tobytes())
    jd(times, pr.p("sentence_times.json"))
    T = {(x["seg"], x["i"]): x for x in times}

    def seg_start(s): return min(x["start"] for x in times if x["seg"] == s)

    def A(an, default_seg=None):
        s = an.get("seg", default_seg)
        x = T[(s, an.get("i", 0))]
        return round(x["start"] + (x["end"] - x["start"]) * an.get("frac", 0.0) + an.get("off", 0.0), 3)

    ep = spec["episode"]
    shots = [dict(kind="slide", image="slides/title.png", start=0, drift=0.02)]
    for sc in spec["scenes"]:
        kind = sc.get("kind", "slide")
        seg = sc.get("seg", sc["id"])
        start = A(sc["start"], seg) if "start" in sc else seg_start(seg) - 0.2
        if kind == "slide":
            states = [{"t": A({"seg": seg, **s_}, seg), "image": f"slides/{sc['id']}_{j + 1}.png"} for j, s_ in enumerate(sc.get("states", []))]
            sh = dict(kind="slide", image=f"slides/{sc['id']}_0.png", start=start, drift=0.025)
            if states:
                sh["states"] = states
            shots.append(sh)
        elif kind == "slide_ref":
            shots.append(dict(kind="slide", image=f"slides/{sc['ref']}_{sc['state']}.png", start=start, drift=0.025))
        elif kind == "browser":
            cam = [{"t": A(c["at"], seg), "dur": c.get("dur", 1.0), **({"rect": c["rect"]} if "rect" in c else {})} for c in sc.get("camera", [])]
            sh = dict(kind="browser", image="shots/" + sc["image"], start=start, url=ep.get("browser_url_base", "") + sc.get("url", ""))
            if cam:
                sh["camera"] = cam
            shots.append(sh)
    shots.append(dict(kind="slide", image="slides/end.png", start=A(ep["end_at"]), drift=0.02))
    shots.sort(key=lambda s: s["start"])
    for x, y in zip(shots, shots[1:]):
        x["end"] = y["start"]
    shots[-1]["end"] = duration

    disp = spec.get("display", [])

    def display(s):
        for x, y in disp:
            s = s.replace(x, y)
        return s

    caps = []
    for x in times:
        parts = chunks(display(x["text"]))
        tot = sum(len(q) for q in parts)
        t0 = x["start"]
        for q in parts:
            d = (x["end"] - x["start"]) * len(q) / tot
            caps.append({"t0": round(t0, 3), "t1": round(t0 + d, 3), "text": q}); t0 += d
    for x, y in zip(caps, caps[1:]):
        if 0 < y["t0"] - x["t1"] < 0.4:
            x["t1"] = y["t0"]
    with open(pr.p("video.srt"), "w", encoding="utf-8") as f:
        for j, c in enumerate(caps, 1):
            f.write(f"{j}\n{ts(c['t0'])} --> {ts(c['t1'])}\n{c['text']}\n\n")

    pills, yt = [], []
    for j, seg in enumerate(narr["segments"], 1):
        st = 0 if j == 1 else seg_start(seg["id"])
        yt.append((st, seg["chapter"]))
        if seg["id"] in ep.get("chapter_pills", []):
            pills.append({"t0": round(st - 0.1, 3), "t1": round(st + 3.4, 3), "num": j, "text": seg["chapter"]})
    with open(pr.p("chapters.txt"), "w", encoding="utf-8") as f:
        for st, name in yt:
            f.write(f"{int(st) // 60}:{int(st) % 60:02d} {name}\n")
    jd({"lower_thirds": [], "duration": round(duration, 3), "crossfade": 0.4, "fade_in": 0.5, "fade_out": 1.2, "shots": shots, "captions": caps, "chapters_ui": pills}, pr.p("timeline.json"))
    if not check_length(pr, duration):
        return 1
    out("ok", duration_s=round(duration, 1), shots=len(shots), captions=len(caps), timeline=pr.p("timeline.json"))
    return 0


# ------------------------------------------------------------------ slides / preview / render / mix
def cmd_slides(pr, a):
    sys.path.insert(0, HERE)
    import slidelib
    made = slidelib.render_all(pr.spec, pr.p("slides"))
    out("ok", slides=len(made), dir=pr.p("slides"))
    return 0


def run_render(pr, args, env=None):
    e = dict(os.environ, **(env or {}))
    return subprocess.run([sys.executable, os.path.join(HERE, "render.py"), pr.p("timeline.json"), *args], cwd=pr.d, env=e)


def cmd_preview(pr, a):
    from PIL import Image
    tl = jl(pr.p("timeline.json"))
    os.makedirs(pr.p("previews"), exist_ok=True)
    ts_ = sorted({round(min(tl["duration"] - 1, s["start"] + (1.5 if i else 0.8)), 1) for i, s in enumerate(tl["shots"])} | {round(c["t0"] + 0.4, 1) for c in tl["captions"][::6]})
    if tl.get("base_video"):
        ts_ = sorted(set(ts_) | {round(c["t0"] + 1.5, 1) for c in tl["chapters_ui"]} | {round(c["t0"] + 0.5, 1) for c in tl["captions"][::3]} | {1.0, round(tl["duration"] - 3, 1)})
    ts_ = ts_[:40]
    r = run_render(pr, [pr.p("previews", "pv"), "--preview", ",".join(map(str, ts_))])
    if r.returncode:
        out("fail", error="preview render failed"); return 1
    files = sorted(f for f in os.listdir(pr.p("previews")) if f.startswith("pv_"))
    ims = [Image.open(pr.p("previews", f)).resize((480, 270)) for f in files]
    cols = 4
    sheet = Image.new("RGB", (cols * 480, math.ceil(len(ims) / cols) * 270))
    for j, im in enumerate(ims):
        sheet.paste(im, ((j % cols) * 480, (j // cols) * 270))
    sheet.save(pr.p("previews", "sheet.jpg"), quality=85)
    out("ok", sheet=pr.p("previews", "sheet.jpg"), frames=len(files))
    return 0


def cmd_render(pr, a):
    tl = jl(pr.p("timeline.json"))
    total = int(tl["duration"] * FPS)
    step = a.part_frames
    parts = []
    for f0 in range(0, total, step):
        f1 = min(total, f0 + step)
        fn = pr.p(f"part_{f0}.mp4")
        parts.append(fn)
        if os.path.exists(fn):
            continue
        r = run_render(pr, [fn + ".tmp.mp4"], {"F0": str(f0), "F1": str(f1)})
        if r.returncode:
            out("fail", error=f"render part {f0} failed (exit {r.returncode})"); return 1
        os.replace(fn + ".tmp.mp4", fn)
    with open(pr.p("parts.txt"), "w") as f:
        for fn in parts:
            f.write(f"file '{os.path.basename(fn)}'\n")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-i", pr.p("parts.txt"), "-c", "copy", pr.p("final_silent.mp4")], check=True)
    for fn in parts:
        os.remove(fn)
    out("ok", video=pr.p("final_silent.mp4"))
    return 0


def sh(args):
    subprocess.run(args, check=True)


def cmd_mix(pr, a):
    raw, sil = pr.p("voiceover_raw.wav"), pr.p("final_silent.mp4")
    name = pr.spec["episode"].get("output_name", "episode")
    outp = pr.p(name + ".mp4")
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", raw], capture_output=True, text=True).stdout)
    fo = round(dur - 4, 2)
    sh(["ffmpeg", "-y", "-v", "error", "-i", raw, "-af", "aresample=48000,highpass=f=70,loudnorm=I=-16:TP=-1.5:LRA=11", "-ar", "48000", pr.p("voice_norm.wav")])
    music = pr.p(pr.cfg.get("music", "music.mp3"))
    if os.path.exists(music):
        sh(["ffmpeg", "-y", "-v", "error", "-i", pr.p("voice_norm.wav"), "-stream_loop", "-1", "-i", music, "-filter_complex",
            f"[0:a]asplit=2[v][vk];[1:a]aresample=48000,atrim=0:{dur},asetpts=N/SR/TB,loudnorm=I=-24:TP=-3,afade=t=in:st=0:d=2,afade=t=out:st={fo}:d=4[m];"
            "[m][vk]sidechaincompress=threshold=0.015:ratio=8:attack=150:release=900[md];[v][md]amix=inputs=2:normalize=0:duration=first,alimiter=limit=0.95[a]",
            "-map", "[a]", "-ar", "48000", "-c:a", "pcm_s16le", pr.p("mix.wav")])
    else:
        shutil.copy(pr.p("voice_norm.wav"), pr.p("mix.wav"))
    sh(["ffmpeg", "-y", "-v", "error", "-i", sil, "-i", pr.p("mix.wav"), "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", outp])
    out("ok", video=outp, size_mb=round(os.path.getsize(outp) / 1e6, 1))
    return 0


def cmd_package(pr, a):
    ep = pr.spec["episode"]
    name = ep.get("output_name", "episode")
    shutil.copy(pr.p("video.srt"), pr.p(name + ".srt"))
    ch = open(pr.p("chapters.txt"), encoding="utf-8").read()
    desc = (f"{ep['series'] if 'series' in ep else 'AWX from Zero'} - Episode {ep['number']}: {ep['title']}\n\n{ep.get('description', '')}\n\nChapters:\n{ch}\n"
            f"Commands and files: https://{ep.get('repo', '')}/tree/main/{ep.get('folder', '')}\nSubscribe: {ep.get('handle', '')} ({ep.get('channel', '')})\n")
    open(pr.p("youtube_description.txt"), "w", encoding="utf-8").write(desc)
    out("ok", files=[pr.p(name + ".mp4"), pr.p(name + ".srt"), pr.p("youtube_description.txt")])
    return 0


# ------------------------------------------------------------------ lab episodes (Studio recording + narration)
def plan_edit_tool():
    for c in (os.path.join(HERE, "plan_edit.py"), os.path.join(HERE, "..", "studio", "tools", "plan_edit.py")):
        if os.path.exists(c):
            return c
    raise SystemExit("plan_edit.py not found (expected next to awxvideo.py or in ../studio/tools)")


def split_sentences(t):
    return [x.strip() for x in re.split(r"(?<=[.!?])\s+", t.strip()) if x.strip()]


def cmd_lab_plan(pr, a):
    sp = pr.p("session.json")
    if not os.path.exists(sp) or not os.path.exists(pr.p("recording.webm")):
        out("fail", error="session.json / recording.webm not in project folder: save the AWX Studio session into this folder"); return 1
    S = jl(sp)
    if S["recording"].get("audio_in_recording"):
        out("fail", error="this session was recorded in Live mode (voice already in the video). Record in Silent mode for narration to be added."); return 1
    font = os.path.join(HERE, "fonts", "Inter-Bold.otf").replace("\\", "/").replace(":", "\\:")
    r = subprocess.run([sys.executable, plan_edit_tool(), pr.d, "--out", pr.p("edit"), "--font", font, "--run"], capture_output=True, text=True)
    if r.returncode:
        out("fail", error="plan_edit/ffmpeg failed", log_tail=(r.stdout + r.stderr)[-1500:]); return 1
    edl = jl(pr.p("edit", "edl.json"))
    say = {x["id"]: x.get("say", "") for x in S["script"]["steps"]}
    steps = [{"id": s["id"], "title": s["title"], "chapter": s["chapter"], "say": say.get(s["id"], ""), "out_start": s["out_start"], "out_end": s["out_end"]} for s in edl["steps"]]
    jd({"episode": S.get("episode", {}), "edited_duration_s": edl["output_duration_s"], "steps": steps, "editor_tasks": edl["editor_tasks"]}, pr.p("lab_steps.json"))
    if not os.path.exists(pr.p("narration.json")) or not pr.narr["segments"]:
        ep = pr.spec.get("episode", {})
        segs = []
        if ep.get("intro"):
            segs.append({"id": "open", "chapter": "Intro", "sentences": ep["intro"]})
        segs += [{"id": s["id"], "chapter": s["chapter"], "sentences": split_sentences(s["say"])} for s in steps if s["say"].strip()]
        if ep.get("outro"):
            segs.append({"id": "close", "chapter": "Wrap up", "sentences": ep["outro"]})
        jd({"segments": segs}, pr.p("narration.json"))
    out("ok", steps=len(steps), edited_s=edl["output_duration_s"], edited=pr.p("edit", "edited.mp4"), lab_steps=pr.p("lab_steps.json"), editor_tasks=len(edl["editor_tasks"]))
    return 0


def probe_dur(path):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path], capture_output=True, text=True).stdout)


def cmd_lab_build(pr, a):
    sys.path.insert(0, HERE)
    import slidelib
    edl = jl(pr.p("edit", "edl.json"))
    steps = edl["steps"]
    edited = pr.p("edit", "edited.mp4")
    ed_dur = probe_dur(edited)
    gens = {g["i"]: g for g in jl(pr.p("generations.json"))}
    n = len(pr.sentences)
    if [k for k in range(n) if k not in gens]:
        raise SystemExit("clips missing; run narrate first")
    spec = pr.spec
    gaps = {"sentence": .32}
    gaps.update(spec.get("gaps", {}))
    sg = gaps["sentence"]
    clips, k = {}, 0
    for seg in pr.narr["segments"]:
        arr = []
        for _ in seg["sentences"]:
            arr.append(trim(load_wav(pr.p("voice", gens[k]["id"] + ".wav")))); k += 1
        clips[seg["id"]] = arr

    def dur(sid):
        arr = clips.get(sid, [])
        return sum(len(x) for x in arr) / SR + sg * max(0, len(arr) - 1)

    LEAD = 0.4
    t_title = max(4.0, 0.7 + dur("open") + 0.9) if "open" in clips else 4.0
    t_end = max(8.0, dur("close") + 3.0) if "close" in clips else 8.0
    plan, cum = [], 0.0
    for st in steps:
        avail = st["out_end"] - st["out_start"]
        hold = max(0.0, LEAD + dur(st["id"]) + 0.6 - avail) if st["id"] in clips else 0.0
        plan.append({"id": st["id"], "chapter": st["chapter"], "e0": st["out_start"], "e1": min(st["out_end"], ed_dur), "cum": cum, "hold": round(hold, 3)})
        cum += hold
    total = t_title + ed_dur + cum + t_end

    # ---- title / end cards
    ep = spec.get("episode", {})
    os.makedirs(pr.p("lab"), exist_ok=True)
    slidelib.title_card(ep).convert("RGB").save(pr.p("lab", "title.png"))
    slidelib.end_card(ep).convert("RGB").save(pr.p("lab", "end.png"))

    # ---- video: title + edited (with freeze holds) + end
    fr = 0.2   # real footage kept before each freeze so the hold always has frames to clone
    fmt = "fps=30,scale=1920:1080,setsar=1,format=yuv420p"
    fc = [f"[0:v]{fmt},fade=t=out:st={max(0, t_title - 0.4):.3f}:d=0.4[c0]"]
    labels = ["[c0]"]
    prev, idx = 0.0, 0
    holds = [p for p in plan if p["hold"] > 0.02]
    holds.sort(key=lambda p: p["e1"])
    for p in holds:
        b = max(prev + fr, p["e1"])
        fc.append(f"[1:v]trim=start={prev:.3f}:end={b - fr:.3f},setpts=PTS-STARTPTS,{fmt}[p{idx}]")
        fc.append(f"[1:v]trim=start={b - fr:.3f}:end={b:.3f},setpts=PTS-STARTPTS,{fmt},tpad=stop_mode=clone:stop_duration={p['hold']:.3f}[h{idx}]")
        labels += [f"[p{idx}]", f"[h{idx}]"]
        prev = b; idx += 1
    fc.append(f"[1:v]trim=start={prev:.3f}:end={ed_dur:.3f},setpts=PTS-STARTPTS,{fmt}[p{idx}]")
    labels.append(f"[p{idx}]")
    fc.append(f"[2:v]{fmt},fade=t=in:st=0:d=0.4[cN]")
    labels.append("[cN]")
    fc.append("".join(labels) + f"concat=n={len(labels)}:v=1:a=0[v]")
    r = subprocess.run(["ffmpeg", "-y", "-v", "error", "-loop", "1", "-framerate", "30", "-t", f"{t_title:.3f}", "-i", pr.p("lab", "title.png"), "-fflags", "+genpts", "-i", edited,
                        "-loop", "1", "-framerate", "30", "-t", f"{t_end:.3f}", "-i", pr.p("lab", "end.png"), "-filter_complex", ";".join(fc), "-map", "[v]",
                        "-c:v", "libx264", "-preset", "veryfast", "-crf", "16", "-pix_fmt", "yuv420p", pr.p("base_silent.mp4")], capture_output=True, text=True)
    if r.returncode:
        out("fail", error="ffmpeg compose failed", log_tail=r.stderr[-1500:]); return 1
    got = probe_dur(pr.p("base_silent.mp4"))
    if abs(got - total) > 0.6:
        out("fail", error=f"composited video is {got:.1f}s, expected {total:.1f}s"); return 1

    # ---- voice placement
    buf = np.zeros(int((total + 1) * SR), np.float32)
    times, k = [], 0
    starts = {"open": 0.7, "close": t_title + ed_dur + cum + 0.8}
    for p in plan:
        starts[p["id"]] = t_title + p["e0"] + p["cum"] + LEAD
    for seg in pr.narr["segments"]:
        t = starts.get(seg["id"], t_title)
        for i, text in enumerate(seg["sentences"]):
            c = clips[seg["id"]][i]
            a0 = int(t * SR)
            buf[a0:a0 + len(c)] += c[:max(0, len(buf) - a0)]
            times.append({"k": k, "seg": seg["id"], "i": i, "text": text, "start": round(t, 3), "end": round(t + len(c) / SR, 3)})
            t += len(c) / SR + sg; k += 1
    for x, y in zip(times, times[1:]):
        if y["start"] < x["end"] - 0.02:
            print(f"WARNING overlap {x['seg']}#{x['i']} / {y['seg']}#{y['i']}", file=sys.stderr)
    buf = buf[:int(total * SR)]
    with wave.open(pr.p("voiceover_raw.wav"), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((np.clip(buf, -1, 1) * 32767).astype(np.int16).tobytes())
    jd(times, pr.p("sentence_times.json"))

    # ---- captions, chapters, timeline
    disp = spec.get("display", [])

    def display(s):
        for x, y in disp:
            s = s.replace(x, y)
        return s
    caps = []
    for x in times:
        parts = chunks(display(x["text"]))
        tot = sum(len(q) for q in parts)
        t0 = x["start"]
        for q in parts:
            d = (x["end"] - x["start"]) * len(q) / tot
            caps.append({"t0": round(t0, 3), "t1": round(t0 + d, 3), "text": q}); t0 += d
    for x, y in zip(caps, caps[1:]):
        if 0 < y["t0"] - x["t1"] < 0.4:
            x["t1"] = y["t0"]
    with open(pr.p("video.srt"), "w", encoding="utf-8") as f:
        for j, c in enumerate(caps, 1):
            f.write(f"{j}\n{ts(c['t0'])} --> {ts(c['t1'])}\n{c['text']}\n\n")
    ch = [(0.0, "Intro")]
    pills = []
    for j, p in enumerate(plan, 1):
        st = t_title + p["e0"] + p["cum"]
        ch.append((st, p["chapter"]))
        pills.append({"t0": round(st, 3), "t1": round(st + 3.4, 3), "num": j, "text": p["chapter"]})
    with open(pr.p("chapters.txt"), "w", encoding="utf-8") as f:
        for st, name in ch:
            f.write(f"{int(st) // 60}:{int(st) % 60:02d} {name}\n")
    jd({"lower_thirds": [], "duration": round(got, 3), "fade_in": 0.5, "fade_out": 1.2, "shots": [], "base_video": "base_silent.mp4", "captions": caps, "chapters_ui": pills}, pr.p("timeline.json"))
    jd({"plan": plan, "title_s": t_title, "end_s": t_end, "holds_total_s": round(cum, 2)}, pr.p("lab_build.json"))
    if not check_length(pr, got):
        return 1
    out("ok", duration_s=round(got, 1), expected_s=round(total, 1), holds_total_s=round(cum, 1), steps=len(plan), captions=len(caps), timeline=pr.p("timeline.json"))
    return 0


def cmd_all(pr, a):
    for fn in (cmd_narrate, cmd_build, cmd_slides, cmd_render, cmd_mix, cmd_package):
        rc = fn(pr, a)
        if rc:
            return rc
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["doctor", "narrate", "build", "slides", "preview", "render", "mix", "package", "all", "lab-plan", "lab-build"])
    ap.add_argument("project")
    ap.add_argument("--voicebox", action="store_true")
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--part-frames", type=int, default=2200)
    a = ap.parse_args()
    pr = P(a.project)
    sys.exit(globals()["cmd_" + a.cmd.replace("-", "_")](pr, a) or 0)


if __name__ == "__main__":
    main()
