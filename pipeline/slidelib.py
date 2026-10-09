#!/usr/bin/env python3
"""Spec-driven slide renderer (3840x2160 PNGs) - same look as the hand-built Ep 1/2 slides.

scene = {"id","label","title","elements":[...], "states":[{"i":sentence_idx,"frac":0..1,"off":secs}, ...]}
State 0 is the initial state; each entry in "states" starts the next one. Elements are stacked top to bottom.
Every element accepts "from" (first state it is visible in, default 0) and "to" (first state it is hidden in).

  tiles : {"type":"tiles","items":[{"big":"4","small":"vCPU","from":0}],"glow":[0],"h":200,"bs":64}
  term  : {"type":"term","title":"root@awx-lab","lines":["$ cmd","output"],"hl":{"1":[0]},"size":30}
          ("$ " lines are commands; hl maps state -> highlighted line indexes)
  cards : {"type":"cards","items":[{"title":"..","sub":"..","mono":false,"from":1}],"numbered":true}
          (the item whose "from" equals the state glows)
  note  : {"type":"note","title":"..","sub":"..","mono_sub":"..","red":false,"glow":true}
  pill  : {"type":"pill","text":"..","red":false}
"""
import math, os
from PIL import Image, ImageDraw, ImageFilter, ImageFont
import render

K = 2
W, H = 1920 * K, 1080 * K
ACC = (255, 170, 40)
WHITE, DIM, GREEN, RED = (255, 255, 255), (150, 155, 170), (90, 220, 140), (255, 95, 95)
FD = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
MONO = os.path.join(FD, "DejaVuSansMono.ttf")


def F(size, w="SemiBold"):
    return ImageFont.truetype(os.path.join(FD, f"Inter-{w}.otf"), int(size * K))


def M(size):
    return ImageFont.truetype(MONO, int(size * K))


def base(hexes=False):
    im = Image.fromarray(render.background()).convert("RGBA")
    if hexes:
        d = ImageDraw.Draw(im)
        for (cx, cy, r, a) in [(1600, 260, 120, 40), (1745, 345, 70, 30), (1700, 820, 160, 22), (230, 900, 90, 26)]:
            pts = [((cx + r * math.cos(math.pi / 3 * i + math.pi / 6)) * K, (cy + r * math.sin(math.pi / 3 * i + math.pi / 6)) * K) for i in range(6)]
            d.polygon(pts, outline=ACC + (a + 40,), width=3 * K)
    return im


def card(im, x, y, w, h, on=True, glow=False, fill=None, r=24):
    if glow:
        g = Image.new("RGBA", im.size, (0, 0, 0, 0))
        ImageDraw.Draw(g).rounded_rectangle([x * K, y * K, (x + w) * K, (y + h) * K], r * K, outline=ACC + (150,), width=8 * K)
        im.alpha_composite(g.filter(ImageFilter.GaussianBlur(10 * K)))
    lay = Image.new("RGBA", im.size, (0, 0, 0, 0))
    ImageDraw.Draw(lay).rounded_rectangle([x * K, y * K, (x + w) * K, (y + h) * K], r * K, fill=fill or (255, 255, 255, 26 if on else 10),
                                          outline=(ACC + (255,)) if glow else (255, 255, 255, 50), width=(4 if glow else 2) * K)
    im.alpha_composite(lay)
    return ImageDraw.Draw(im)


def head(label, title):
    im = base()
    d = ImageDraw.Draw(im)
    d.text((140 * K, 70 * K), label, font=F(26, "Bold"), fill=ACC)
    d.text((140 * K, 112 * K), title, font=F(52, "Bold"), fill=WHITE)
    return im


def term(im, x, y, w, lines, hl=(), size=30, title="root@awx-lab"):
    lh = int(size * 1.6)
    h = 70 + lh * len(lines) + 30
    lay = Image.new("RGBA", im.size, (0, 0, 0, 0))
    ImageDraw.Draw(lay).rounded_rectangle([x * K, y * K, (x + w) * K, (y + h) * K], 22 * K, fill=(10, 12, 20, 235), outline=(255, 255, 255, 60), width=2 * K)
    im.alpha_composite(lay)
    d = ImageDraw.Draw(im)
    for i, c in enumerate([(255, 95, 86), (255, 189, 46), (39, 201, 63)]):
        d.ellipse([(x + 28 + i * 30) * K, (y + 24) * K, (x + 46 + i * 30) * K, (y + 42) * K], fill=c)
    d.text(((x + w / 2) * K, (y + 33) * K), title, font=F(20, "Regular"), fill=DIM, anchor="mm")
    for i, ln in enumerate(lines):
        ty = y + 70 + i * lh
        if i in hl:
            hlay = Image.new("RGBA", im.size, (0, 0, 0, 0))
            ImageDraw.Draw(hlay).rounded_rectangle([(x + 14) * K, (ty - 4) * K, (x + w - 14) * K, (ty + lh - 8) * K], 10 * K, fill=ACC + (60,), outline=ACC + (230,), width=3 * K)
            im.alpha_composite(hlay)
            d = ImageDraw.Draw(im)
        if ln.startswith("$ "):
            d.text(((x + 34) * K, ty * K), "$", font=M(size), fill=GREEN)
            d.text(((x + 34 + size * 1.25) * K, ty * K), ln[2:], font=M(size), fill=WHITE)
        else:
            d.text(((x + 34) * K, ty * K), ln, font=M(size), fill=(200, 205, 220))
    return h


def tile(im, x, y, w, h, big, small, on=True, glow=False, bs=64):
    d = card(im, x, y, w, h, on=on, glow=glow)
    d.text(((x + w / 2) * K, (y + h * 0.40) * K), big, font=F(bs, "Bold"), fill=ACC if on else DIM, anchor="mm")
    d.text(((x + w / 2) * K, (y + h * 0.76) * K), small, font=F(28, "Regular"), fill=WHITE if on else DIM, anchor="mm")


def pill(im, cx, cy, text, fill=ACC, fg=(20, 16, 8), size=34):
    d = ImageDraw.Draw(im)
    f = F(size, "Bold")
    tw = f.getlength(text)
    d.rounded_rectangle([cx * K - tw / 2 - 36 * K, (cy - 34) * K, cx * K + tw / 2 + 36 * K, (cy + 34) * K], 30 * K, fill=fill)
    d.text((cx * K, cy * K), text, font=f, fill=fg, anchor="mm")


GAP, TOP, LEFT, CW = 36, 220, 140, 1640


def visible(e, s):
    return e.get("from", 0) <= s and (e.get("to") is None or s < e["to"])


def draw_element(im, e, s, y):
    """Draw one element at y for state s; return its height."""
    t = e["type"]
    if t == "tiles":
        items = e["items"]
        n = len(items)
        cols = e.get("cols", n)
        h = e.get("h", 200)
        gap = 30
        w = (CW - gap * (cols - 1)) / cols
        rows = math.ceil(n / cols)
        for i, it in enumerate(items):
            on = it.get("from", e.get("from", 0)) <= s
            if not on and not e.get("ghost", True):
                continue
            x = LEFT + (i % cols) * (w + gap)
            yy = y + (i // cols) * (h + gap)
            tile(im, x, yy, w, h, it["big"], it["small"], on=on, glow=on and (s in e.get("glow", []) or s in it.get("glow_at", [])), bs=e.get("bs", 64))
        return rows * h + (rows - 1) * gap
    if t == "term":
        hl = e.get("hl", {}).get(str(s), [])
        return term(im, LEFT, y, CW, e["lines"], hl=hl, size=e.get("size", 30), title=e.get("title", "root@awx-lab"))
    if t == "cards":
        rh, gap = e.get("h", 125), 25
        for i, it in enumerate(e["items"]):
            fr = it.get("from", i + 1)
            on = s >= fr
            yy = y + i * (rh + gap)
            d = card(im, LEFT, yy, CW, rh, on=on, glow=(s == fr))
            tx = 190
            if e.get("numbered", True):
                d.text((190 * K, (yy + rh / 2) * K), str(i + 1), font=F(54, "Bold"), fill=ACC if on else DIM, anchor="lm")
                tx = 270
            sub = it.get("sub")
            if sub and e.get("stacked", False):
                d.text((tx * K, (yy + rh * 0.36) * K), it["title"], font=F(42, "Bold"), fill=WHITE if on else DIM, anchor="lm")
                d.text((tx * K, (yy + rh * 0.72) * K), sub, font=F(30, "Regular"), fill=(215, 220, 232) if on else DIM, anchor="lm")
            else:
                d.text((tx * K, (yy + rh / 2) * K), it["title"], font=M(34) if it.get("mono") else F(42, "Bold"), fill=WHITE if on else DIM, anchor="lm")
                if sub:
                    d.text(((LEFT + CW - 50) * K, (yy + rh / 2) * K), sub, font=F(36), fill=(230, 232, 240) if on else DIM, anchor="rm")
        return len(e["items"]) * (rh + gap) - gap
    if t == "note":
        h = e.get("h", 150 if not e.get("mono_sub") else 190)
        d = card(im, LEFT, y, CW, h, glow=e.get("glow", True), fill=(255, 95, 95, 40) if e.get("red") else None)
        d.text(((LEFT + 50) * K, (y + h * 0.33) * K), e["title"], font=F(42, "Bold"), fill=WHITE, anchor="lm")
        yy = y + h * 0.60
        if e.get("mono_sub"):
            d.text(((LEFT + 50) * K, yy * K), e["mono_sub"], font=M(26), fill=(255, 215, 150), anchor="lm")
            yy += 42
        if e.get("sub"):
            d.text(((LEFT + 50) * K, (yy if e.get("mono_sub") else y + h * 0.70) * K), e["sub"], font=F(28, "Regular"), fill=(230, 232, 240), anchor="lm")
        return h
    if t == "pill":
        pill(im, 960, y + 40, e["text"], fill=RED if e.get("red") else ACC, fg=WHITE if e.get("red") else (20, 16, 8))
        return 80
    raise ValueError("unknown element type " + t)


def n_states(scene):
    return len(scene.get("states", [])) + 1 + scene.get("extra_states", 0)


def render_scene_state(scene, s):
    im = head(scene["label"], scene["title"])
    y = TOP
    for e in scene["elements"]:
        if not visible(e, s):
            continue
        y += draw_element(im, e, s, y) + GAP
    return im


def title_card(ep):
    im = base(True)
    d = ImageDraw.Draw(im)
    d.text((160 * K, 300 * K), (ep.get("series") or "AWX FROM ZERO").upper(), font=F(30, "Bold"), fill=ACC)
    d.text((160 * K, 360 * K), f"Episode {ep['number']}", font=F(96, "Bold"), fill=WHITE)
    d.text((160 * K, 500 * K), ep["title"], font=F(64), fill=(235, 238, 245))
    if ep.get("subtitle"):
        d.text((160 * K, 580 * K), ep["subtitle"], font=F(64), fill=(235, 238, 245))
    lay = Image.new("RGBA", im.size, (0, 0, 0, 0))
    t = f"{ep.get('channel', 'Venu Automates')}  ·  {ep.get('handle', '@VenAutomates')}"
    tw = F(30, "Regular").getlength(t)
    ImageDraw.Draw(lay).rounded_rectangle([160 * K, 720 * K, 160 * K + tw + 56 * K, 782 * K], 16 * K, fill=(255, 255, 255, 34))
    im.alpha_composite(lay)
    ImageDraw.Draw(im).text((188 * K, 751 * K), t, font=F(30, "Regular"), fill=(225, 228, 238), anchor="lm")
    return im


def end_card(ep):
    nx = ep.get("next", {})
    im = base(True)
    d = ImageDraw.Draw(im)
    d.text((W / 2, 230 * K), "NEXT EPISODE", font=F(30, "Bold"), fill=ACC, anchor="mm")
    d.text((W / 2, 330 * K), nx.get("title", ""), font=F(84, "Bold"), fill=WHITE, anchor="mm")
    d.text((W / 2, 430 * K), nx.get("sub", ""), font=F(40, "Regular"), fill=(215, 220, 232), anchor="mm")
    bw, bh = 520, 110
    bx, by = (1920 - bw) / 2, 560
    d.rounded_rectangle([bx * K, by * K, (bx + bw) * K, (by + bh) * K], 55 * K, fill=(230, 33, 23))
    d.text((960 * K, (by + bh / 2) * K), "SUBSCRIBE", font=F(46, "Bold"), fill=WHITE, anchor="mm")
    d.text((W / 2, 745 * K), ep.get("handle", "@VenAutomates"), font=F(34, "Bold"), fill=ACC, anchor="mm")
    d.text((W / 2, 800 * K), f"Commands for this episode: {ep.get('folder', '')} folder", font=F(30, "Regular"), fill=(190, 195, 210), anchor="mm")
    d.text((W / 2, 855 * K), ep.get("repo", "github.com/Venuvgp19/Youtube-Tutorials-Awx"), font=F(40), fill=WHITE, anchor="mm")
    return im


def render_all(spec, outdir):
    """Write title.png, end.png and <scene>_<state>.png for every slide scene. Returns list of files."""
    os.makedirs(outdir, exist_ok=True)
    made = []

    def save(im, name):
        p = os.path.join(outdir, name + ".png")
        im.convert("RGB").save(p)
        made.append(p)

    save(title_card(spec["episode"]), "title")
    for sc in spec["scenes"]:
        if sc.get("kind", "slide") != "slide":
            continue
        for s in range(n_states(sc)):
            save(render_scene_state(sc, s), f"{sc['id']}_{s}")
    save(end_card(spec["episode"]), "end")
    return made
