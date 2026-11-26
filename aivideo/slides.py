"""Render each Scene to a 1920×1080 PNG with Pillow.

Visual styles
-------------
auto       – dark gradient (default, context-aware accent colour)
classic    – clean white/light background, editorial typography
whiteboard – white background, hand-drawn feel, blue marker colour
kawaii     – soft pastel background, rounded cards, playful feel
"""
import os
import math
import random
from PIL import Image, ImageDraw, ImageFont

W, H = 1920, 1080
FONT_DIRS = ["C:/Windows/Fonts", "/usr/share/fonts/truetype/dejavu",
             "/usr/share/fonts/dejavu", "/Library/Fonts"]

# ── theme palettes ────────────────────────────────────────────────────────────
THEMES = {
    "auto": {
        "bg_top":  (10, 18, 35),   "bg_mid": (15, 28, 52),  "bg_bot": (20, 35, 60),
        "accent":  (56, 189, 248), "accent2":(251,191, 36), "green":  (74, 222,128),
        "red":     (248,113,113),  "purple": (167,139,250), "text":   (241,245,249),
        "muted":   (148,163,184),  "card":   (20, 32, 55),  "line":   (30, 48, 80),
        "dark": True,
    },
    "classic": {
        "bg_top":  (248,250,252),  "bg_mid": (241,245,249), "bg_bot": (226,232,240),
        "accent":  (37, 99,235),   "accent2":(217, 70,  0), "green":  (22,163, 74),
        "red":     (220, 38, 38),  "purple": (124, 58,237), "text":   (15, 23, 42),
        "muted":   (71, 85,105),   "card":   (255,255,255), "line":   (203,213,225),
        "dark": False,
    },
    "whiteboard": {
        "bg_top":  (255,255,255),  "bg_mid": (253,253,253), "bg_bot": (248,248,248),
        "accent":  (30, 100,200),  "accent2":(220, 90,  0), "green":  (20,140, 60),
        "red":     (200, 40, 40),  "purple": (110, 60,200), "text":   (20, 20, 30),
        "muted":   (100,110,130),  "card":   (245,248,255), "line":   (200,210,230),
        "dark": False,
        "sketchy": True,
    },
    "kawaii": {
        "bg_top":  (255,240,250),  "bg_mid": (248,228,255), "bg_bot": (228,240,255),
        "accent":  (219, 39,119),  "accent2":(245,158, 11), "green":  (16,185,129),
        "red":     (239, 68, 68),  "purple": (139, 92,246), "text":   (30, 20, 40),
        "muted":   (140,110,160),  "card":   (255,250,255), "line":   (230,210,240),
        "dark": False,
        "kawaii": True,
    },
}

ICON_GLYPH = {
    "book":"B","health":"+","money":"$","science":"⚗","code":"</>",
    "globe":"◉","people":"⬡","idea":"✦","warning":"!","check":"✓",
}
ICON_COLOR_KEY = {
    "book":"accent","health":"green","money":"accent2","science":"purple",
    "code":"accent","globe":"green","people":"accent2","idea":"accent2",
    "warning":"red","check":"green",
}


def _font(size, bold=False):
    names = ["arialbd.ttf","DejaVuSans-Bold.ttf"] if bold else ["arial.ttf","DejaVuSans.ttf"]
    for d in FONT_DIRS:
        for n in names:
            p = os.path.join(d, n)
            if os.path.exists(p):
                try:
                    return ImageFont.truetype(p, size)
                except Exception:
                    pass
    return ImageFont.load_default()


def _wrap(draw, text, font, max_w):
    words, lines, cur = text.split(), [], ""
    for w in words:
        test = (cur + " " + w).strip()
        if draw.textlength(test, font=font) <= max_w:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def _bg(draw, T):
    """Gradient background using theme top/mid/bot colours."""
    for y in range(H):
        t = y / H
        if t < 0.5:
            t2 = t * 2
            c = tuple(int(T["bg_top"][i]*(1-t2) + T["bg_mid"][i]*t2) for i in range(3))
        else:
            t2 = (t - 0.5) * 2
            c = tuple(int(T["bg_mid"][i]*(1-t2) + T["bg_bot"][i]*t2) for i in range(3))
        draw.line([(0, y), (W, y)], fill=c)


def _sketchy_rect(draw, x0, y0, x1, y1, color, width=3):
    """Slightly wobbly rectangle to simulate whiteboard marker."""
    rng = random.Random(x0 + y0)
    def jitter(v): return v + rng.randint(-3, 3)
    pts = [(jitter(x0),jitter(y0)),(jitter(x1),jitter(y0)),
           (jitter(x1),jitter(y1)),(jitter(x0),jitter(y1)),(jitter(x0),jitter(y0))]
    draw.line(pts, fill=color, width=width)


def _kawaii_star(draw, cx, cy, r, color):
    """Small 4-point star decoration."""
    pts = []
    for i in range(8):
        angle = math.pi * i / 4 - math.pi/8
        radius = r if i % 2 == 0 else r * 0.45
        pts.append((cx + radius*math.cos(angle), cy + radius*math.sin(angle)))
    draw.polygon(pts, fill=color)


def _badge(draw, icon, cx, cy, r, T):
    color = T.get(ICON_COLOR_KEY.get(icon, "accent"), T["accent"])
    sketchy = T.get("sketchy", False)
    kawaii  = T.get("kawaii",  False)
    if kawaii:
        # soft rounded square
        draw.rounded_rectangle([cx-r, cy-r, cx+r, cy+r], r//3, fill=color)
        _kawaii_star(draw, cx+r-10, cy-r+10, 12, T["accent2"])
    elif sketchy:
        _sketchy_rect(draw, cx-r, cy-r, cx+r, cy+r, color, width=4)
        draw.rounded_rectangle([cx-r+6, cy-r+6, cx+r-6, cy+r-6], 4, fill=color)
    else:
        for extra in range(16, 0, -4):
            glow = tuple(int(c*0.07) for c in color)
            draw.ellipse([cx-r-extra, cy-r-extra, cx+r+extra, cy+r+extra], fill=glow)
        draw.ellipse([cx-r, cy-r, cx+r, cy+r], fill=color)
    glyph = ICON_GLYPH.get(icon, "●")
    fs = 56 if len(glyph) <= 2 else 38
    f = _font(fs, bold=True)
    draw.text((cx, cy), glyph, font=f, fill=T["bg_top"] if not T["dark"] else T["bg_top"], anchor="mm")


def _progress_bar(draw, index, total, T):
    bw = W - 160
    x0, y = 80, H - 28
    draw.rounded_rectangle([x0, y, x0+bw, y+8], 4, fill=T["line"])
    if total > 1:
        fw = int(bw * index / (total - 1))
        if fw > 0:
            draw.rounded_rectangle([x0, y, x0+fw, y+8], 4, fill=T["accent"])
    draw.text((W-60, H-36), f"{index+1} / {total}", font=_font(28), fill=T["muted"], anchor="rm")


def _takeaway_strip(draw, text, T):
    if not text:
        return
    a2 = T["accent2"]
    bg = tuple(int(c*0.15) for c in a2) if T["dark"] else tuple(min(255, int(c*1.1)) for c in T["card"])
    draw.rectangle([80, H-100, W-80, H-50], fill=bg)
    draw.rectangle([80, H-102, 90, H-50], fill=a2)
    t = text[:115] + ("…" if len(text) > 115 else "")
    draw.text((110, H-76), "KEY INSIGHT  →  " + t, font=_font(26), fill=a2)


# ── scene renderers ───────────────────────────────────────────────────────────

def render_title(draw, scene, index, total, T):
    sketchy = T.get("sketchy", False)
    kawaii  = T.get("kawaii",  False)
    color   = T[ICON_COLOR_KEY.get(scene.icon, "accent")]

    _badge(draw, scene.icon, W//2, 290, 95, T)

    # decorative rule
    if sketchy:
        _sketchy_rect(draw, W//2-180, 418, W//2+180, 422, color, width=5)
    elif kawaii:
        draw.rounded_rectangle([W//2-180, 416, W//2+180, 426], 5, fill=T["accent"])
        for x in range(W//2-160, W//2+160, 40):
            _kawaii_star(draw, x, 420, 7, T["accent2"])
    else:
        draw.rectangle([W//2-180, 418, W//2+180, 422], fill=T["accent"])

    f_big = _font(96, bold=True)
    lines = _wrap(draw, scene.title, f_big, W-320)
    y = 460
    for ln in lines[:3]:
        draw.text((W//2, y), ln, font=f_big, fill=T["text"], anchor="mt")
        y += 110

    if scene.narration:
        f_sub = _font(40)
        for ln in _wrap(draw, scene.narration[:130], f_sub, W-400)[:2]:
            draw.text((W//2, y+16), ln, font=f_sub, fill=T["muted"], anchor="mt")
            y += 54

    # bottom bar
    if kawaii:
        draw.rounded_rectangle([0, H-18, W, H], 0, fill=T["accent"])
        draw.rounded_rectangle([0, H-18, W, H], 0, fill=T["accent2"])
    else:
        draw.rectangle([0, H-12, W, H], fill=color)


def render_bullets(draw, scene, index, total, T):
    color  = T[ICON_COLOR_KEY.get(scene.icon, "accent")]
    sketchy= T.get("sketchy", False)
    kawaii = T.get("kawaii",  False)

    # left accent bar
    if sketchy:
        _sketchy_rect(draw, 0, 0, 14, H, color, width=6)
    elif kawaii:
        draw.rounded_rectangle([0, 40, 14, H-40], 7, fill=color)
    else:
        draw.rectangle([0, 0, 14, H], fill=color)

    _badge(draw, scene.icon, 130, 130, 60, T)
    f_title = _font(72, bold=True)
    title_lines = _wrap(draw, scene.title, f_title, W-300)
    ty = 90
    for ln in title_lines[:2]:
        draw.text((230, ty), ln, font=f_title, fill=T["text"])
        ty += 84

    # underline
    ul_w = min(620, int(draw.textlength(scene.title, font=f_title)))
    if sketchy:
        _sketchy_rect(draw, 230, ty+4, 230+ul_w, ty+9, color, width=4)
    else:
        draw.rectangle([230, ty+4, 230+ul_w, ty+10], fill=color)

    # bullet cards
    f_b    = _font(50)
    f_bnum = _font(30, bold=True)
    y = ty + 50
    for i, b in enumerate(scene.bullets[:4]):
        if y > H - 220:
            break
        cx, cy = 100, y + 36
        blines   = _wrap(draw, b, f_b, W-310)
        card_h   = len(blines[:2]) * 60 + 24

        if kawaii:
            draw.rounded_rectangle([140, y, W-80, y+card_h], 18, fill=T["card"],
                                   outline=color, width=2)
            draw.ellipse([cx-26, cy-26, cx+26, cy+26], fill=color)
            _kawaii_star(draw, W-100, y+card_h//2, 10, T["accent2"])
        elif sketchy:
            _sketchy_rect(draw, 140, y, W-80, y+card_h, color, width=2)
            draw.rectangle([142, y+2, W-82, y+card_h-2], fill=T["card"])
            draw.ellipse([cx-26, cy-26, cx+26, cy+26], fill=color)
        else:
            draw.rounded_rectangle([140, y, W-80, y+card_h], 10, fill=T["card"])
            draw.ellipse([cx-26, cy-26, cx+26, cy+26], fill=color)

        draw.text((cx, cy), str(i+1), font=f_bnum, fill=T["bg_top"] if T["dark"] else (255,255,255), anchor="mm")
        by = y + 12
        for ln in blines[:2]:
            draw.text((180, by), ln, font=f_b, fill=T["text"])
            by += 60
        y += card_h + 22


def render_quiz(draw, scene, index, total, T):
    draw.rectangle([0, 0, 14, H], fill=T["accent2"])
    _badge(draw, "check", 130, 120, 55, T)
    draw.text((220, 90), "KNOWLEDGE CHECK", font=_font(44, bold=True), fill=T["accent2"])

    f_q = _font(54, bold=True)
    q_lines = _wrap(draw, scene.question, f_q, W-220)
    y = 200
    for ln in q_lines[:3]:
        draw.text((110, y), ln, font=f_q, fill=T["text"])
        y += 70

    f_opt = _font(44)
    opt_colors = [T["accent"], T["green"], T["red"], T["purple"]]
    y += 30
    for i, opt in enumerate(scene.options[:4]):
        color   = opt_colors[i % len(opt_colors)]
        correct = i == scene.answer_index
        bg      = tuple(int(c*0.15) for c in color) if T["dark"] else tuple(min(255,int(c*0.12)+235) for c in color)
        draw.rounded_rectangle([110, y, W-110, y+100], 16, fill=bg,
                               outline=color if correct else T["line"], width=3 if correct else 1)
        draw.ellipse([126, y+22, 170, y+66], fill=color)
        draw.text((148, y+44), "ABCD"[i], font=_font(30, bold=True),
                  fill=(255,255,255) if T["dark"] else T["card"], anchor="mm")
        draw.text((195, y+50), opt[:72], font=f_opt, fill=T["text"], anchor="lm")
        if correct:
            draw.text((W-130, y+50), "✓ Correct", font=_font(30, bold=True), fill=color, anchor="rm")
        y += 125


def render_flashcard(draw, scene, index, total, T):
    color = T["purple"]
    draw.rectangle([0, 0, 14, H], fill=color)
    _badge(draw, "book", 130, 110, 50, T)
    draw.text((210, 85), "FLASHCARDS", font=_font(50, bold=True), fill=T["text"])
    draw.text((210, 145), f"{len(scene.flashcards)} cards to reinforce your learning",
              font=_font(32), fill=T["muted"])

    cards = scene.flashcards[:4]
    cols  = 2
    cw    = (W-160) // cols
    ch    = min((H-300) // max(math.ceil(len(cards)/cols), 1), 240)

    for i, card in enumerate(cards):
        col, row = i%cols, i//cols
        x0, y0   = 80+col*cw, 220+row*ch
        draw.rounded_rectangle([x0, y0, x0+cw-20, y0+ch-20], 14, fill=T["card"])
        draw.rounded_rectangle([x0, y0, x0+cw-20, y0+8],     14, fill=color)
        f_front = _font(26, bold=True)
        f_back  = _font(30)
        front_lines = _wrap(draw, card["front"], f_front, cw-50)
        back_lines  = _wrap(draw, card["back"],  f_back,  cw-50)
        y = y0 + 24
        for ln in front_lines[:2]:
            draw.text((x0+20, y), ln, font=f_front, fill=T["muted"])
            y += 32
        draw.line([(x0+20, y), (x0+cw-40, y)], fill=T["line"], width=1)
        y += 10
        for ln in back_lines[:2]:
            draw.text((x0+20, y), ln, font=f_back, fill=T["text"])
            y += 36


def render_summary(draw, scene, index, total, T):
    color  = T["green"]
    kawaii = T.get("kawaii", False)

    draw.rectangle([0, 0, 14, H], fill=color)
    _badge(draw, "check", 130, 120, 60, T)
    draw.text((220, 88), scene.title, font=_font(72, bold=True), fill=color)
    draw.rectangle([220, 170, 700, 176], fill=T["accent2"])

    f_b = _font(48)
    y   = 220
    for b in scene.bullets[:5]:
        if y > H-250:
            break
        draw.text((160, y), "▸", font=f_b, fill=T["accent2"])
        for ln in _wrap(draw, b, f_b, W-280)[:2]:
            draw.text((220, y), ln, font=f_b, fill=T["text"])
            y += 58
        y += 16

    # completion band
    band_color = (15, 35, 15) if T["dark"] else (220, 255, 220)
    text_color = color
    draw.rectangle([0, H-130, W, H-50], fill=band_color)
    msg = "🎓  You've completed this lesson. Well done." if not kawaii else "✨  Amazing work! You finished the lesson! 🌟"
    draw.text((W//2, H-90), msg, font=_font(38, bold=True), fill=text_color, anchor="mm")


# ── public entry points ───────────────────────────────────────────────────────

def render_scene(scene, index, total, path, style="auto"):
    T = THEMES.get(style, THEMES["auto"])
    img  = Image.new("RGB", (W, H))
    draw = ImageDraw.Draw(img)
    _bg(draw, T)

    if   scene.kind == "title":     render_title(draw, scene, index, total, T)
    elif scene.kind == "quiz":      render_quiz(draw, scene, index, total, T)
    elif scene.kind == "flashcard": render_flashcard(draw, scene, index, total, T)
    elif scene.kind == "summary":   render_summary(draw, scene, index, total, T)
    else:
        render_bullets(draw, scene, index, total, T)
        try:
            from .visual_engine import make_graphic
            graphic = make_graphic(scene, T, size=(860, 500))
            img.paste(graphic, (1022, 220))
        except Exception:
            pass

    _progress_bar(draw, index, total, T)
    _takeaway_strip(draw, scene.takeaway, T)
    img.save(path, optimize=True)
    return path


def render_all(plan, outdir, style="auto"):
    os.makedirs(outdir, exist_ok=True)
    total = len(plan.scenes)
    return [render_scene(s, i, total, os.path.join(outdir, f"slide_{i:02d}.png"), style)
            for i, s in enumerate(plan.scenes)]
