#!/usr/bin/env python3
"""Turn an AWX Studio session into an edit plan and (optionally) a rendered cut.

  python3 plan_edit.py <session-folder-or-session.json> [--out DIR] [--speed 8] [--scale 1920x1080]
                       [--font PATH] [--run]

Reads  : session.json (+ recording.webm next to it)
Writes : DIR/edl.json            keep-segments with speed, step/chapter output times, callouts, editor tasks
         DIR/chapters.txt        YouTube chapter list in OUTPUT time
         DIR/narration_plan.json one entry per step: say text + output start/end (for cloned-voice narration)
         DIR/render.sh           the ffmpeg command (also runs it with --run)
         DIR/edited.mp4          only with --run

Rules (see SESSION_FORMAT.md):
  cut ranges and dropped takes (retake) are removed; speed ranges are time-lapsed (default 8x, or "x16" in the note);
  audio of time-lapsed segments is muted; callouts become on-screen text; zoom/note/mark are listed as editor tasks.
Only needs Python 3 and ffmpeg.
"""
import argparse, json, os, re, shlex, subprocess, sys

MIN_SEG = 0.05


def load(p):
    if os.path.isdir(p):
        p = os.path.join(p, "session.json")
    return p, json.load(open(p))


def merge(iv):
    iv = sorted((a, b) for a, b in iv if b > a)
    out = []
    for a, b in iv:
        if out and a <= out[-1][1]:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return out


def build_segments(dur, removed, speeds, default_speed):
    """Return [{start,end,speed}] covering [0,dur] minus removed, split on speed ranges."""
    cuts = merge(removed)
    keep, pos = [], 0.0
    for a, b in cuts:
        if a > pos:
            keep.append([pos, min(a, dur)])
        pos = max(pos, b)
    if pos < dur:
        keep.append([pos, dur])
    segs = []
    for a, b in keep:
        pts = {a, b}
        for s in speeds:
            for t in (s["start"], s["end"]):
                if a < t < b:
                    pts.add(t)
        pts = sorted(pts)
        for x, y in zip(pts, pts[1:]):
            if y - x < MIN_SEG:
                continue
            mid = (x + y) / 2
            sp = 1.0
            for s in speeds:
                if s["start"] <= mid < s["end"]:
                    sp = s["factor"]
            segs.append({"start": round(x, 3), "end": round(y, 3), "speed": sp})
    return segs


def out_time(segs, t):
    """Map source time -> output time (kept footage only; removed time collapses to next kept point)."""
    o = 0.0
    for s in segs:
        if t <= s["start"]:
            return o
        if t < s["end"]:
            return o + (t - s["start"]) / s["speed"]
        o += (s["end"] - s["start"]) / s["speed"]
    return o


def hms(t):
    t = int(round(t))
    return f"{t // 60}:{t % 60:02d}" if t < 3600 else f"{t // 3600}:{t % 3600 // 60:02d}:{t % 60:02d}"


def esc_text(s):
    return s.replace("\\", "\\\\").replace(":", "\\:").replace("'", "’").replace("%", "\\%")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("session")
    ap.add_argument("--out")
    ap.add_argument("--speed", type=float, default=8.0)
    ap.add_argument("--scale", default="1920x1080")
    ap.add_argument("--font", default="")
    ap.add_argument("--run", action="store_true")
    a = ap.parse_args()

    sp, S = load(a.session)
    base = os.path.dirname(os.path.abspath(sp))
    out = a.out or os.path.join(base, "edit")
    os.makedirs(out, exist_ok=True)
    rec = S["recording"]
    dur = rec["duration_s"]
    live = bool(rec.get("audio_in_recording"))

    removed = [(r["start"], r["end"]) for r in S["ranges"] if r["type"] == "cut"]
    removed += [(t["from"], t["to"]) for t in S["takes"] if t.get("to") is not None]
    speeds = []
    for r in S["ranges"]:
        if r["type"] == "speed":
            m = re.search(r"x\s*(\d+(?:\.\d+)?)", r.get("note", "") or "")
            speeds.append({"start": r["start"], "end": r["end"], "factor": float(m.group(1)) if m else a.speed, "note": r.get("note", "")})
    segs = build_segments(dur, removed, speeds, a.speed)
    out_dur = sum((s["end"] - s["start"]) / s["speed"] for s in segs)

    # steps -> output time (use the last visit of each step, i.e. the kept take)
    steps = []
    for st in S["steps"]:
        if not st.get("visited"):
            continue
        s0, s1 = st["start_s"], st["end_s"] if st["end_s"] is not None else dur
        steps.append({"id": st["id"], "title": st["title"], "chapter": st["chapter"], "src_start": s0, "src_end": s1,
                      "out_start": round(out_time(segs, s0), 2), "out_end": round(out_time(segs, s1), 2)})
    chapters = [(0.0 if i == 0 else s["out_start"], s["chapter"]) for i, s in enumerate(steps)]
    with open(os.path.join(out, "chapters.txt"), "w") as f:
        for t, c in chapters:
            f.write(f"{hms(t)} {c}\n")

    say = {x["id"]: x.get("say", "") for x in S["script"]["steps"]}
    narr = [{"step": s["id"], "say": say.get(s["id"], ""), "out_start": s["out_start"], "out_end": s["out_end"],
             "available_s": round(s["out_end"] - s["out_start"], 2)} for s in steps]
    json.dump({"mode": S["mode"], "note": "Silent mode: generate one cloned-voice clip per entry and start it at out_start. If available_s is shorter than the clip, extend the step (freeze last frame) or shorten the text.",
               "steps": narr}, open(os.path.join(out, "narration_plan.json"), "w"), indent=1)

    callouts, tasks = [], []
    for m in S["markers"]:
        t_o = round(out_time(segs, m["t"]), 2)
        if any(a_ <= m["t"] < b_ for a_, b_ in merge(removed)):
            continue  # marker sits inside removed footage
        if m["type"] == "callout" and m.get("note"):
            callouts.append({"t": t_o, "dur": 3.5, "text": m["note"]})
        elif m["type"] in ("zoom", "note", "mark"):
            tasks.append({"type": m["type"], "src_t": m["t"], "out_t": t_o, "step": m["step"], "note": m.get("note", ""), "frame": m.get("frame", "")})
    json.dump({"source": os.path.join(base, rec["file"]), "mode": S["mode"], "source_duration_s": dur, "output_duration_s": round(out_dur, 2),
               "segments": segs, "removed": merge(removed), "speedups": speeds, "steps": steps, "callouts": callouts, "editor_tasks": tasks,
               "chapters": [{"out_t": round(t, 2), "title": c} for t, c in chapters]},
              open(os.path.join(out, "edl.json"), "w"), indent=1)

    # ---- ffmpeg ----
    W, H = a.scale.split("x")
    fc, vlab, alab = [], [], []
    for i, s in enumerate(segs):
        fc.append(f"[0:v]trim=start={s['start']}:end={s['end']},setpts=(PTS-STARTPTS)/{s['speed']},fps=30,scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2,setsar=1[v{i}]")
        vlab.append(f"[v{i}]")
        if live:
            if s["speed"] == 1.0:
                fc.append(f"[0:a]atrim=start={s['start']}:end={s['end']},asetpts=PTS-STARTPTS,aresample=48000[a{i}]")
            else:
                d = (s["end"] - s["start"]) / s["speed"]
                fc.append(f"anullsrc=r=48000:cl=mono,atrim=0:{d:.3f}[a{i}]")
            alab.append(f"[a{i}]")
    n = len(segs)
    if live:
        fc.append("".join(f"{v}{al}" for v, al in zip(vlab, alab)) + f"concat=n={n}:v=1:a=1[vc][ac]")
    else:
        fc.append("".join(vlab) + f"concat=n={n}:v=1:a=0[vc]")
    last = "vc"
    fontopt = f":fontfile='{a.font}'" if a.font else ""
    for k, c in enumerate(callouts):
        fc.append(f"[{last}]drawtext=text='{esc_text(c['text'])}'{fontopt}:fontsize=44:fontcolor=white:box=1:boxcolor=0x000000AA:boxborderw=18:x=(w-text_w)/2:y=h-260:enable='between(t,{c['t']},{c['t'] + c['dur']})'[d{k}]")
        last = f"d{k}"
    cmd = ["ffmpeg", "-y", "-fflags", "+genpts", "-i", os.path.join(base, rec["file"]), "-filter_complex", ";".join(fc), "-map", f"[{last}]"]
    if live:
        cmd += ["-map", "[ac]", "-c:a", "aac", "-b:a", "160k"]
    cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p", "-movflags", "+faststart", os.path.join(out, "edited.mp4")]
    with open(os.path.join(out, "render.sh"), "w") as f:
        f.write("#!/usr/bin/env bash\nset -e\n" + " ".join(shlex.quote(c) for c in cmd) + "\n")
    print(f"segments {n}, source {dur:.1f}s -> output {out_dur:.1f}s, {len(callouts)} callouts, {len(tasks)} editor tasks")
    print("wrote", out)
    if a.run:
        r = subprocess.run(cmd)
        sys.exit(r.returncode)


if __name__ == "__main__":
    main()
