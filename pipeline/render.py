#!/usr/bin/env python3
"""Screen-capture explainer renderer.

Input: timeline.json (absolute times) with shots built from real browser screenshots,
camera moves, cursor moves/clicks, highlight boxes, captions and chapter labels.
Output: silent H.264 video (audio is muxed separately).

  python3 render.py timeline.json out_silent.mp4 [--preview t1,t2,...]
"""
import json, math, os, subprocess, sys, functools
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H, FPS, SS = 1920, 1080, 30, 2
_FD = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
FONT = os.path.join(_FD, "Inter-SemiBold.otf")
FONT_B = os.path.join(_FD, "Inter-Bold.otf")
FONT_R = os.path.join(_FD, "Inter-Regular.otf")
ACCENT = (255, 170, 40)


def font(size, path=FONT):
    return ImageFont.truetype(path, size)


def ease(x):
    x = min(1.0, max(0.0, x))
    return 4 * x ** 3 if x < 0.5 else 1 - (-2 * x + 2) ** 3 / 2


def lerp(a, b, t):
    return a + (b - a) * t


# ---------- static layers ----------
@functools.lru_cache(None)
def background():
    w, h = W * SS, H * SS
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    base = np.zeros((h, w, 3), np.float32)
    top, bot = np.array([18, 20, 38], np.float32), np.array([8, 9, 18], np.float32)
    t = (y / h)[..., None]
    base[:] = top * (1 - t) + bot * t
    for cx, cy, r, col in [(0.15, 0.2, 0.55, (60, 40, 140)), (0.9, 0.85, 0.6, (20, 90, 140)), (0.75, 0.1, 0.35, (120, 50, 90))]:
        d = np.sqrt((x / w - cx) ** 2 + ((y / h - cy) * h / w) ** 2) / r
        a = np.clip(1 - d, 0, 1) ** 2 * 0.35
        base += a[..., None] * (np.array(col, np.float32) - base) * 0.9
    return np.clip(base, 0, 255).astype(np.uint8)


def window_geom(sw, sh):
    bar = 44
    scale = min(1760 / sw, (H - 100 - bar) / sh)
    ww, wh = sw * scale, sh * scale + bar
    wx, wy = (W - ww) / 2, (H - wh) / 2
    return dict(scale=scale, bar=bar, wx=wx, wy=wy, ww=ww, wh=wh, ox=wx, oy=wy + bar)


@functools.lru_cache(None)
def browser_scene(path, url):
    """Background + browser window holding the screenshot, at SS x resolution. Returns (img, geom)."""
    shot = Image.open(path).convert("RGB")
    sw, sh = shot.size
    g = window_geom(sw, sh)
    k = SS
    canvas = Image.fromarray(background()).convert("RGBA")
    wx, wy, ww, wh, bar = [g[n] * k for n in ("wx", "wy", "ww", "wh", "bar")]
    # shadow
    sh_layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh_layer).rounded_rectangle([wx, wy + 18 * k, wx + ww, wy + wh + 18 * k], 16 * k, fill=(0, 0, 0, 170))
    sh_layer = sh_layer.filter(ImageFilter.GaussianBlur(28 * k))
    canvas.alpha_composite(sh_layer)
    win = Image.new("RGBA", (int(ww), int(wh)), (0, 0, 0, 0))
    d = ImageDraw.Draw(win)
    d.rounded_rectangle([0, 0, ww - 1, wh - 1], 14 * k, fill=(36, 38, 46, 255))
    for i, c in enumerate([(255, 95, 86), (255, 189, 46), (39, 201, 63)]):
        cx = (22 + i * 22) * k
        d.ellipse([cx - 6 * k, bar / 2 - 6 * k, cx + 6 * k, bar / 2 + 6 * k], fill=c)
    d.rounded_rectangle([110 * k, 9 * k, ww - 110 * k, bar - 9 * k], 8 * k, fill=(22, 23, 29, 255))
    d.text((128 * k, bar / 2), url, font=font(int(15 * k), FONT_R), fill=(190, 194, 205), anchor="lm")
    body = shot.resize((int(ww), int(wh - bar)), Image.LANCZOS)
    mask = Image.new("L", body.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, -20 * k, body.size[0] - 1, body.size[1] - 1], 14 * k, fill=255)
    win.paste(body, (0, int(bar)), mask)
    canvas.alpha_composite(win, (int(wx), int(wy)))
    return np.array(canvas.convert("RGB")), g


@functools.lru_cache(None)
def slide_scene(path):
    im = Image.open(path).convert("RGB")
    if im.size != (W * SS, H * SS):
        im = im.resize((W * SS, H * SS), Image.LANCZOS)
    return np.array(im), None


# ---------- sprites ----------
@functools.lru_cache(None)
def cursor_sprite():
    k = 4
    pts = [(0, 0), (0, 34), (9, 26), (15, 40), (21, 37), (15, 24), (27, 24)]
    im = Image.new("RGBA", (50 * k, 56 * k), (0, 0, 0, 0))
    sh = Image.new("RGBA", im.size, (0, 0, 0, 0))
    off = 6
    ImageDraw.Draw(sh).polygon([((x + off + 2) * k, (y + off + 3) * k) for x, y in pts], fill=(0, 0, 0, 140))
    sh = sh.filter(ImageFilter.GaussianBlur(3 * k))
    im.alpha_composite(sh)
    d = ImageDraw.Draw(im)
    d.polygon([((x + off) * k, (y + off) * k) for x, y in pts], fill=(255, 255, 255, 255), outline=(0, 0, 0, 255), width=int(2.2 * k))
    im = im.resize((50, 56), Image.LANCZOS)
    a = np.array(im).astype(np.float32)
    return a, (off, off)


def blend(frame, rgba, x, y):
    """Alpha-blend float RGBA sprite onto uint8 frame at integer x, y (top-left)."""
    h, w = rgba.shape[:2]
    x0, y0, x1, y1 = max(0, x), max(0, y), min(W, x + w), min(H, y + h)
    if x0 >= x1 or y0 >= y1:
        return
    s = rgba[y0 - y:y1 - y, x0 - x:x1 - x]
    a = s[..., 3:4] / 255.0
    roi = frame[y0:y1, x0:x1].astype(np.float32)
    frame[y0:y1, x0:x1] = (roi * (1 - a) + s[..., :3] * a).astype(np.uint8)


@functools.lru_cache(None)
def caption_sprite(text):
    f = font(42)
    maxw = 1560
    words, lines, cur = text.split(), [], ""
    for w_ in words:
        t = (cur + " " + w_).strip()
        if f.getlength(t) > maxw and cur:
            lines.append(cur)
            cur = w_
        else:
            cur = t
    lines.append(cur)
    lh = 56
    tw = int(max(f.getlength(l) for l in lines))
    pw, ph = tw + 56, lh * len(lines) + 26
    im = Image.new("RGBA", (pw, ph), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, pw - 1, ph - 1], 18, fill=(10, 11, 18, 205))
    for i, l in enumerate(lines):
        d.text((pw / 2, 13 + lh * i + lh / 2), l, font=f, fill=(255, 255, 255), anchor="mm")
    return np.array(im).astype(np.float32)


@functools.lru_cache(None)
def chapter_sprite(num, text):
    f1, f2 = font(26, FONT_B), font(30)
    n = f"{num:02d}"
    w1, w2 = f1.getlength(n), f2.getlength(text)
    pw, ph = int(w1 + w2 + 74), 58
    im = Image.new("RGBA", (pw, ph), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, pw - 1, ph - 1], 14, fill=(10, 11, 18, 215))
    d.rounded_rectangle([10, 10, 10 + w1 + 22, ph - 10], 9, fill=ACCENT)
    d.text((21 + w1 / 2, ph / 2), n, font=f1, fill=(20, 16, 8), anchor="mm")
    d.text((w1 + 48, ph / 2), text, font=f2, fill=(255, 255, 255), anchor="lm")
    return np.array(im).astype(np.float32)


@functools.lru_cache(None)
def label_sprite(text):
    f = font(30)
    pw, ph = int(f.getlength(text) + 40), 52
    im = Image.new("RGBA", (pw, ph), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, pw - 1, ph - 1], 12, fill=ACCENT + (255,))
    d.text((pw / 2, ph / 2), text, font=f, fill=(20, 16, 8), anchor="mm")
    return np.array(im).astype(np.float32)


@functools.lru_cache(None)
def lower_third_sprite(title, sub):
    f1, f2 = font(40, FONT_B), font(28, FONT_R)
    pw = int(max(f1.getlength(title), f2.getlength(sub)) + 80)
    ph = 118
    im = Image.new("RGBA", (pw, ph), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, pw - 1, ph - 1], 16, fill=(255, 255, 255, 245))
    d.rectangle([0, 18, 8, ph - 18], fill=ACCENT)
    d.text((34, 20), title, font=f1, fill=(18, 20, 28))
    d.text((34, 70), sub, font=f2, fill=(70, 75, 90))
    return np.array(im).astype(np.float32)


# ---------- per-shot state ----------
def camera_rect(shot, t):
    """Camera rect in output (1x scene) coords at time t."""
    full = (0.0, 0.0, float(W), float(H))
    cur = full
    for kf in shot.get("camera", []):
        tgt = to_scene_rect(shot, kf["rect"]) if kf.get("rect") else full
        t0, dur = kf["t"], kf.get("dur", 1.0)
        if t <= t0:
            break
        p = ease((t - t0) / dur)
        cur = tuple(lerp(a, b, p) for a, b in zip(cur, tgt)) if p < 1 else tgt
    # gentle drift so stills never look frozen
    drift = shot.get("drift", 0.012)
    if drift:
        span = max(1e-3, shot["end"] - shot["start"])
        p = (t - shot["start"]) / span
        z = 1 - drift * p
        cx, cy = cur[0] + cur[2] / 2, cur[1] + cur[3] / 2
        cur = (cx - cur[2] * z / 2, cy - cur[3] * z / 2, cur[2] * z, cur[3] * z)
    return cur


def to_scene_rect(shot, r):
    """Screenshot-pixel rect [x,y,w,h] -> 16:9 scene rect containing it."""
    g = shot["_geom"]
    if g is None:
        x, y, w, h = r
    else:
        x, y = g["ox"] + r[0] * g["scale"], g["oy"] + r[1] * g["scale"]
        w, h = r[2] * g["scale"], r[3] * g["scale"]
    cx, cy = x + w / 2, y + h / 2
    if w / h > W / H:
        h = w * H / W
    else:
        w = h * W / H
    w, h = min(w, W), min(h, H)
    x = min(max(0, cx - w / 2), W - w)
    y = min(max(0, cy - h / 2), H - h)
    return (x, y, w, h)


def to_scene_pt(shot, p):
    g = shot["_geom"]
    if g is None:
        return p
    return (g["ox"] + p[0] * g["scale"], g["oy"] + p[1] * g["scale"])


def cursor_state(shot, t):
    evs = shot.get("cursor", [])
    if not evs:
        return None
    pos = to_scene_pt(shot, evs[0]["pos"])
    click_age = None
    for i, e in enumerate(evs):
        tgt = to_scene_pt(shot, e["pos"])
        mv = e.get("move", 0.7)
        if t < e["t"] - mv:
            break
        p = ease((t - (e["t"] - mv)) / mv) if mv > 0 else 1
        pos = (lerp(pos[0], tgt[0], p), lerp(pos[1], tgt[1], p)) if p < 1 else tgt
        if e.get("click") and t >= e["t"]:
            click_age = t - e["t"]
    return pos, click_age


def render_shot(shot, t):
    if shot["kind"] == "browser":
        scene, geom = browser_scene(shot["image"], shot.get("url", ""))
    else:
        scene, geom = slide_scene(shot["image"])
    shot["_geom"] = geom
    if shot.get("states"):  # slide with timed alternative images (e.g. roadmap progress)
        img = shot["image"]
        for st in shot["states"]:
            if t >= st["t"]:
                img = st["image"]
        scene, _ = slide_scene(img)
    cx, cy, cw, ch = camera_rect(shot, t)
    k = SS
    patch = cv2.getRectSubPix(scene, (max(2, int(round(cw * k))), max(2, int(round(ch * k)))), ((cx + cw / 2) * k, (cy + ch / 2) * k))
    interp = cv2.INTER_AREA if cw * k > W else cv2.INTER_CUBIC
    frame = cv2.resize(patch, (W, H), interpolation=interp)
    zoom = W / cw

    def proj(px, py):
        return ((px - cx) * zoom, (py - cy) * zoom)

    # highlight boxes
    for hb in shot.get("highlights", []):
        if not (hb["t0"] <= t <= hb["t1"]):
            continue
        a = min(1, (t - hb["t0"]) / 0.35, (hb["t1"] - t) / 0.3)
        x, y = to_scene_pt(shot, hb["rect"][:2])
        g = shot["_geom"]
        s = g["scale"] if g else 1
        x0, y0 = proj(x, y)
        x1, y1 = proj(x + hb["rect"][2] * s, y + hb["rect"][3] * s)
        pad = 8
        over = frame.copy()
        cv2.rectangle(over, (int(x0 - pad), int(y0 - pad)), (int(x1 + pad), int(y1 + pad)), ACCENT, 5, cv2.LINE_AA)
        frame[:] = cv2.addWeighted(over, a, frame, 1 - a, 0)
        if hb.get("label"):
            spr = label_sprite(hb["label"])
            lx = int(min(max(20, x0 - pad), W - spr.shape[1] - 20))
            ly = int(y0 - pad - spr.shape[0] - 10) if y0 - pad - 62 > 20 else int(y1 + pad + 10)
            blend(frame, spr * np.array([1, 1, 1, a], np.float32), lx, ly)
    # cursor
    cs = cursor_state(shot, t)
    if cs:
        (px, py), click_age = cs
        sx, sy = proj(px, py)
        if click_age is not None and click_age < 0.6:
            r = 10 + 46 * ease(click_age / 0.6)
            al = 1 - click_age / 0.6
            over = frame.copy()
            cv2.circle(over, (int(sx), int(sy)), int(r), ACCENT, 4, cv2.LINE_AA)
            cv2.circle(over, (int(sx), int(sy)), int(r * 0.45), ACCENT, -1, cv2.LINE_AA)
            frame[:] = cv2.addWeighted(over, al * 0.85, frame, 1 - al * 0.85, 0)
        spr, (ox, oy) = cursor_sprite()
        blend(frame, spr, int(sx - ox), int(sy - oy))
    return frame


def render_frame(tl, t):
    shots = tl["shots"]
    xf = tl.get("crossfade", 0.4)
    cur = None
    for i, s in enumerate(shots):
        if s["start"] <= t < s["end"] or (i == len(shots) - 1 and t >= s["start"]):
            cur = i
    if cur is None:
        cur = 0
    frame = render_shot(shots[cur], t)
    s = shots[cur]
    if cur > 0 and t - s["start"] < xf and s.get("transition", "fade") == "fade":
        prev = render_shot(shots[cur - 1], t)
        a = ease((t - s["start"]) / xf)
        frame = cv2.addWeighted(frame, a, prev, 1 - a, 0)
    # chapter label
    for c in tl.get("chapters_ui", []):
        if c["t0"] <= t <= c["t1"]:
            spr = chapter_sprite(c["num"], c["text"])
            a = min(1, (t - c["t0"]) / 0.4, (c["t1"] - t) / 0.4)
            slide = int((1 - ease(min(1, (t - c["t0"]) / 0.4))) * -30)
            blend(frame, spr * np.array([1, 1, 1, a], np.float32), 40 + slide, 34)
    # lower thirds
    for c in tl.get("lower_thirds", []):
        if c["t0"] <= t <= c["t1"]:
            spr = lower_third_sprite(c["title"], c["sub"])
            p = ease(min(1, (t - c["t0"]) / 0.5))
            a = min(1, (t - c["t0"]) / 0.3, (c["t1"] - t) / 0.4)
            blend(frame, spr * np.array([1, 1, 1, a], np.float32), int(60 - (1 - p) * 80), H - 330)
    # captions
    for c in tl.get("captions", []):
        if c["t0"] <= t < c["t1"]:
            spr = caption_sprite(c["text"])
            a = min(1, (t - c["t0"]) / 0.12, (c["t1"] - t) / 0.12)
            blend(frame, spr * np.array([1, 1, 1, a], np.float32), (W - spr.shape[1]) // 2, H - 52 - spr.shape[0])
    # fade from/to black
    fi, fo = tl.get("fade_in", 0.6), tl.get("fade_out", 1.0)
    if t < fi:
        frame = (frame * (t / fi)).astype(np.uint8)
    if t > tl["duration"] - fo:
        frame = (frame * max(0, (tl["duration"] - t) / fo)).astype(np.uint8)
    return frame


def main():
    tl = json.load(open(sys.argv[1]))
    out = sys.argv[2]
    if "--preview" in sys.argv:
        ts = [float(x) for x in sys.argv[sys.argv.index("--preview") + 1].split(",")]
        for t in ts:
            f = render_frame(tl, t)
            cv2.imwrite(f"{out}_{t:07.2f}.jpg", cv2.cvtColor(f, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 88])
        return
    import os
    n = int(tl["duration"] * FPS)
    a0 = int(os.environ.get('F0', 0)); n = min(n, int(os.environ.get('F1', n)))
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                           "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", out], stdin=subprocess.PIPE)
    for i in range(a0, n):
        ff.stdin.write(render_frame(tl, i / FPS).tobytes())
        if i % 150 == 0:
            print(f"frame {i}/{n}", flush=True)
    ff.stdin.close()
    ff.wait()
    print("done", out)


if __name__ == "__main__":
    main()
