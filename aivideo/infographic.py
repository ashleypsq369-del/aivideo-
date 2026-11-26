"""Generate a tall infographic (1080×1920) from a ScenePlan using Pillow.
Uses the same theme dict as slides.py so style is consistent.
"""
import os
from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1920
FONT_DIRS = ["C:/Windows/Fonts", "/usr/share/fonts/truetype/dejavu",
             "/usr/share/fonts/dejavu", "/Library/Fonts"]


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


def render_infographic(plan, path, style="auto"):
    from .slides import THEMES
    T = THEMES.get(style, THEMES["auto"])

    ac   = T.get("accent",  (56, 189, 248))
    ac2  = T.get("accent2", (251, 191, 36))
    gr   = T.get("green",   (74, 222, 128))
    rd   = T.get("red",     (248, 113, 113))
    pu   = T.get("purple",  (167, 139, 250))
    txt  = T.get("text",    (241, 245, 249))
    mu   = T.get("muted",   (148, 163, 184))
    card = T.get("card",    (20, 32, 55))
    bg   = T.get("bg_top",  (10, 18, 35))

    STEP_COLORS = [ac, ac2, gr, pu, rd]

    img  = Image.new("RGB", (W, H), bg)
    draw = ImageDraw.Draw(img)

    # gradient background
    for y in range(H):
        t2 = y / H
        c  = tuple(int(T["bg_top"][i] * (1 - t2) + T["bg_bot"][i] * t2) for i in range(3))
        draw.line([(0, y), (W, y)], fill=c)

    # header
    draw.line([(40, 210), (W - 40, 210)], fill=ac, width=2)
    f_topic = _font(56, bold=True)
    for ln in _wrap(draw, plan.topic, f_topic, W - 80)[:2]:
        draw.text((W // 2, 60), ln, font=f_topic, fill=txt, anchor="mt")
    draw.text((W // 2, 148), "Key insights at a glance",
              font=_font(28), fill=mu, anchor="mt")

    # content scenes
    content = [s for s in plan.scenes if s.kind in ("bullets", "summary")][:6]
    if not content:
        img.save(path)
        return path

    card_h = min(260, (H - 280) // max(len(content), 1))
    pad    = 28

    y = 240
    for i, scene in enumerate(content):
        color = STEP_COLORS[i % len(STEP_COLORS)]
        x0, x1 = pad, W - pad

        # card
        draw.rounded_rectangle([x0, y, x1, y + card_h - 10], 16, fill=card)
        draw.rounded_rectangle([x0, y, x0 + 8, y + card_h - 10], 4, fill=color)

        # step circle
        draw.ellipse([x0 + 18, y + 12, x0 + 58, y + 52], fill=color)
        draw.text((x0 + 38, y + 32), str(i + 1), font=_font(26, bold=True),
                  fill=(10, 18, 35), anchor="mm")

        # title
        draw.text((x0 + 72, y + 18), scene.title[:42],
                  font=_font(32, bold=True), fill=color)

        # bullets
        f_b = _font(24)
        by  = y + 62
        for b in scene.bullets[:3]:
            if by + 34 > y + card_h - 14:
                break
            draw.ellipse([x0 + 72, by + 10, x0 + 88, by + 26], fill=color)
            draw.text((x0 + 100, by), b[:56] + ("..." if len(b) > 56 else ""),
                      font=f_b, fill=txt)
            by += 36

        # takeaway
        if scene.takeaway and by + 34 <= y + card_h - 10:
            draw.line([(x0 + 72, by), (x1 - 18, by)], fill=mu, width=1)
            draw.text((x0 + 76, by + 6),
                      "→ " + scene.takeaway[:72] + ("..." if len(scene.takeaway) > 72 else ""),
                      font=_font(21), fill=mu)

        y += card_h

    # footer
    draw.line([(40, H - 58), (W - 40, H - 58)], fill=ac, width=1)
    draw.text((W // 2, H - 38), "aivideo Studio  •  " + plan.topic,
              font=_font(22), fill=mu, anchor="mm")

    img.save(path)
    return path
