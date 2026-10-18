#!/usr/bin/env python3
"""AWX from Zero - lab episode finishing in the Ep 4 / Ep 5 style.

Runs after `lab-plan` and `narrate` (see awxvideo.py). Same project folder.

  python awxpro.py pro-compose <project>   cut footage to the voice (jump-cuts / slow-down / hold), voiceover_raw.wav, pro/vid.mp4, pro/timeline.json
  python awxpro.py pro-events  <project>   chapter lower-thirds + keyword callouts -> pro/events.json
  python awxpro.py pro-overlay <project>   render the graphics layer (Chromium) -> pro/overlay.mov
  python awxpro.py pro-final   <project>   title/end card + ducked music + size-capped export: "AWX Ep05 - Motion Graphics.mp4" and "... - Clean.mp4"
  python awxpro.py pro-extras  <project>   thumbnail + YouTube title/description/chapters/tags + review notes (frames to blur)

Optional pro.json in the project folder (every key optional): see examples/ep05/pro.json.
Every command ends with one JSON line (status + paths) so n8n can read it.
"""
import argparse, json, math, os, re, shutil, subprocess, sys, wave
from concurrent.futures import ThreadPoolExecutor
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import awxvideo as A
from awxvideo import jl, jd, out, load_wav, trim, probe_dur, SR

DEFAULTS = {
    "chunk_chars": 170,        # sentences are grouped into chunks of about this many characters; each chunk gets its own footage window
    "gap": 0.3,                # silence after each chunk
    "sentence_gap": 0.32,      # silence between sentences inside a chunk
    "jump_ratio": 1.35,        # footage / voice above this: jump-cut instead of speeding up
    "min_speed": 0.8,          # below this the footage is slowed to 0.8x and the last frame is held
    "silent_speed": 8,         # steps without narration are time-lapsed up to this speed
    "title_s": 5.0, "end_s": 9.0,
    "music_volume": 0.28, "duck": {"threshold": 0.015, "ratio": 6, "attack": 300, "release": 900},
    "size_cap_mb": 27.0, "preset": "slow", "audio_kbps": 128,
    "auto_cmd_callouts": False,
    "chapters": {}, "callouts": [], "ranges": {}, "thumb": {}, "youtube": {}, "sensitive": [],
}


def cfg_of(pr):
    c = json.loads(json.dumps(DEFAULTS))
    f = pr.p("pro.json")
    if os.path.exists(f):
        for k, v in jl(f).items():
            if isinstance(v, dict) and isinstance(c.get(k), dict) and k in ("duck",):
                c[k].update(v)
            else:
                c[k] = v
    return c


def pdir(pr):
    d = pr.p("pro")
    os.makedirs(d, exist_ok=True)
    return d


def run(args, **kw):
    r = subprocess.run(args, capture_output=True, text=True, **kw)
    if r.returncode:
        raise RuntimeError("ffmpeg failed: " + " ".join(args[:6]) + "\n" + r.stderr[-1500:])
    return r


def _parallel(cmds):
    n = max(2, os.cpu_count() or 2)
    with ThreadPoolExecutor(n) as ex:
        res = list(ex.map(lambda c: subprocess.run(c, capture_output=True, text=True), cmds))
    bad = [r for r in res if r.returncode]
    if bad:
        raise RuntimeError("segment encode failed: " + bad[0].stderr[-800:])


def group(sents, maxc):
    g, cur, n = [], [], 0
    for k, t in sents:
        if cur and n + len(t) > maxc:
            g.append(cur); cur, n = [], 0
        cur.append((k, t)); n += len(t) + 1
    if cur:
        g.append(cur)
    return g


# ------------------------------------------------------------------ pro-compose
def cmd_pro_compose(pr, a):
    cfg = cfg_of(pr)
    d = pdir(pr)
    edl = jl(pr.p("edit", "edl.json"))
    edited = pr.p("edit", "edited.mp4")
    ed_dur = probe_dur(edited)
    steps = edl["steps"]
    order = [s["id"] for s in steps]
    byid = {s["id"]: s for s in steps}
    gens = {g["i"]: g for g in jl(pr.p("generations.json"))}
    sents = pr.sentences
    miss = [k for k in range(len(sents)) if k not in gens]
    if miss:
        out("fail", error="narration clips missing, run narrate first"); return 1
    clip = {}
    for k in range(len(sents)):
        clip[k] = trim(load_wav(pr.p("voice", gens[k]["id"] + ".wav")))

    def step_for(seg):
        if seg in byid:
            return seg
        return order[0] if seg == "open" else order[-1] if seg == "close" else None
    per = {sid: [] for sid in order}
    k = 0
    for seg in pr.narr["segments"]:
        sid = step_for(seg["id"])
        items = []
        for t in seg["sentences"]:
            items.append((k, t)); k += 1
        if sid is None:
            out("fail", error=f"narration segment '{seg['id']}' matches no step in the recording"); return 1
        per[sid] += items
    sg, gap = cfg["sentence_gap"], cfg["gap"]
    chunks = []
    for sid in order:
        for gi, g in enumerate(group(per[sid], cfg["chunk_chars"])):
            arr = []
            for kk, _ in g:
                arr.append(clip[kk])
                arr.append(np.zeros(int(sg * SR), np.float32))
            wav = np.concatenate(arr[:-1])
            vd = len(wav) / SR
            chunks.append({"step": sid, "idx": gi, "text": " ".join(t for _, t in g), "wav": wav, "vd": vd, "D": vd + gap})
    cmds, lst, t = [], [], 0.0
    segdir = os.path.join(d, "seg")
    os.makedirs(segdir, exist_ok=True)
    for f in os.listdir(segdir):
        os.remove(os.path.join(segdir, f))
    meta_steps, silent = [], []
    n_seg = 0

    def enc(st, w, vf, tt, name):
        return ["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{st:.3f}", "-t", f"{w:.3f}", "-i", edited, "-vf", vf, "-t", f"{tt:.3f}", "-an",
                "-c:v", "libx264", "-preset", "fast", "-crf", "16", "-pix_fmt", "yuv420p", os.path.join(segdir, name + ".mp4")]
    for sid in order:
        st = byid[sid]
        e0, e1 = max(0.0, st["out_start"]), min(st["out_end"], ed_dur)
        mine = [c for c in chunks if c["step"] == sid]
        t_step0 = t
        if not mine:
            span = e1 - e0
            if span < 1.0:
                continue
            D = max(span / cfg["silent_speed"], 1.0)
            cmds.append(enc(e0, span, f"setpts=(PTS-STARTPTS)/{span / D:.5f},fps=30", D, f"s{n_seg}")); lst.append(f"s{n_seg}"); n_seg += 1
            silent.append({"step": sid, "t": round(t, 3), "D": round(D, 3)}); t += D
            meta_steps.append({"id": sid, "title": st["title"], "chapter": st["chapter"], "t0": round(t_step0, 3), "t1": round(t, 3), "silent": True})
            continue
        tot = sum(c["D"] for c in mine)
        cum = 0.0
        for c in mine:
            key = f"{sid}:{c['idx']}"
            if key in cfg["ranges"]:
                sa, sb = cfg["ranges"][key]
            else:
                sa = e0 + (e1 - e0) * cum / tot
                sb = e0 + (e1 - e0) * (cum + c["D"]) / tot
            cum += c["D"]
            sa, sb = max(0.0, min(sa, ed_dur - 0.2)), min(sb, ed_dur)
            Sj = max(0.12, sb - sa); D = c["D"]; rr = Sj / D
            c["t"], c["src"] = t, [round(sa, 2), round(sb, 2)]
            if rr > cfg["jump_ratio"]:
                p = 1.15; kept = D * p; n = max(1, min(8, math.ceil(rr * 0.9))); w = kept / n
                gaps = (Sj - kept) / (n - 1) if n > 1 else 0
                for q in range(n):
                    s0 = sa + q * (w + gaps)
                    cmds.append(enc(s0, w, f"setpts=(PTS-STARTPTS)/{p},fps=30", w / p, f"c{n_seg}")); lst.append(f"c{n_seg}"); n_seg += 1
                c["mode"] = f"jump x{n}"
            else:
                if rr >= cfg["min_speed"]:
                    sp, hold = rr, 0.0
                else:
                    sp, hold = cfg["min_speed"], D - Sj / cfg["min_speed"]
                vf = f"setpts=(PTS-STARTPTS)/{sp:.5f},fps=30" + (f",tpad=stop_mode=clone:stop_duration={hold:.3f}" if hold > 0 else "")
                cmds.append(enc(sa, Sj, vf, D, f"c{n_seg}")); lst.append(f"c{n_seg}"); n_seg += 1
                c["mode"] = f"speed {sp:.2f}" + (f" hold {hold:.1f}s" if hold > 0 else "")
            t += D
        meta_steps.append({"id": sid, "title": st["title"], "chapter": st["chapter"], "t0": round(t_step0, 3), "t1": round(t, 3), "silent": False})
    total = t
    try:
        _parallel(cmds)
    except RuntimeError as e:
        out("fail", error=str(e)); return 1
    open(os.path.join(d, "list.txt"), "w").write("\n".join(f"file 'seg/{n}.mp4'" for n in lst))
    try:
        run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", os.path.join(d, "list.txt"), "-c:v", "libx264", "-preset", "fast", "-crf", "14", "-pix_fmt", "yuv420p", "-r", "30", os.path.join(d, "vid.mp4")])
    except RuntimeError as e:
        out("fail", error=str(e)); return 1
    got = probe_dur(os.path.join(d, "vid.mp4"))
    buf = np.zeros(int((total + 1) * SR), np.float32)
    for c in chunks:
        a0 = int(c["t"] * SR)
        w = c["wav"][:max(0, len(buf) - a0)]
        buf[a0:a0 + len(w)] += w
    buf = buf[:int(total * SR)]
    with wave.open(pr.p("voiceover_raw.wav"), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((np.clip(buf, -1, 1) * 32767).astype(np.int16).tobytes())
    jd({"dur": round(total, 3), "video_dur": round(got, 3),
        "chunks": [{k: v for k, v in c.items() if k != "wav"} | {"vd": round(c["vd"], 3), "D": round(c["D"], 3), "t": round(c["t"], 3)} for c in chunks],
        "steps": meta_steps, "silent_steps": silent}, os.path.join(d, "timeline.json"))
    if abs(got - total) > 0.5:
        out("fail", error=f"composed video is {got:.1f}s, voice is {total:.1f}s"); return 1
    out("ok", duration_s=round(total, 1), chunks=len(chunks), segments=len(lst), silent_steps=len(silent), video=os.path.join(d, "vid.mp4"), voice=pr.p("voiceover_raw.wav"))
    return 0


# ------------------------------------------------------------------ pro-events
def cmd_pro_events(pr, a):
    cfg = cfg_of(pr)
    d = pdir(pr)
    T = jl(os.path.join(d, "timeline.json"))
    dur, ch = T["dur"], T["chunks"]
    steps = [s for s in T["steps"] if not s["silent"]]
    inner = [s for s in steps if s["id"] not in ("open", "close") and s["id"] != steps[0]["id"] and s["id"] != steps[-1]["id"]]
    ev = []
    for i, s in enumerate(inner, 1):
        tag, title = cfg["chapters"].get(s["id"], [s["chapter"], s["title"]])
        first = next(c for c in ch if c["step"] == s["id"])
        ev.append({"type": "chapter", "n": i, "total": len(inner), "tag": tag, "title": title, "t0": round(first["t"] + 0.3, 2), "dur": 4.2})
    C = list(cfg["callouts"])
    if cfg["auto_cmd_callouts"] and os.path.exists(pr.p("session.json")):
        S = jl(pr.p("session.json"))
        for st in S.get("script", {}).get("steps", []):
            cm = [x for x in st.get("cmd", []) if isinstance(x, str) and x.strip()]
            if cm and any(c["step"] == st["id"] for c in ch):
                C.append({"step": st["id"], "at": 1.0, "type": "callout", "text": cm[0][:60], "k": "COMMAND", "mono": True})
    miss = []
    for c in C:
        if "kw" in c:
            cc = next((x for x in ch if c["kw"].lower() in x["text"].lower()), None)
            if not cc:
                miss.append(c["kw"]); continue
            fr = cc["text"].lower().index(c["kw"].lower()) / max(1, len(cc["text"]))
            t0 = cc["t"] + fr * cc["vd"] + 0.4 + float(c.get("offset", 0))
        else:
            cc = next((x for x in ch if x["step"] == c["step"]), None)
            if not cc:
                continue
            t0 = cc["t"] + float(c.get("at", 1.0))
        ty = c.get("type", "callout")
        e = {"type": ty, "t0": round(t0, 2), "dur": float(c.get("dur", 5.0 if ty == "full" else 4.0))}
        if ty == "callout":
            e.update(text=c["text"], k=c.get("k", ""), mono=bool(c.get("mono")))
        else:
            e.update(text=c["text"], sub=c.get("sub", ""))
        ev.append(e)
    ev.sort(key=lambda e: e["t0"])
    last = 0.0
    for e in ev:
        if e["type"] in ("chapter", "callout"):
            if e["t0"] < last + 0.2:
                e["t0"] = round(last + 0.2, 2)
            last = e["t0"] + e["dur"]
    for e in ev:
        e["t0"] = round(max(0.0, min(e["t0"], dur - e["dur"] - 0.1)), 2)
    jd(ev, os.path.join(d, "events.json"))
    out("ok", events=len(ev), chapters=sum(1 for e in ev if e["type"] == "chapter"), missing_keywords=miss, events_file=os.path.join(d, "events.json"))
    return 0


# ------------------------------------------------------------------ pro-overlay
def cmd_pro_overlay(pr, a):
    from playwright.sync_api import sync_playwright
    d = pdir(pr)
    ev = jl(os.path.join(d, "events.json"))
    T = jl(os.path.join(d, "timeline.json"))
    dst = os.path.join(d, "overlay.mov")
    if not ev:
        if os.path.exists(dst):
            os.remove(dst)
        out("ok", overlay=None, note="no events, clean video only"); return 0
    FPS = 30
    n = int(T["dur"] * FPS)
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", str(FPS), "-c:v", "png", "-i", "-", "-c:v", "png", "-pix_fmt", "rgba", dst], stdin=subprocess.PIPE)
    page_url = "file:///" + os.path.join(HERE, "overlay", "index.html").replace("\\", "/").lstrip("/")
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1920, "height": 1080})
        pg.goto(page_url)
        pg.evaluate("ev=>load(ev)", ev)
        pg.evaluate("render(-1)")
        blank = pg.screenshot(omit_background=True, type="png")
        act = [(e["t0"], e["t0"] + e["dur"]) for e in ev]
        for f in range(n):
            t = f / FPS
            if any(x <= t <= y for x, y in act):
                pg.evaluate("t=>render(t)", t)
                ff.stdin.write(pg.screenshot(omit_background=True, type="png"))
            else:
                ff.stdin.write(blank)
        b.close()
    ff.stdin.close()
    if ff.wait():
        out("fail", error="overlay encode failed"); return 1
    out("ok", overlay=dst, frames=n, size_mb=round(os.path.getsize(dst) / 1e6, 1))
    return 0


# ------------------------------------------------------------------ pro-final
def ep_meta(pr):
    ep = dict(pr.spec.get("episode", {}))
    S = jl(pr.p("session.json")) if os.path.exists(pr.p("session.json")) else {}
    se = S.get("episode", {})
    ep.setdefault("number", se.get("number", 0)); ep.setdefault("title", se.get("title", "Episode"))
    return ep


def out_names(pr):
    ep = ep_meta(pr)
    base = f"AWX Ep{int(ep['number']):02d}"
    return pr.p(base + " - Motion Graphics.mp4"), pr.p(base + " - Clean.mp4")


def cmd_pro_final(pr, a):
    cfg = cfg_of(pr)
    d = pdir(pr)
    sys.path.insert(0, HERE)
    import slidelib
    ep = ep_meta(pr)
    T = jl(os.path.join(d, "timeline.json"))
    ts_, te_ = cfg["title_s"], cfg["end_s"]
    main = T["video_dur"]
    total = ts_ + main + te_
    os.makedirs(pr.p("lab"), exist_ok=True)
    slidelib.title_card(ep).convert("RGB").save(pr.p("lab", "title.png"))
    slidelib.end_card(ep).convert("RGB").save(pr.p("lab", "end.png"))
    try:
        for n, secs in (("title", ts_), ("end", te_)):
            run(["ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-framerate", "30", "-t", str(secs), "-i", pr.p("lab", n + ".png"),
                 "-vf", f"scale=1920:1080,fade=t=in:st=0:d=0.5,fade=t=out:st={secs - 1}:d=1,format=yuv420p", "-c:v", "libx264", "-crf", "14", os.path.join(d, f"ch_{n}.mp4")])
        # audio: voice delayed by the title card, music looped + ducked under the voice
        music = pr.p(pr.cfg.get("music", "music.mp3"))
        du = cfg["duck"]
        have_music = os.path.exists(music)
        fade_out = round(total - 4, 2)
        if have_music:
            fc = (f"[0:a]aresample=48000,adelay={int(ts_ * 1000)}|{int(ts_ * 1000)},apad=whole_dur={total:.3f},asplit=2[v1][v2];"
                  f"[1:a]aresample=48000,atrim=0:{total:.3f},asetpts=PTS-STARTPTS,volume={cfg['music_volume']},afade=t=in:d=2,afade=t=out:st={fade_out}:d=4[m];"
                  f"[m][v2]sidechaincompress=threshold={du['threshold']}:ratio={du['ratio']}:attack={du['attack']}:release={du['release']}[md];"
                  "[v1][md]amix=inputs=2:normalize=0:duration=first,alimiter=limit=0.95[a]")
            ins = ["-i", pr.p("voiceover_raw.wav"), "-stream_loop", "-1", "-i", music]
        else:
            fc = f"[0:a]aresample=48000,adelay={int(ts_ * 1000)}|{int(ts_ * 1000)},apad=whole_dur={total:.3f},alimiter=limit=0.95[a]"
            ins = ["-i", pr.p("voiceover_raw.wav")]
        run(["ffmpeg", "-y", "-loglevel", "error"] + ins + ["-filter_complex", fc, "-map", "[a]", "-t", f"{total:.3f}", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2", os.path.join(d, "mix.m4a")])
        ov = os.path.join(d, "overlay.mov")
        names = {"text": out_names(pr)[0], "clean": out_names(pr)[1]}
        made = []
        for v in ("text", "clean"):
            if v == "text" and not os.path.exists(ov):
                continue
            m = os.path.join(d, f"m_{v}.mp4")
            if v == "text":
                run(["ffmpeg", "-y", "-loglevel", "error", "-i", os.path.join(d, "vid.mp4"), "-i", ov, "-filter_complex", "[0:v][1:v]overlay=0:0:format=auto,format=yuv420p[v]", "-map", "[v]",
                     "-c:v", "libx264", "-preset", "fast", "-crf", "14", m])
            else:
                shutil.copy(os.path.join(d, "vid.mp4"), m)
            lst = os.path.join(d, f"j_{v}.txt")
            open(lst, "w").write(f"file 'ch_title.mp4'\nfile 'm_{v}.mp4'\nfile 'ch_end.mp4'\n")
            allv = os.path.join(d, f"all_{v}.mp4")
            run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c:v", "libx264", "-preset", "fast", "-crf", "14", "-pix_fmt", "yuv420p", "-r", "30", allv])
            kb = max(150, int(cfg["size_cap_mb"] * 8000 / total * 0.96) - cfg["audio_kbps"])
            common = ["-c:v", "libx264", "-preset", cfg["preset"], "-b:v", f"{kb}k", "-maxrate", f"{kb * 2}k", "-bufsize", f"{kb * 4}k", "-passlogfile", os.path.join(d, "p_" + v)]
            nul = "NUL" if os.name == "nt" else "/dev/null"
            run(["ffmpeg", "-y", "-loglevel", "error", "-i", allv] + common + ["-pass", "1", "-an", "-f", "null", nul])
            run(["ffmpeg", "-y", "-loglevel", "error", "-i", allv, "-i", os.path.join(d, "mix.m4a"), "-map", "0:v", "-map", "1:a"] + common +
                ["-pass", "2", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", f"{cfg['audio_kbps']}k", "-ar", "44100", "-ac", "2", "-movflags", "+faststart", "-shortest", names[v]])
            made.append({"file": names[v], "size_mb": round(os.path.getsize(names[v]) / 1e6, 1)})
    except RuntimeError as e:
        out("fail", error=str(e)); return 1
    out("ok", files=made, duration_s=round(total, 1))
    return 0


# ------------------------------------------------------------------ pro-extras
def mmss(t):
    return f"{int(t // 60)}:{int(t % 60):02d}"


def cmd_pro_extras(pr, a):
    cfg = cfg_of(pr)
    d = pdir(pr)
    sys.path.insert(0, HERE)
    import slidelib as L
    from PIL import ImageDraw, Image
    ep = ep_meta(pr)
    T = jl(os.path.join(d, "timeline.json"))
    th = cfg["thumb"]
    words = ep["title"].upper().split()
    line1 = th.get("line1", " ".join(words[:2]) if len(words) > 2 else words[0])
    line2 = th.get("line2", " ".join(words[2:]) if len(words) > 2 else (words[1] if len(words) > 1 else ""))
    sub = th.get("sub", ep["title"])
    chips = th.get("chips", [s["chapter"] for s in T["steps"][1:-1][:4]])
    K = L.K
    im = L.base(True)
    dr = ImageDraw.Draw(im)
    dr.text((100 * K, 90 * K), f"AWX FROM ZERO  ·  EP {ep['number']}", font=L.F(40, "Bold"), fill=L.ACC)
    dr.text((100 * K, 200 * K), line1, font=L.F(190, "Bold"), fill=L.WHITE)
    dr.text((100 * K, 400 * K), line2, font=L.F(280, "Bold"), fill=L.ACC)
    dr.text((100 * K, 715 * K), sub, font=L.F(60, "Bold"), fill=(255, 210, 138))
    x, y = 100, 850
    for i, n in enumerate(chips):
        f = L.F(46, "Bold"); w = f.getlength(n) / K + 60
        lay = Image.new("RGBA", im.size, (0, 0, 0, 0))
        ImageDraw.Draw(lay).rounded_rectangle([x * K, y * K, (x + w) * K, (y + 84) * K], 22 * K, fill=(255, 255, 255, 40), outline=L.ACC + (255,), width=3 * K)
        im.alpha_composite(lay)
        ImageDraw.Draw(im).text(((x + 30) * K, (y + 42) * K), n, font=f, fill=L.WHITE, anchor="lm")
        x += w
        if i < len(chips) - 1:
            ImageDraw.Draw(im).text(((x + 24) * K, (y + 42) * K), "→", font=L.F(54, "Bold"), fill=L.ACC, anchor="mm"); x += 48
    thumb = pr.p(f"ep{int(ep['number']):02d}_thumbnail.png")
    im.convert("RGB").resize((1280, 720), Image.LANCZOS).save(thumb, optimize=True)
    # YouTube text. Chapters are shifted by the title card.
    yt = cfg["youtube"]
    off = cfg["title_s"]
    chap = [("0:00", "Intro")]
    for s in T["steps"]:
        if s["silent"] or s["id"] in ("open", "close"):
            continue
        chap.append((mmss(s["t0"] + off), yt.get("chapter_names", {}).get(s["id"], s["title"])))
    chap.append((mmss(next((s["t0"] for s in T["steps"] if s["id"] == "close"), T["dur"] - 20) + off), "Recap"))
    title = yt.get("title") or f"AWX from Zero Ep {ep['number']}: {ep['title']}" + (f" ({yt['title_suffix']})" if yt.get("title_suffix") else "")
    nxt = ep.get("next", {})
    desc = [yt.get("description", ep.get("description", "")), ""]
    if yt.get("bullets"):
        desc += ["In this episode:"] + [f"- {b}" for b in yt["bullets"]] + [""]
    desc += ["Chapters:"] + [f"{t} {n}" for t, n in chap] + ["",
             f"All files are in the {ep.get('folder', 'episode')} folder: {ep.get('repo', 'github.com/Venuvgp19/Youtube-Tutorials-Awx')}"]
    if nxt.get("title"):
        desc.append(f"Next episode: {nxt['title']}" + (f" ({nxt['sub']})" if nxt.get("sub") else "") + ".")
    if yt.get("music_credit", True):
        desc += ["", yt.get("music_line", 'Music: "Background Educational" by sigmamusicart (Pixabay)')]
    tags = yt.get("tags", ["AWX", "Ansible AWX", "AWX tutorial", "AWX for beginners", "Ansible Tower", "DevOps", "Ansible automation", "AWX from Zero", "Venu Automates"])
    hashtags = yt.get("hashtags", ["#AWX", "#Ansible", "#DevOps", "#Automation", "#RedHat"])
    txt = f"TITLE:\n{title}\n\nDESCRIPTION:\n" + "\n".join(desc) + "\n\n" + " ".join(hashtags) + "\n\nTAGS:\n" + ", ".join(tags) + "\n"
    ytf = pr.p(f"youtube_ep{int(ep['number']):02d}.txt")
    open(ytf, "w", encoding="utf-8").write(txt)
    # review notes: frames to blur (times in the final video)
    notes = ["Frames to check / blur before publishing:"]
    for s in cfg["sensitive"]:
        st = next((x for x in T["steps"] if x["id"] == s["step"]), None)
        if st:
            notes.append(f"{mmss(st['t0'] + off)}-{mmss(st['t1'] + off)}  ({st['title']}): {s['note']}")
    notes += ["", "Chunk timing (video, voice, footage window, mode):"]
    for c in T["chunks"]:
        notes.append(f"{mmss(c['t'] + off)} {c['step']}#{c['idx']} voice {c['vd']:.1f}s, footage {c['src'][0]}-{c['src'][1]}s, {c.get('mode', '')}")
    nf = pr.p("review_notes.txt")
    open(nf, "w", encoding="utf-8").write("\n".join(notes) + "\n")
    out("ok", thumbnail=thumb, youtube=ytf, notes=nf)
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["pro-compose", "pro-events", "pro-overlay", "pro-final", "pro-extras"])
    ap.add_argument("project")
    a = ap.parse_args()
    pr = A.P(a.project)
    sys.exit(globals()["cmd_" + a.cmd.replace("-", "_")](pr, a) or 0)


if __name__ == "__main__":
    main()
