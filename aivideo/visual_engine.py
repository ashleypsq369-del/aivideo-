"""Smart topic-aware graphic generator.
Produces an 860x500 Pillow Image with an explanatory diagram for the scene icon/topic.
"""
import math
import os
import re
from PIL import Image, ImageDraw, ImageFont

W, H = 860, 500
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
            if draw.textlength(test, font=font) <= max_w:
                cur = test
            else:
                if cur:
                    lines.append(cur)
                cur = w
        except Exception:
            cur = test
    if cur:
        lines.append(cur)
    return lines


def _extract_numbers(bullets):
    pairs = []
    for b in bullets:
        nums = re.findall(r"(\d+(?:\.\d+)?)", b)
        if nums:
            pairs.append((b[:30].rstrip(), float(nums[0])))
    return pairs[:5]


def _draw_health(draw, scene, T):
    ac  = T.get("accent",  (56, 189, 248))
    ac2 = T.get("accent2", (251, 191, 36))
    gr  = T.get("green",   (74, 222, 128))
    rd  = T.get("red",     (248, 113, 113))
    txt = T.get("text",    (241, 245, 249))
    mu  = T.get("muted",   (148, 163, 184))
    cx, cy = W // 2, H // 2 + 20
    draw.ellipse([cx-55, cy-200, cx+55, cy-100], outline=ac, width=3)
    draw.rounded_rectangle([cx-70, cy-100, cx+70, cy+120], 20, outline=ac, width=3)
    draw.line([(cx-70, cy-80), (cx-140, cy+20)], fill=ac, width=4)
    draw.line([(cx+70, cy-80), (cx+140, cy+20)], fill=ac, width=4)
    draw.line([(cx-35, cy+120), (cx-50, cy+230)], fill=ac, width=5)
    draw.line([(cx+35, cy+120), (cx+50, cy+230)], fill=ac, width=5)
    for ox, oy, lbl, col, lx, ly in [
        (cx,    cy-150, "Brain", ac2, -170, -20),
        (cx-20, cy-50,  "Heart", rd,  -170,  60),
        (cx+20, cy-30,  "Lungs", ac,   100, -40),
        (cx,    cy+40,  "Gut",   gr,   100,  60),
    ]:
        draw.ellipse([ox-18, oy-18, ox+18, oy+18], fill=col)
        ex, ey = cx+lx, cy+ly
        draw.line([(ox, oy), (ex, ey)], fill=mu, width=1)
        draw.rounded_rectangle([ex-50, ey-14, ex+50, ey+14], 7,
                                fill=T.get("card", (20, 32, 55)), outline=col, width=1)
        draw.text((ex, ey), lbl, font=_font(20), fill=txt, anchor="mm")


def _draw_science(draw, scene, T):
    ac  = T.get("accent",  (56, 189, 248))
    ac2 = T.get("accent2", (251, 191, 36))
    pu  = T.get("purple",  (167, 139, 250))
    gr  = T.get("green",   (74, 222, 128))
    cx, cy = W // 2, H // 2
    draw.ellipse([cx-40, cy-40, cx+40, cy+40], fill=ac2)
    kw = (scene.title or "X").split()[0][:2].upper()
    draw.text((cx, cy), kw, font=_font(32, bold=True), fill=(10, 18, 35), anchor="mm")
    for i, ang in enumerate([0, 60, 120]):
        rad = math.radians(ang)
        rx, ry = 180, 70
        pts = []
        for deg in range(0, 361, 5):
            a = math.radians(deg)
            x = rx * math.cos(a)
            y = ry * math.sin(a)
            pts.append((cx + x*math.cos(rad) - y*math.sin(rad),
                        cy + x*math.sin(rad) + y*math.cos(rad)))
        col = [ac, pu, gr][i]
        for j in range(len(pts) - 1):
            draw.line([pts[j], pts[j+1]], fill=col, width=2)
        ex = cx + rx * math.cos(rad) * 0.9
        ey = cy + rx * math.sin(rad) * 0.4
        draw.ellipse([ex-10, ey-10, ex+10, ey+10], fill=col)
    draw.text((cx, H-28), "Atomic Structure", font=_font(22),
              fill=T.get("muted", (148, 163, 184)), anchor="mm")


def _draw_money(draw, scene, T):
    ac  = T.get("accent",  (56, 189, 248))
    ac2 = T.get("accent2", (251, 191, 36))
    gr  = T.get("green",   (74, 222, 128))
    mu  = T.get("muted",   (148, 163, 184))
    pairs = _extract_numbers(scene.bullets) if scene.bullets else []
    if not pairs:
        pairs = [("Before", 35), ("After", 72), ("Target", 90), ("Current", 58)]
    bcolors = [ac, ac2, gr, T.get("purple", (167, 139, 250))]
    n = min(len(pairs), 5)
    cx0, cy0, cw, ch = 60, 40, W-120, H-120
    mv = max(v for _, v in pairs) or 1
    draw.line([(cx0, cy0), (cx0, cy0+ch)], fill=mu, width=2)
    draw.line([(cx0, cy0+ch), (cx0+cw, cy0+ch)], fill=mu, width=2)
    bw = (cw - 20) // n - 10
    for i, (lbl, val) in enumerate(pairs[:n]):
        bh  = int(ch * (val / mv) * 0.9)
        bx  = cx0 + 20 + i * (bw + 10)
        by  = cy0 + ch - bh
        col = bcolors[i % len(bcolors)]
        draw.rounded_rectangle([bx, by, bx+bw, cy0+ch], 6, fill=col)
        draw.text((bx+bw//2, by-10), str(int(val)), font=_font(24, bold=True),
                  fill=col, anchor="mb")
        draw.text((bx+bw//2, cy0+ch+14), lbl[:12], font=_font(20),
                  fill=mu, anchor="mt")
    draw.text((W//2, H-12), (scene.title or "Data")[:40],
              font=_font(20), fill=mu, anchor="mb")


def _draw_code(draw, scene, T):
    ac  = T.get("accent",  (56, 189, 248))
    ac2 = T.get("accent2", (251, 191, 36))
    txt = T.get("text",    (241, 245, 249))
    mu  = T.get("muted",   (148, 163, 184))
    steps = scene.bullets[:4] if scene.bullets else ["Input", "Process", "Decide", "Output"]
    n = len(steps)
    bw, bh = 180, 60
    total = n * bw + (n-1) * 50
    sx = (W - total) // 2
    cy = H // 2
    for i, step in enumerate(steps):
        bx = sx + i * (bw + 50)
        by = cy - bh // 2
        if i % 2 == 1:
            draw.polygon([(bx+bw//2, by), (bx+bw, cy), (bx+bw//2, by+bh), (bx, cy)],
                         fill=ac, outline=txt)
        else:
            draw.rounded_rectangle([bx, by, bx+bw, by+bh], 10, fill=ac, outline=txt, width=2)
        draw.text((bx+bw//2, cy), step[:16], font=_font(22), fill=(10, 18, 35), anchor="mm")
        if i < n - 1:
            ax = bx + bw + 2
            draw.line([(ax, cy), (ax+46, cy)], fill=ac2, width=3)
            draw.polygon([(ax+46, cy-8), (ax+50, cy), (ax+46, cy+8)], fill=ac2)
    draw.text((W//2, H-20), "Process Flow", font=_font(20), fill=mu, anchor="mm")


def _draw_globe(draw, scene, T):
    ac2  = T.get("accent2", (251, 191, 36))
    mu   = T.get("muted",   (148, 163, 184))
    txt  = T.get("text",    (241, 245, 249))
    dark = T.get("dark",    True)
    ocean = (20, 60, 120) if dark else (173, 216, 230)
    land  = (40, 100, 60) if dark else (144, 185, 100)
    draw.ellipse([40, 20, W-40, H-20], fill=ocean)
    for cx, cy, rx, ry, lbl, hl in [
        (W//2-180, H//2-30,  80, 100, "Americas",  False),
        (W//2-20,  H//2-60,  70,  80, "Europe",    False),
        (W//2+50,  H//2+10,  85, 110, "Africa",    True),
        (W//2+180, H//2-20,  90,  95, "Asia",      False),
    ]:
        draw.ellipse([cx-rx, cy-ry, cx+rx, cy+ry], fill=ac2 if hl else land)
        draw.text((cx, cy+ry+12), lbl, font=_font(16), fill=txt, anchor="mt")
    draw.text((W//2, H-14), "Global View", font=_font(20), fill=mu, anchor="mb")


def _draw_people(draw, scene, T):
    ac  = T.get("accent",  (56, 189, 248))
    ac2 = T.get("accent2", (251, 191, 36))
    gr  = T.get("green",   (74, 222, 128))
    mu  = T.get("muted",   (148, 163, 184))
    nodes   = scene.bullets[:4] if scene.bullets else ["Community", "Clinic", "School", "Family"]
    cx, cy  = W//2, H//2
    bcolors = [ac, ac2, gr, T.get("purple", (167, 139, 250))]
    draw.ellipse([cx-48, cy-48, cx+48, cy+48], fill=ac)
    draw.text((cx, cy), (scene.title or "Network")[:10],
              font=_font(22, bold=True), fill=(10, 18, 35), anchor="mm")
    for i, node in enumerate(nodes):
        angle = 2 * math.pi * i / len(nodes) - math.pi / 2
        nx = int(cx + 180 * math.cos(angle))
        ny = int(cy + 180 * math.sin(angle))
        col = bcolors[i % len(bcolors)]
        draw.line([(cx, cy), (nx, ny)], fill=mu, width=2)
        draw.ellipse([nx-36, ny-36, nx+36, ny+36], fill=col)
        draw.text((nx, ny), node[:10], font=_font(18), fill=(10, 18, 35), anchor="mm")


def _draw_idea(draw, scene, T):
    ac  = T.get("accent",  (56, 189, 248))
    ac2 = T.get("accent2", (251, 191, 36))
    gr  = T.get("green",   (74, 222, 128))
    pu  = T.get("purple",  (167, 139, 250))
    mu  = T.get("muted",   (148, 163, 184))
    concepts = scene.bullets[:5] if scene.bullets else ["Define", "Explore", "Connect", "Apply", "Reflect"]
    cx, cy   = W//2, H//2
    bcolors  = [ac, ac2, gr, pu, T.get("red", (248, 113, 113))]
    draw.ellipse([cx-55, cy-55, cx+55, cy+55], fill=ac2)
    draw.text((cx, cy), (scene.title or "Idea")[:8],
              font=_font(26, bold=True), fill=(10, 18, 35), anchor="mm")
    for i in range(8):
        a = math.pi * i / 4
        draw.line([(cx + 60*math.cos(a), cy + 60*math.sin(a)),
                   (cx + 85*math.cos(a), cy + 85*math.sin(a))], fill=ac2, width=2)
    for i, concept in enumerate(concepts):
        angle = 2 * math.pi * i / len(concepts) - math.pi / 2
        nx = int(cx + 170 * math.cos(angle))
        ny = int(cy + 170 * math.sin(angle))
        col = bcolors[i % len(bcolors)]
        draw.line([(cx, cy), (nx, ny)], fill=mu, width=2)
        bw2 = max(80, len(concept[:20]) * 10)
        draw.rounded_rectangle([nx-bw2//2, ny-20, nx+bw2//2, ny+20], 10, fill=col)
        draw.text((nx, ny), concept[:18], font=_font(18), fill=(10, 18, 35), anchor="mm")


def _draw_warning(draw, scene, T):
    ac  = T.get("accent",  (56, 189, 248))
    ac2 = T.get("accent2", (251, 191, 36))
    rd  = T.get("red",     (248, 113, 113))
    gr  = T.get("green",   (74, 222, 128))
    txt = T.get("text",    (241, 245, 249))
    mu  = T.get("muted",   (148, 163, 184))
    steps  = scene.bullets[:4] if scene.bullets else ["Root Cause", "Risk", "Effect", "Outcome"]
    colors = [rd, ac2, ac, gr]
    n = len(steps)
    bw, bh = 160, 72
    gap = 50
    total = n * bw + (n-1) * gap
    sx = (W - total) // 2
    cy = H // 2
    for i, step in enumerate(steps):
        bx = sx + i * (bw + gap)
        by = cy - bh // 2
        draw.rounded_rectangle([bx, by, bx+bw, by+bh], 12, fill=colors[i % len(colors)])
        draw.text((bx+bw//2, cy), step[:20], font=_font(20), fill=(10, 18, 35), anchor="mm")
        if i < n - 1:
            ax = bx + bw + 2
            draw.line([(ax, cy), (ax+gap-4, cy)], fill=txt, width=3)
            draw.polygon([(ax+gap-4, cy-8), (ax+gap, cy), (ax+gap-4, cy+8)], fill=txt)
    draw.text((W//2, H-20), "Cause to Effect", font=_font(20), fill=mu, anchor="mm")


def _draw_check(draw, scene, T):
    gr   = T.get("green",  (74, 222, 128))
    txt  = T.get("text",   (241, 245, 249))
    mu   = T.get("muted",  (148, 163, 184))
    card = T.get("card",   (20, 32, 55))
    items = scene.bullets[:5] if scene.bullets else [
        "Key action 1", "Key action 2", "Key action 3", "Key action 4"]
    rh = 72
    sy = (H - len(items) * rh) // 2
    for i, item in enumerate(items):
        y    = sy + i * rh
        done = i < max(1, len(items) // 2)
        draw.rounded_rectangle([40, y, W-40, y+rh-6], 8, fill=card)
        draw.rounded_rectangle([52, y+10, 92, y+rh-16], 6, fill=gr if done else mu)
        draw.text((72, y+rh//2-3), "v" if done else ".", font=_font(30, bold=True),
                  fill=(10, 18, 35) if done else txt, anchor="mm")
        draw.text((106, y+rh//2-3), item[:45], font=_font(26), fill=txt, anchor="lm")
        if done:
            draw.rectangle([40, y+rh-7, W-40, y+rh-4], fill=gr)


def _draw_book(draw, scene, T):
    ac  = T.get("accent",  (56, 189, 248))
    ac2 = T.get("accent2", (251, 191, 36))
    gr  = T.get("green",   (74, 222, 128))
    pu  = T.get("purple",  (167, 139, 250))
    txt = T.get("text",    (241, 245, 249))
    mu  = T.get("muted",   (148, 163, 184))
    ms  = scene.bullets[:5] if scene.bullets else ["Start", "Learn", "Practice", "Master"]
    n   = len(ms)
    colors = [ac, ac2, gr, pu, T.get("red", (248, 113, 113))]
    ty = H // 2
    tx0, tx1 = 60, W - 60
    draw.line([(tx0, ty), (tx1, ty)], fill=mu, width=4)
    for i, m in enumerate(ms):
        x   = tx0 + int((tx1 - tx0) * i / (n-1)) if n > 1 else W//2
        col = colors[i % len(colors)]
        draw.ellipse([x-18, ty-18, x+18, ty+18], fill=col)
        draw.text((x, ty), str(i+1), font=_font(22, bold=True), fill=(10, 18, 35), anchor="mm")
        label_y = ty - 50 if i % 2 == 0 else ty + 42
        for ln in _wrap(draw, m[:25], _font(20), 140)[:2]:
            draw.text((x, label_y), ln, font=_font(20), fill=txt, anchor="mm")
            label_y += 24


DRAWERS = {
    "health":  _draw_health,
    "science": _draw_science,
    "money":   _draw_money,
    "code":    _draw_code,
    "globe":   _draw_globe,
    "people":  _draw_people,
    "idea":    _draw_idea,
    "warning": _draw_warning,
    "check":   _draw_check,
    "book":    _draw_book,
}


def make_graphic(scene, theme_dict, size=(860, 500)):
    """Return a Pillow Image with the topic-appropriate diagram."""
    img  = Image.new("RGB", size, theme_dict.get("card", (20, 32, 55)))
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, size[0], size[1]], fill=theme_dict.get("card", (20, 32, 55)))
    fn = DRAWERS.get(scene.icon, _draw_book)
    try:
        fn(draw, scene, theme_dict)
    except Exception:
        draw.text((size[0]//2, size[1]//2), (scene.title or "")[:40],
                  font=_font(32), fill=theme_dict.get("text", (241, 245, 249)), anchor="mm")
    return img
