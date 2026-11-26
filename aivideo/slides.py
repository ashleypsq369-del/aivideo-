"""Render each Scene to a 1920x1080 PNG with Pillow (no browser needed)."""
import os
from PIL import Image, ImageDraw, ImageFont

W, H = 1920, 1080
FONT_DIRS = ["/usr/share/fonts/truetype/dejavu", "/usr/share/fonts/dejavu", "C:/Windows/Fonts", "/Library/Fonts"]
THEME = {
    "bg_top": (15, 23, 42), "bg_bottom": (30, 41, 59), "accent": (56, 189, 248),
    "accent2": (251, 191, 36), "text": (241, 245, 249), "muted": (148, 163, 184), "good": (74, 222, 128),
}
GLYPH = {"book": "B", "health": "+", "money": "$", "science": "A", "code": "</>", "globe": "G", "people": "P"}


def _font(size, bold=False):
    names = ["DejaVuSans-Bold.ttf", "arialbd.ttf"] if bold else ["DejaVuSans.ttf", "arial.ttf"]
    for d in FONT_DIRS:
        for n in names:
            p = os.path.join(d, n)
            if os.path.exists(p):
                return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def _background():
    img = Image.new("RGB", (W, H))
    px = ImageDraw.Draw(img)
    for y in range(H):
        t = y / H
        c = tuple(int(THEME["bg_top"][i] * (1 - t) + THEME["bg_bottom"][i] * t) for i in range(3))
        px.line([(0, y), (W, y)], fill=c)
    return img


def _wrap(draw, text, font, max_w):
    words, lines, cur = text.split(), [], ""
    for w in words:
        test = f"{cur} {w}".strip()
        if draw.textlength(test, font=font) <= max_w:
            cur = test
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def _badge(draw, icon, cx, cy, r=70):
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=THEME["accent"])
    f = _font(64 if len(GLYPH.get(icon, "B")) == 1 else 44, True)
    draw.text((cx, cy), GLYPH.get(icon, "B"), font=f, fill=THEME["bg_top"], anchor="mm")


def render_scene(scene, index, total, path):
    img = _background()
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, 18, H], fill=THEME["accent"])
    d.text((W - 80, H - 50), f"{index + 1} / {total}", font=_font(30), fill=THEME["muted"], anchor="rm")

    if scene.kind == "title":
        _badge(d, scene.icon, W // 2, 330, 90)
        lines = _wrap(d, scene.title, _font(110, True), W - 360)
        y = 520
        for ln in lines:
            d.text((W // 2, y), ln, font=_font(110, True), fill=THEME["text"], anchor="mm")
            y += 130
        d.rectangle([W // 2 - 120, y + 20, W // 2 + 120, y + 28], fill=THEME["accent2"])
    elif scene.kind == "quiz":
        _badge(d, "book", 160, 150, 60)
        d.text((260, 150), scene.title, font=_font(72, True), fill=THEME["accent2"], anchor="lm")
        y = 300
        for ln in _wrap(d, scene.question, _font(58, True), W - 300):
            d.text((150, y), ln, font=_font(58, True), fill=THEME["text"])
            y += 80
        y += 40
        for i, opt in enumerate(scene.options):
            d.rounded_rectangle([150, y, W - 150, y + 110], 24, outline=THEME["accent"], width=4)
            d.text((200, y + 55), f"{'ABCD'[i]}.  {opt}"[:80], font=_font(46), fill=THEME["text"], anchor="lm")
            y += 140
    else:  # bullets / summary
        _badge(d, scene.icon, 160, 150, 60)
        d.text((260, 150), scene.title, font=_font(80, True), fill=THEME["text"], anchor="lm")
        d.rectangle([150, 245, 450, 252], fill=THEME["accent2"])
        y = 340
        for b in scene.bullets[:4]:
            lines = _wrap(d, b, _font(54), W - 400)
            d.ellipse([160, y + 20, 184, y + 44], fill=THEME["accent"])
            for ln in lines[:3]:
                d.text((220, y), ln, font=_font(54), fill=THEME["text"])
                y += 72
            y += 50
    img.save(path)
    return path


def render_all(plan, outdir):
    os.makedirs(outdir, exist_ok=True)
    total = len(plan.scenes)
    return [render_scene(s, i, total, os.path.join(outdir, f"slide_{i:02d}.png")) for i, s in enumerate(plan.scenes)]
