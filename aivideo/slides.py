"""Render each Scene to a 1920×1080 PNG.

Layout rules (no overlap, nothing clipped):
  Title scene   — full-width centred layout
  Bullets scene — left panel: icon + title + bullet cards (x 0..1000)
                  right panel: smart visual from assets.py  (x 1020..1900)
  Quiz scene    — full-width
  Flashcard     — full-width
  Summary       — full-width

Visual styles:
  auto       — dark navy gradient (default)
  classic    — light editorial
  whiteboard — white, sketchy marker lines
  kawaii     — pastel, rounded, playful
"""
import math
import os
import random

from PIL import Image, ImageDraw, ImageFont

from .assets import make_visual, choose_visual_spec

W, H = 1920, 1080
# Left text panel: x 0..1005   Right visual panel: x 1020..1900
TEXT_W = 1005          # max x for text content
VIS_X  = 1020          # start x of visual panel
VIS_W  = 860           # width of visual  (matches assets.W)
VIS_H  = 540           # height of visual (matches assets.H)
VIS_Y  = 220           # top y of visual panel

FONT_DIRS = [
    "C:/Windows/Fonts",
    "/usr/share/fonts/truetype/dejavu",
    "/usr/share/fonts/dejavu",
    "/Library/Fonts",
]

# ── themes ────────────────────────────────────────────────────────────────────
THEMES = {
    "auto": {
        "bg_top":  (10, 18, 35),  "bg_mid": (15, 28, 52),  "bg_bot": (20, 35, 60),
        "accent":  (56, 189, 248), "accent2": (251, 191, 36), "green":  (74, 222, 128),
        "red":     (248, 113, 113), "purple": (167, 139, 250), "text":   (241, 245, 249),
        "muted":   (148, 163, 184), "card":   (20, 32, 55),   "line":   (30, 48, 80),
        "dark": True,
    },
    "classic": {
        "bg_top":  (248, 250, 252), "bg_mid": (241, 245, 249), "bg_bot": (226, 232, 240),
        "accent":  (37, 99, 235),   "accent2": (217, 70, 0),   "green":  (22, 163, 74),
        "red":     (220, 38, 38),   "purple": (124, 58, 237),  "text":   (15, 23, 42),
        "muted":   (71, 85, 105),   "card":   (255, 255, 255), "line":   (203, 213, 225),
        "dark": False,
    },
    "whiteboard": {
        "bg_top":  (255, 255, 255), "bg_mid": (253, 253, 253), "bg_bot": (248, 248, 248),
        "accent":  (30, 100, 200),  "accent2": (220, 90, 0),   "green":  (20, 140, 60),
        "red":     (200, 40, 40),   "purple": (110, 60, 200),  "text":   (20, 20, 30),
        "muted":   (100, 110, 130), "card":   (245, 248, 255), "line":   (200, 210, 230),
        "dark": False, "sketchy": True,
    },
    "kawaii": {
        "bg_top":  (255, 240, 250), "bg_mid": (248, 228, 255), "bg_bot": (228, 240, 255),
        "accent":  (219, 39, 119),  "accent2": (245, 158, 11), "green":  (16, 185, 129),
        "red":     (239, 68, 68),   "purple": (139, 92, 246),  "text":   (30, 20, 40),
        "muted":   (140, 110, 160), "card":   (255, 250, 255), "line":   (230, 210, 240),
        "dark": False, "kawaii": True,
    },
}

ICON_COLOR_KEY = {
    "book": "accent", "health": "green", "money": "accent2",
    "science": "purple", "code": "accent", "globe": "green",
    "people": "accent2", "idea": "accent2", "warning": "red", "check": "green",
}

ICON_GLYPH = {
    "book": "B", "health": "+", "money": "$", "science": "⚗",
    "code": "</>", "globe": "◉", "people": "⬡", "idea": "✦",
    "warning": "!", "check": "✓",
}


# ── helpers ───────────────────────────────────────────────────────────────────

def _font(size, bold=False):
    names = ["arialbd.ttf", "DejaVuSans-Bold.ttf"] if bold else ["arial.ttf", "DejaVuSans.ttf"]
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
        try:
            ok = draw.textlength(test, font=font) <= max_w
        except Exception:
            ok = True
        if ok:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def _bg(draw, T):
    for y in range(H):
        t = y / H
        if t < 0.5:
            t2 = t * 2
            c = tuple(int(T["bg_top"][i] * (1 - t2) + T["bg_mid"][i] * t2) for i in range(3))
        else:
            t2 = (t - 0.5) * 2
            c = tuple(int(T["bg_mid"][i] * (1 - t2) + T["bg_bot"][i] * t2) for i in range(3))
        draw.line([(0, y), (W, y)], fill=c)


def _sketchy_rect(draw, x0, y0, x1, y1, color, width=3):
    rng = random.Random(x0 + y0)
    jitter = lambda v: v + rng.randint(-3, 3)
    pts = [(jitter(x0), jitter(y0)), (jitter(x1), jitter(y0)),
           (jitter(x1), jitter(y1)), (jitter(x0), jitter(y1)),
           (jitter(x0), jitter(y0))]
    draw.line(pts, fill=color, width=width)


def _kawaii_star(draw, cx, cy, r, color):
    pts = []
    for i in range(8):
        angle = math.pi * i / 4 - math.pi / 8
        radius = r if i % 2 == 0 else r * 0.45
        pts.append((cx + radius * math.cos(angle), cy + radius * math.sin(angle)))
    draw.polygon(pts, fill=color)


def _badge(draw, icon, cx, cy, r, T):
    color = T.get(ICON_COLOR_KEY.get(icon, "accent"), T["accent"])
    sketchy = T.get("sketchy", False)
    kawaii  = T.get("kawaii",  False)
    if kawaii:
        draw.rounded_rectangle([cx - r, cy - r, cx + r, cy + r], r // 3, fill=color)
        _kawaii_star(draw, cx + r - 10, cy - r + 10, 12, T["accent2"])
    elif sketchy:
        _sketchy_rect(draw, cx - r, cy - r, cx + r, cy + r, color, width=4)
        draw.rounded_rectangle([cx - r + 6, cy - r + 6, cx + r - 6, cy + r - 6], 4, fill=color)
    else:
        for extra in range(16, 0, -4):
            draw.ellipse([cx - r - extra, cy - r - extra, cx + r + extra, cy + r + extra],
                         fill=tuple(int(c * 0.07) for c in color))
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color)
    glyph = ICON_GLYPH.get(icon, "●")
    fs = 54 if len(glyph) <= 2 else 36
    draw.text((cx, cy), glyph, font=_font(fs, bold=True),
              fill=(10, 18, 35) if not T["dark"] else (10, 18, 35), anchor="mm")


def _progress_bar(draw, index, total, T):
    bw = W - 160
    x0, y = 80, H - 28
    draw.rounded_rectangle([x0, y, x0 + bw, y + 8], 4, fill=T["line"])
    if total > 1:
        fw = int(bw * index / (total - 1))
        if fw > 0:
            draw.rounded_rectangle([x0, y, x0 + fw, y + 8], 4, fill=T["accent"])
    draw.text((W - 60, H - 36), f"{index + 1} / {total}",
              font=_font(28), fill=T["muted"], anchor="rm")


def _takeaway_strip(draw, text, T):
    if not text:
        return
    a2 = T["accent2"]
    bg = tuple(int(c * 0.15) for c in a2) if T["dark"] \
        else tuple(min(255, int(c * 1.1)) for c in T["card"])
    draw.rectangle([80, H - 100, W - 80, H - 50], fill=bg)
    draw.rectangle([80, H - 102, 90, H - 50], fill=a2)
    t = text[:115] + ("..." if len(text) > 115 else "")
    draw.text((110, H - 76), "KEY INSIGHT  →  " + t, font=_font(26), fill=a2)


# ── visual panel embed ────────────────────────────────────────────────────────

def _embed_visual(img, scene, T):
    """Render the right-panel visual and paste it onto img."""
    try:
        visual_type, spec = choose_visual_spec(scene)
        graphic = make_visual(visual_type, spec, T)
        # Resize if needed (should already be 860x540)
        if graphic.size != (VIS_W, VIS_H):
            graphic = graphic.resize((VIS_W, VIS_H), Image.LANCZOS)
        img.paste(graphic, (VIS_X, VIS_Y))
        # Label the visual type (small, bottom right of panel)
        draw = ImageDraw.Draw(img)
        label = visual_type.replace("_", " ").title()
        draw.text((VIS_X + VIS_W - 10, VIS_Y + VIS_H + 8), label,
                  font=_font(18), fill=T["muted"], anchor="rb")
    except Exception as e:
        print(f"[slides] visual embed failed ({e}), skipping.")


# ── scene renderers ───────────────────────────────────────────────────────────

def render_title(draw, scene, index, total, T):
    color  = T[ICON_COLOR_KEY.get(scene.icon, "accent")]
    kawaii = T.get("kawaii", False)
    sketchy = T.get("sketchy", False)

    _badge(draw, scene.icon, W // 2, 270, 100, T)

    # decorative rule
    rx = W // 2
    if sketchy:
        _sketchy_rect(draw, rx - 190, 408, rx + 190, 414, color, width=5)
    elif kawaii:
        draw.rounded_rectangle([rx - 190, 406, rx + 190, 418], 6, fill=T["accent"])
        for x in range(rx - 170, rx + 170, 42):
            _kawaii_star(draw, x, 412, 7, T["accent2"])
    else:
        draw.rectangle([rx - 190, 408, rx + 190, 414], fill=T["accent"])

    f_big = _font(96, bold=True)
    lines = _wrap(draw, scene.title, f_big, W - 320)
    y = 448
    for ln in lines[:3]:
        draw.text((W // 2, y), ln, font=f_big, fill=T["text"], anchor="mt")
        y += 110

    if scene.narration:
        f_sub = _font(40)
        for ln in _wrap(draw, scene.narration[:140], f_sub, W - 400)[:2]:
            draw.text((W // 2, y + 16), ln, font=f_sub, fill=T["muted"], anchor="mt")
            y += 54

    draw.rectangle([0, H - 12, W, H], fill=color)


def render_bullets(draw, img, scene, index, total, T):
    """Two-column layout: text left (0..1005), visual right (1020..1900)."""
    color  = T[ICON_COLOR_KEY.get(scene.icon, "accent")]
    sketchy = T.get("sketchy", False)
    kawaii  = T.get("kawaii",  False)

    # Left accent bar
    if sketchy:
        _sketchy_rect(draw, 0, 0, 14, H, color, width=6)
    elif kawaii:
        draw.rounded_rectangle([0, 40, 14, H - 40], 7, fill=color)
    else:
        draw.rectangle([0, 0, 14, H], fill=color)

    # Right panel background
    rp_bg = tuple(max(0, c - 4) for c in T.get("card", (20, 32, 55)))
    draw.rounded_rectangle([VIS_X - 8, VIS_Y - 10,
                             VIS_X + VIS_W + 8, VIS_Y + VIS_H + 24],
                            12, fill=rp_bg)

    # Icon badge + title  (constrained to left panel)
    _badge(draw, scene.icon, 128, 128, 58, T)
    f_title = _font(68, bold=True)
    title_lines = _wrap(draw, scene.title, f_title, TEXT_W - 220)
    ty = 88
    for ln in title_lines[:2]:
        draw.text((224, ty), ln, font=f_title, fill=T["text"])
        ty += 80

    # Underline
    ul_w = min(580, int(draw.textlength(scene.title, font=f_title)))
    if sketchy:
        _sketchy_rect(draw, 224, ty + 4, 224 + ul_w, ty + 9, color, width=4)
    else:
        draw.rectangle([224, ty + 4, 224 + ul_w, ty + 10], fill=color)

    # Bullet cards  (constrained to x 140..TEXT_W-30)
    f_b    = _font(46)
    f_bnum = _font(28, bold=True)
    y = ty + 46
    for i, b in enumerate(scene.bullets[:4]):
        if y > H - 230:
            break
        blines  = _wrap(draw, b, f_b, TEXT_W - 220)
        card_h  = len(blines[:2]) * 56 + 22
        cx_num, cy_num = 98, y + 34

        if kawaii:
            draw.rounded_rectangle([138, y, TEXT_W - 20, y + card_h], 18,
                                   fill=T["card"], outline=color, width=2)
            draw.ellipse([cx_num - 25, cy_num - 25, cx_num + 25, cy_num + 25], fill=color)
            _kawaii_star(draw, TEXT_W - 36, y + card_h // 2, 10, T["accent2"])
        elif sketchy:
            _sketchy_rect(draw, 138, y, TEXT_W - 20, y + card_h, color, width=2)
            draw.rectangle([140, y + 2, TEXT_W - 22, y + card_h - 2], fill=T["card"])
            draw.ellipse([cx_num - 25, cy_num - 25, cx_num + 25, cy_num + 25], fill=color)
        else:
            draw.rounded_rectangle([138, y, TEXT_W - 20, y + card_h], 10, fill=T["card"])
            draw.ellipse([cx_num - 25, cy_num - 25, cx_num + 25, cy_num + 25], fill=color)

        draw.text((cx_num, cy_num), str(i + 1), font=f_bnum,
                  fill=(10, 18, 35), anchor="mm")
        by = y + 11
        for ln in blines[:2]:
            draw.text((174, by), ln, font=f_b, fill=T["text"])
            by += 56
        y += card_h + 20

    # Embed visual in right panel
    _embed_visual(img, scene, T)


def render_quiz(draw, scene, index, total, T):
    draw.rectangle([0, 0, 14, H], fill=T["accent2"])
    _badge(draw, "check", 128, 118, 54, T)
    draw.text((218, 88), "KNOWLEDGE CHECK", font=_font(44, bold=True), fill=T["accent2"])

    f_q = _font(52, bold=True)
    q_lines = _wrap(draw, scene.question, f_q, W - 220)
    y = 196
    for ln in q_lines[:3]:
        draw.text((108, y), ln, font=f_q, fill=T["text"])
        y += 68

    opt_colors = [T["accent"], T["green"], T["red"], T["purple"]]
    y += 28
    f_opt = _font(42)
    for i, opt in enumerate(scene.options[:4]):
        col     = opt_colors[i % len(opt_colors)]
        correct = i == scene.answer_index
        bg = tuple(int(c * 0.15) for c in col) if T["dark"] \
             else tuple(min(255, int(c * 0.12) + 235) for c in col)
        draw.rounded_rectangle([108, y, W - 108, y + 96], 16,
                               fill=bg, outline=col if correct else T["line"],
                               width=3 if correct else 1)
        draw.ellipse([124, y + 20, 166, y + 62], fill=col)
        draw.text((145, y + 41), "ABCD"[i], font=_font(28, bold=True),
                  fill=(255, 255, 255), anchor="mm")
        draw.text((192, y + 48), opt[:74], font=f_opt, fill=T["text"], anchor="lm")
        if correct:
            draw.text((W - 128, y + 48), "✓ Correct",
                      font=_font(28, bold=True), fill=col, anchor="rm")
        y += 120


def render_flashcard(draw, scene, index, total, T):
    color = T["purple"]
    draw.rectangle([0, 0, 14, H], fill=color)
    _badge(draw, "book", 128, 108, 50, T)
    draw.text((208, 83), "FLASHCARDS", font=_font(50, bold=True), fill=T["text"])
    draw.text((208, 143), f"{len(scene.flashcards)} cards to reinforce your learning",
              font=_font(30), fill=T["muted"])

    cards = scene.flashcards[:4]
    cols  = 2
    cw    = (W - 160) // cols
    ch    = min((H - 300) // max(math.ceil(len(cards) / cols), 1), 240)
    for i, card in enumerate(cards):
        col2, row = i % cols, i // cols
        x0, y0   = 80 + col2 * cw, 220 + row * ch
        draw.rounded_rectangle([x0, y0, x0 + cw - 20, y0 + ch - 20], 14, fill=T["card"])
        draw.rounded_rectangle([x0, y0, x0 + cw - 20, y0 + 8], 14, fill=color)
        f_front = _font(24, bold=True)
        f_back  = _font(28)
        front_lns = _wrap(draw, card["front"], f_front, cw - 50)
        back_lns  = _wrap(draw, card["back"],  f_back,  cw - 50)
        y = y0 + 22
        for ln in front_lns[:2]:
            draw.text((x0 + 18, y), ln, font=f_front, fill=T["muted"])
            y += 30
        draw.line([(x0 + 18, y), (x0 + cw - 38, y)], fill=T["line"], width=1)
        y += 8
        for ln in back_lns[:2]:
            draw.text((x0 + 18, y), ln, font=f_back, fill=T["text"])
            y += 34


def render_summary(draw, scene, index, total, T):
    color  = T["green"]
    kawaii = T.get("kawaii", False)

    draw.rectangle([0, 0, 14, H], fill=color)
    _badge(draw, "check", 128, 118, 60, T)
    draw.text((218, 86), scene.title, font=_font(70, bold=True), fill=color)
    draw.rectangle([218, 168, 680, 174], fill=T["accent2"])

    f_b = _font(46)
    y   = 214
    for b in scene.bullets[:5]:
        if y > H - 250:
            break
        draw.text((158, y), "▸", font=f_b, fill=T["accent2"])
        for ln in _wrap(draw, b, f_b, W - 270)[:2]:
            draw.text((218, y), ln, font=f_b, fill=T["text"])
            y += 56
        y += 14

    band = (15, 35, 15) if T["dark"] else (220, 255, 220)
    draw.rectangle([0, H - 128, W, H - 50], fill=band)
    msg = ("🎓  Lesson complete! Well done." if not kawaii
           else "✨  Amazing work! You finished the lesson! 🌟")
    draw.text((W // 2, H - 89), msg, font=_font(36, bold=True),
              fill=color, anchor="mm")


# ── public entry points ───────────────────────────────────────────────────────

def render_scene(scene, index, total, path, style="auto"):
    T    = THEMES.get(style, THEMES["auto"])
    img  = Image.new("RGB", (W, H))
    draw = ImageDraw.Draw(img)
    _bg(draw, T)

    if scene.kind == "title":
        render_title(draw, scene, index, total, T)
    elif scene.kind == "quiz":
        render_quiz(draw, scene, index, total, T)
    elif scene.kind == "flashcard":
        render_flashcard(draw, scene, index, total, T)
    elif scene.kind == "summary":
        render_summary(draw, scene, index, total, T)
    else:
        # bullets / debate / critique — two-column layout
        render_bullets(draw, img, scene, index, total, T)

    _progress_bar(draw, index, total, T)
    _takeaway_strip(draw, scene.takeaway, T)
    img.save(path, optimize=True)
    return path


def render_all(plan, outdir, style="auto"):
    os.makedirs(outdir, exist_ok=True)
    total = len(plan.scenes)
    return [
        render_scene(s, i, total, os.path.join(outdir, f"slide_{i:02d}.png"), style)
        for i, s in enumerate(plan.scenes)
    ]
