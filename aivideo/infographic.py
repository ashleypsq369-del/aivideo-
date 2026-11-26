"""Generate a tall infographic (1080×1920) from a ScenePlan using Pillow."""
import os
from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1920
FONT_DIRS = ["C:/Windows/Fonts", "/usr/share/fonts/truetype/dejavu", "/Library/Fonts"]

THEME = {
    "bg":       (10, 18, 35),
    "card":     (20, 30, 50),
    "accent":   (56, 189, 248),
    "accent2":  (251, 191, 36),
    "green":    (74, 222, 128),
    "red":      (248, 113, 113),
    "purple":   (167, 139, 250),
    "text":     (241, 245, 249),
    "muted":    (148, 163, 184),
}
STEP_COLORS = [THEME["accent"], THEME["accent2"], THEME["green"], THEME["purple"], THEME["red"]]


def _font(size, bold=False):
    names = ["arialbd.ttf", "DejaVuSans-Bold.ttf"] if bold else ["arial.ttf", "DejaVuSans.ttf"]
    for d in FONT_DIRS:
        for n in names:
            p = os.path.join(d, n)
            if os.path.exists(p):
                return ImageFont.truetype(p, size)
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


def render_infographic(plan, path):
    img = Image.new("RGB", (W, H), THEME["bg"])
    draw = ImageDraw.Draw(img)

    # header gradient band
    for y in range(220):
        t = y / 220
        c = tuple(int(THEME["accent"][i] * (1-t) * 0.3 + THEME["bg"][i] * (0.7 + t * 0.3)) for i in range(3))
        draw.line([(0, y), (W, y)], fill=c)

    # title
    draw.rectangle([0, 0, W, 220], fill=None)
    draw.line([(40, 210), (W-40, 210)], fill=THEME["accent"], width=2)
    f_topic = _font(58, bold=True)
    topic_lines = _wrap(draw, plan.topic, f_topic, W - 80)
    y = 30
    for ln in topic_lines[:2]:
        draw.text((W//2, y), ln, font=f_topic, fill=THEME["text"], anchor="mt")
        y += 70
    draw.text((W//2, y + 10), f"Key insights at a glance", font=_font(28),
              fill=THEME["muted"], anchor="mt")

    # content scenes
    content = [s for s in plan.scenes if s.kind in ("bullets", "summary")][:6]
    card_h = (H - 280) // max(len(content), 1)
    card_h = min(card_h, 280)
    pad = 30

    y = 240
    for i, scene in enumerate(content):
        color = STEP_COLORS[i % len(STEP_COLORS)]
        x0, x1 = pad, W - pad

        # card background
        draw.rounded_rectangle([x0, y, x1, y + card_h - 10], 16, fill=THEME["card"])
        # left accent bar
        draw.rounded_rectangle([x0, y, x0 + 8, y + card_h - 10], 4, fill=color)
        # step number circle
        draw.ellipse([x0 + 20, y + 14, x0 + 60, y + 54], fill=color)
        f_num = _font(28, bold=True)
        draw.text((x0 + 40, y + 34), str(i + 1), font=f_num, fill=THEME["bg"], anchor="mm")

        # scene title
        f_title = _font(34, bold=True)
        draw.text((x0 + 76, y + 20), scene.title[:40], font=f_title, fill=color)

        # bullets
        f_b = _font(26)
        by = y + 66
        for b in scene.bullets[:3]:
            if by + 36 > y + card_h - 16:
                break
            draw.ellipse([x0 + 76, by + 10, x0 + 92, by + 26], fill=color)
            draw.text((x0 + 104, by), b[:55] + ("…" if len(b) > 55 else ""),
                      font=f_b, fill=THEME["text"])
            by += 38

        # takeaway
        if scene.takeaway and by + 36 <= y + card_h - 10:
            draw.line([(x0 + 76, by), (x1 - 20, by)], fill=THEME["muted"], width=1)
            draw.text((x0 + 80, by + 6),
                      "→ " + scene.takeaway[:70] + ("…" if len(scene.takeaway) > 70 else ""),
                      font=_font(23), fill=THEME["muted"])

        y += card_h

    # footer
    draw.line([(40, H - 60), (W - 40, H - 60)], fill=THEME["accent"], width=1)
    draw.text((W//2, H - 40), "aivideo Studio  •  " + plan.topic,
              font=_font(24), fill=THEME["muted"], anchor="mm")

    img.save(path)
    return path
