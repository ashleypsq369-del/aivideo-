"""Rich visual asset generator for all 14 visual types from the guide.

Each function returns a Pillow Image (860x540) for the right-panel
of a 1920x1080 slide (no overlap with the text on the left).

Visual types:
  process_flow, cycle, comparison, chart_bar, chart_line,
  timeline, concept_map, analogy_split, statement,
  checklist, cause_effect, tree, annotated_body, atom_orbital
"""
import math
import os
import re

from PIL import Image, ImageDraw, ImageFont

W, H = 860, 540
FONT_DIRS = [
    "C:/Windows/Fonts",
    "/usr/share/fonts/truetype/dejavu",
    "/usr/share/fonts/dejavu",
    "/Library/Fonts",
]


# ── font / draw helpers ───────────────────────────────────────────────────────

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
    draw.rectangle([0, 0, W, H], fill=T.get("card", (20, 32, 55)))


def _arrow_h(draw, x, cy, length, color, head=12):
    if length < head + 2:
        return
    draw.line([(x, cy), (x + length - head, cy)], fill=color, width=3)
    draw.polygon([
        (x + length - head, cy - head // 2),
        (x + length, cy),
        (x + length - head, cy + head // 2),
    ], fill=color)


def _arrow_v(draw, cx, y, length, color, head=10):
    if length < head + 2:
        return
    draw.line([(cx, y), (cx, y + length - head)], fill=color, width=3)
    draw.polygon([
        (cx - head // 2, y + length - head),
        (cx, y + length),
        (cx + head // 2, y + length - head),
    ], fill=color)


# ── process_flow ─────────────────────────────────────────────────────────────

def process_flow(steps, T):
    img = Image.new("RGB", (W, H), T.get("card", (20, 32, 55)))
    d = ImageDraw.Draw(img)
    _bg(d, T)
    ac = T.get("accent", (56, 189, 248))
    ac2 = T.get("accent2", (251, 191, 36))
    gr = T.get("green", (74, 222, 128))
    pu = T.get("purple", (167, 139, 250))
    rd = T.get("red", (248, 113, 113))
    txt = T.get("text", (241, 245, 249))
    mu = T.get("muted", (148, 163, 184))
    colors = [ac, ac2, gr, pu, rd]

    n = min(len(steps), 5)
    if n == 0:
        return img

    bw = min(150, (W - 60) // n - 14)
    bh = 70
    total_w = n * bw + (n - 1) * 14
    sx = (W - total_w) // 2
    cy = H // 2
    f = _font(19)

    for i, step in enumerate(steps[:n]):
        bx = sx + i * (bw + 14)
        col = colors[i % len(colors)]
        # shadow
        d.rounded_rectangle([bx + 3, cy - bh // 2 + 3, bx + bw + 3, cy + bh // 2 + 3],
                             10, fill=tuple(c // 4 for c in col))
        d.rounded_rectangle([bx, cy - bh // 2, bx + bw, cy + bh // 2], 10, fill=col)
        # number badge
        d.ellipse([bx + 5, cy - bh // 2 + 5, bx + 23, cy - bh // 2 + 23],
                  fill=tuple(max(0, c - 70) for c in col))
        d.text((bx + 14, cy - bh // 2 + 14), str(i + 1),
               font=_font(13, bold=True), fill=txt, anchor="mm")
        # label
        lns = _wrap(d, step[:28], f, bw - 10)
        ly = cy - len(lns) * 11
        for ln in lns[:3]:
            d.text((bx + bw // 2, ly), ln, font=f, fill=(10, 18, 35), anchor="mt")
            ly += 22
        # arrow
        if i < n - 1:
            _arrow_h(d, bx + bw + 2, cy, 12, ac2)

    d.text((W // 2, H - 20), "Process Flow", font=_font(17), fill=mu, anchor="mm")
    return img


# ── cycle ─────────────────────────────────────────────────────────────────────

def cycle(steps, T):
    img = Image.new("RGB", (W, H), T.get("card", (20, 32, 55)))
    d = ImageDraw.Draw(img)
    _bg(d, T)
    ac = T.get("accent", (56, 189, 248))
    ac2 = T.get("accent2", (251, 191, 36))
    gr = T.get("green", (74, 222, 128))
    pu = T.get("purple", (167, 139, 250))
    rd = T.get("red", (248, 113, 113))
    txt = T.get("text", (241, 245, 249))
    mu = T.get("muted", (148, 163, 184))
    colors = [ac, ac2, gr, pu, rd]

    n = min(len(steps), 6)
    if n == 0:
        return img

    cx, cy = W // 2, H // 2
    r = min(W, H) // 2 - 68
    nr = 34

    # dashed ring
    for deg in range(0, 360, 8):
        a = math.radians(deg)
        d.ellipse([cx + r * math.cos(a) - 2, cy + r * math.sin(a) - 2,
                   cx + r * math.cos(a) + 2, cy + r * math.sin(a) + 2], fill=mu)

    f = _font(17)
    for i, step in enumerate(steps[:n]):
        angle = 2 * math.pi * i / n - math.pi / 2
        nx = int(cx + r * math.cos(angle))
        ny = int(cy + r * math.sin(angle))
        col = colors[i % len(colors)]

        # arc to next
        next_angle = 2 * math.pi * ((i + 1) % n) / n - math.pi / 2
        for t in range(10):
            a1 = angle + (next_angle - angle) * t / 10
            a2 = angle + (next_angle - angle) * (t + 1) / 10
            x1 = cx + (r + 10) * math.cos(a1)
            y1 = cy + (r + 10) * math.sin(a1)
            x2 = cx + (r + 10) * math.cos(a2)
            y2 = cy + (r + 10) * math.sin(a2)
            d.line([(x1, y1), (x2, y2)], fill=col, width=2)

        # node
        d.ellipse([nx - nr, ny - nr, nx + nr, ny + nr], fill=col)
        d.text((nx, ny), str(i + 1), font=_font(20, bold=True),
               fill=(10, 18, 35), anchor="mm")

        # label outside
        lx = int(cx + (r + nr + 26) * math.cos(angle))
        ly = int(cy + (r + nr + 26) * math.sin(angle))
        lns = _wrap(d, step[:20], f, 120)
        d.text((lx, ly), lns[0] if lns else step[:20], font=f, fill=txt, anchor="mm")

    d.text((W // 2, H - 20), "Cycle", font=_font(17), fill=mu, anchor="mm")
    return img


# ── comparison ───────────────────────────────────────────────────────────────

def comparison(left_label, right_label, left_items, right_items, T):
    img = Image.new("RGB", (W, H), T.get("card", (20, 32, 55)))
    d = ImageDraw.Draw(img)
    _bg(d, T)
    ac = T.get("accent", (56, 189, 248))
    ac2 = T.get("accent2", (251, 191, 36))
    gr = T.get("green", (74, 222, 128))
    txt = T.get("text", (241, 245, 249))
    mu = T.get("muted", (148, 163, 184))
    card = T.get("card", (20, 32, 55))

    mid = W // 2
    # headers
    d.rounded_rectangle([10, 8, mid - 8, 52], 8, fill=ac)
    d.rounded_rectangle([mid + 8, 8, W - 10, 52], 8, fill=ac2)
    d.text((mid // 2 + 5, 30), left_label[:22],
           font=_font(20, bold=True), fill=(10, 18, 35), anchor="mm")
    d.text((mid + (W - mid) // 2, 30), right_label[:22],
           font=_font(20, bold=True), fill=(10, 18, 35), anchor="mm")

    # divider
    d.line([(mid, 56), (mid, H - 28)], fill=mu, width=1)

    n = max(len(left_items), len(right_items))
    rh = min(72, (H - 80) // max(n, 1))
    f = _font(18)
    for i in range(min(n, 7)):
        y = 60 + i * rh
        alt = tuple(min(255, c + 10) for c in card) if i % 2 else card
        d.rectangle([10, y, mid - 8, y + rh - 4], fill=alt)
        d.rectangle([mid + 8, y, W - 10, y + rh - 4], fill=alt)
        if i < len(left_items):
            lns = _wrap(d, left_items[i][:38], f, mid - 28)
            d.text((22, y + rh // 2 - 10), lns[0] if lns else "", font=f, fill=gr)
        if i < len(right_items):
            rns = _wrap(d, right_items[i][:38], f, mid - 28)
            d.text((mid + 16, y + rh // 2 - 10), rns[0] if rns else "", font=f, fill=ac2)

    return img


# ── chart_bar ─────────────────────────────────────────────────────────────────

def chart_bar(labels, values, title, T):
    img = Image.new("RGB", (W, H), T.get("card", (20, 32, 55)))
    d = ImageDraw.Draw(img)
    _bg(d, T)
    ac = T.get("accent", (56, 189, 248))
    ac2 = T.get("accent2", (251, 191, 36))
    gr = T.get("green", (74, 222, 128))
    pu = T.get("purple", (167, 139, 250))
    rd = T.get("red", (248, 113, 113))
    mu = T.get("muted", (148, 163, 184))
    txt = T.get("text", (241, 245, 249))
    colors = [ac, ac2, gr, pu, rd]

    if not values:
        return img

    n = min(len(values), 8)
    mx = max(abs(v) for v in values) or 1
    cx0, cy0, cw, ch = 52, 28, W - 76, H - 90

    d.line([(cx0, cy0), (cx0, cy0 + ch)], fill=mu, width=2)
    d.line([(cx0, cy0 + ch), (cx0 + cw, cy0 + ch)], fill=mu, width=2)

    # grid lines
    for g in range(1, 5):
        gy = cy0 + ch - int(ch * g / 4)
        d.line([(cx0, gy), (cx0 + cw, gy)],
               fill=tuple(c // 2 for c in mu), width=1)
        d.text((cx0 - 4, gy), str(int(mx * g / 4)),
               font=_font(13), fill=mu, anchor="rm")

    bw = max(18, (cw - 20) // n - 8)
    bsp = (cw - n * bw) // (n + 1)
    f = _font(15)
    for i, (lbl, val) in enumerate(zip(labels[:n], values[:n])):
        bh = int(ch * abs(val) / mx * 0.94)
        bx = cx0 + bsp + i * (bw + bsp)
        by = cy0 + ch - bh
        col = colors[i % len(colors)]
        d.rounded_rectangle([bx - 2, by + 2, bx + bw + 2, cy0 + ch], 4,
                             fill=tuple(c // 4 for c in col))
        d.rounded_rectangle([bx, by, bx + bw, cy0 + ch], 4, fill=col)
        d.text((bx + bw // 2, by - 5), str(int(val)),
               font=_font(15, bold=True), fill=col, anchor="mb")
        lns = _wrap(d, lbl[:13], f, bw + 8)
        d.text((bx + bw // 2, cy0 + ch + 8),
               lns[0] if lns else lbl[:10], font=f, fill=mu, anchor="mt")

    d.text((cx0 + cw // 2, H - 16), title[:40],
           font=_font(17, bold=True), fill=txt, anchor="mm")
    return img


# ── chart_line ────────────────────────────────────────────────────────────────

def chart_line(labels, values, title, T):
    img = Image.new("RGB", (W, H), T.get("card", (20, 32, 55)))
    d = ImageDraw.Draw(img)
    _bg(d, T)
    ac = T.get("accent", (56, 189, 248))
    ac2 = T.get("accent2", (251, 191, 36))
    mu = T.get("muted", (148, 163, 184))
    txt = T.get("text", (241, 245, 249))

    if not values:
        return img

    n = len(values)
    mx = max(values) or 1
    mn = min(values)
    cx0, cy0, cw, ch = 52, 28, W - 76, H - 90

    d.line([(cx0, cy0), (cx0, cy0 + ch)], fill=mu, width=2)
    d.line([(cx0, cy0 + ch), (cx0 + cw, cy0 + ch)], fill=mu, width=2)

    pts = []
    for i, v in enumerate(values):
        x = cx0 + int(cw * i / max(n - 1, 1))
        y = cy0 + ch - int(ch * (v - mn) / max(mx - mn, 1) * 0.92)
        pts.append((x, y))

    # fill area
    poly = [(cx0, cy0 + ch)] + pts + [(pts[-1][0], cy0 + ch)]
    d.polygon(poly, fill=tuple(int(c * 0.22) for c in ac))

    # line
    for i in range(len(pts) - 1):
        d.line([pts[i], pts[i + 1]], fill=ac, width=3)

    # dots + labels
    f = _font(14)
    for i, (p, lbl) in enumerate(zip(pts, labels)):
        d.ellipse([p[0] - 6, p[1] - 6, p[0] + 6, p[1] + 6], fill=ac2)
        d.text((p[0], cy0 + ch + 8), lbl[:8], font=f, fill=mu, anchor="mt")

    d.text((cx0 + cw // 2, H - 16), title[:40],
           font=_font(17, bold=True), fill=txt, anchor="mm")
    return img


# ── timeline ──────────────────────────────────────────────────────────────────

def timeline(events, T):
    """events: list of {"label": str, "date": str, "detail": str}"""
    img = Image.new("RGB", (W, H), T.get("card", (20, 32, 55)))
    d = ImageDraw.Draw(img)
    _bg(d, T)
    ac = T.get("accent", (56, 189, 248))
    ac2 = T.get("accent2", (251, 191, 36))
    gr = T.get("green", (74, 222, 128))
    pu = T.get("purple", (167, 139, 250))
    rd = T.get("red", (248, 113, 113))
    txt = T.get("text", (241, 245, 249))
    mu = T.get("muted", (148, 163, 184))
    colors = [ac, ac2, gr, pu, rd]

    n = min(len(events), 6)
    if n == 0:
        return img

    ty = H // 2
    tx0, tx1 = 48, W - 48
    # spine gradient
    for x in range(tx0, tx1):
        t = (x - tx0) / (tx1 - tx0)
        col = tuple(int(ac[i] * t + mu[i] * (1 - t)) for i in range(3))
        d.line([(x, ty), (x, ty + 1)], fill=col)
    d.line([(tx0, ty), (tx1, ty)], fill=mu, width=4)

    f_date = _font(17, bold=True)
    f_lbl = _font(16)
    f_det = _font(13)

    for i, ev in enumerate(events[:n]):
        x = tx0 + int((tx1 - tx0) * i / max(n - 1, 1))
        col = colors[i % len(colors)]

        # spine dot with glow
        for extra in [12, 8, 4]:
            d.ellipse([x - extra, ty - extra, x + extra, ty + extra],
                      fill=tuple(int(c * 0.15) for c in col))
        d.ellipse([x - 14, ty - 14, x + 14, ty + 14], fill=col)
        d.text((x, ty), str(i + 1), font=_font(15, bold=True),
               fill=(10, 18, 35), anchor="mm")

        above = i % 2 == 0
        sign = -1 if above else 1

        d.line([(x, ty + sign * 14), (x, ty + sign * 52)], fill=col, width=2)

        dy = ty + sign * 65
        d.text((x, dy), ev.get("date", "")[:12], font=f_date, fill=col, anchor="mm")

        ly = dy + sign * 22
        lns = _wrap(d, ev.get("label", "")[:28], f_lbl, 155)
        for ln in lns[:2]:
            d.text((x, ly), ln, font=f_lbl, fill=txt, anchor="mm")
            ly += sign * 20

        det = ev.get("detail", "")[:30]
        if det:
            d.text((x, ly + sign * 4), det, font=f_det, fill=mu, anchor="mm")

    d.text((W // 2, H - 20), "Timeline", font=_font(17), fill=mu, anchor="mm")
    return img


# ── concept_map ───────────────────────────────────────────────────────────────

def concept_map(center, concepts, T):
    img = Image.new("RGB", (W, H), T.get("card", (20, 32, 55)))
    d = ImageDraw.Draw(img)
    _bg(d, T)
    ac = T.get("accent", (56, 189, 248))
    ac2 = T.get("accent2", (251, 191, 36))
    gr = T.get("green", (74, 222, 128))
    pu = T.get("purple", (167, 139, 250))
    rd = T.get("red", (248, 113, 113))
    txt = T.get("text", (241, 245, 249))
    mu = T.get("muted", (148, 163, 184))
    colors = [ac, ac2, gr, pu, rd]

    cx, cy = W // 2, H // 2
    r = min(W, H) // 2 - 76

    # subtle background rings
    for rr in [r // 3, 2 * r // 3, r]:
        for deg in range(0, 360, 12):
            a = math.radians(deg)
            d.point((int(cx + rr * math.cos(a)), int(cy + rr * math.sin(a))),
                    fill=tuple(c // 4 for c in mu))

    # center hub
    hub_r = 46
    for extra in range(22, 0, -6):
        d.ellipse([cx - hub_r - extra, cy - hub_r - extra,
                   cx + hub_r + extra, cy + hub_r + extra],
                  fill=tuple(int(c * 0.07) for c in ac))
    d.ellipse([cx - hub_r, cy - hub_r, cx + hub_r, cy + hub_r], fill=ac)
    lns = _wrap(d, center[:18], _font(19, bold=True), hub_r * 1.75)
    ly0 = cy - len(lns) * 11
    for ln in lns[:3]:
        d.text((cx, ly0), ln, font=_font(19, bold=True), fill=(10, 18, 35), anchor="mm")
        ly0 += 22

    n = min(len(concepts), 7)
    nr = 34
    f = _font(16)
    for i, concept in enumerate(concepts[:n]):
        angle = 2 * math.pi * i / n - math.pi / 2
        nx = int(cx + r * math.cos(angle))
        ny = int(cy + r * math.sin(angle))
        col = colors[i % len(colors)]

        # curved bezier spoke
        mx_ = int(cx + r * 0.5 * math.cos(angle))
        my_ = int(cy + r * 0.5 * math.sin(angle))
        pts = []
        for t in range(21):
            tt = t / 20
            px = int((1 - tt) ** 2 * cx + 2 * (1 - tt) * tt * mx_ + tt ** 2 * nx)
            py = int((1 - tt) ** 2 * cy + 2 * (1 - tt) * tt * my_ + tt ** 2 * ny)
            pts.append((px, py))
        for j in range(len(pts) - 1):
            d.line([pts[j], pts[j + 1]], fill=col, width=2)

        # node
        d.ellipse([nx - nr, ny - nr, nx + nr, ny + nr], fill=col)
        lns2 = _wrap(d, concept[:16], f, nr * 1.85)
        ly2 = ny - len(lns2) * 8
        for ln in lns2[:2]:
            d.text((nx, ly2), ln, font=f, fill=(10, 18, 35), anchor="mm")
            ly2 += 17

    d.text((W // 2, H - 20), "Concept Map", font=_font(17), fill=mu, anchor="mm")
    return img


# ── analogy_split ─────────────────────────────────────────────────────────────

def analogy_split(familiar_label, familiar_items, target_label, target_items, T):
    img = Image.new("RGB", (W, H), T.get("card", (20, 32, 55)))
    d = ImageDraw.Draw(img)
    _bg(d, T)
    ac = T.get("accent", (56, 189, 248))
    ac2 = T.get("accent2", (251, 191, 36))
    gr = T.get("green", (74, 222, 128))
    txt = T.get("text", (241, 245, 249))
    mu = T.get("muted", (148, 163, 184))
    card = T.get("card", (20, 32, 55))

    mid = W // 2
    dark_card = tuple(min(255, int(c * 1.5)) for c in card)

    # panels
    d.rounded_rectangle([8, 8, mid - 8, H - 8], 12, fill=dark_card)
    d.rounded_rectangle([mid + 8, 8, W - 8, H - 8], 12, fill=dark_card)
    # headers
    d.rounded_rectangle([8, 8, mid - 8, 50], 10, fill=ac2)
    d.rounded_rectangle([mid + 8, 8, W - 8, 50], 10, fill=ac)
    d.text((mid // 2 + 4, 29), familiar_label[:20],
           font=_font(19, bold=True), fill=(10, 18, 35), anchor="mm")
    d.text((mid + (W - mid) // 2, 29), target_label[:20],
           font=_font(19, bold=True), fill=(10, 18, 35), anchor="mm")

    f = _font(17)
    y = 58
    for item in familiar_items[:5]:
        lns = _wrap(d, item[:36], f, mid - 30)
        d.text((20, y), ("• " + (lns[0] if lns else item[:30])), font=f, fill=txt)
        y += 28
        y += 5

    y = 58
    for item in target_items[:5]:
        lns = _wrap(d, item[:36], f, mid - 30)
        d.text((mid + 16, y), ("• " + (lns[0] if lns else item[:30])), font=f, fill=txt)
        y += 28
        y += 5

    # mapping arrows in the middle
    n_map = min(len(familiar_items), len(target_items), 4)
    if n_map:
        rh = (H - 70) // n_map
        mapping_colors = [ac, ac2, gr, T.get("purple", (167, 139, 250))]
        for i in range(n_map):
            ay = 72 + i * rh + rh // 2
            col = mapping_colors[i % len(mapping_colors)]
            d.line([(mid - 8, ay), (mid + 8, ay)], fill=col, width=2)
            d.polygon([(mid + 4, ay - 5), (mid + 10, ay), (mid + 4, ay + 5)], fill=col)

    return img


# ── statement ─────────────────────────────────────────────────────────────────

def statement(text_str, source, T):
    img = Image.new("RGB", (W, H), T.get("card", (20, 32, 55)))
    d = ImageDraw.Draw(img)
    _bg(d, T)
    ac = T.get("accent", (56, 189, 248))
    ac2 = T.get("accent2", (251, 191, 36))
    txt = T.get("text", (241, 245, 249))
    mu = T.get("muted", (148, 163, 184))

    # decorative quote mark (large, faded)
    d.text((60, 70), "\u201c", font=_font(110, bold=True),
           fill=tuple(int(c * 0.18) for c in ac), anchor="mm")

    f = _font(30, bold=True)
    lns = _wrap(d, text_str[:200], f, W - 80)
    total_h = len(lns[:5]) * 42
    y = H // 2 - total_h // 2
    for ln in lns[:5]:
        d.text((W // 2, y), ln, font=f, fill=txt, anchor="mt")
        y += 42

    # accent line
    d.rectangle([W // 2 - 90, y + 10, W // 2 + 90, y + 14], fill=ac2)

    if source:
        d.text((W // 2, y + 26), "— " + source[:55],
               font=_font(16), fill=mu, anchor="mt")
    return img


# ── checklist ─────────────────────────────────────────────────────────────────

def checklist(items, checked, T):
    img = Image.new("RGB", (W, H), T.get("card", (20, 32, 55)))
    d = ImageDraw.Draw(img)
    _bg(d, T)
    gr = T.get("green", (74, 222, 128))
    ac = T.get("accent", (56, 189, 248))
    txt = T.get("text", (241, 245, 249))
    mu = T.get("muted", (148, 163, 184))
    card = T.get("card", (20, 32, 55))

    n = min(len(items), 6)
    rh = min(76, (H - 36) // max(n, 1))
    f = _font(22)

    for i, (item, done) in enumerate(zip(items[:n], checked[:n])):
        y = 18 + i * rh
        alt = tuple(min(255, c + 12) for c in card) if i % 2 else card
        d.rounded_rectangle([16, y, W - 16, y + rh - 5], 8, fill=alt)

        col = gr if done else mu
        d.rounded_rectangle([26, y + 10, 62, y + rh - 15], 6, fill=col)
        if done:
            d.line([(32, y + rh // 2), (42, y + rh - 19)], fill=(10, 18, 35), width=3)
            d.line([(42, y + rh - 19), (58, y + 13)], fill=(10, 18, 35), width=3)
        else:
            d.text((44, y + rh // 2 - 2), "·", font=_font(26), fill=txt, anchor="mm")

        lns = _wrap(d, item[:52], f, W - 100)
        d.text((76, y + rh // 2 - 11), lns[0] if lns else item[:40], font=f, fill=txt)

        if done:
            d.rectangle([16, y + rh - 7, W - 16, y + rh - 4], fill=gr)

    return img


# ── cause_effect ──────────────────────────────────────────────────────────────

def cause_effect(steps, T):
    img = Image.new("RGB", (W, H), T.get("card", (20, 32, 55)))
    d = ImageDraw.Draw(img)
    _bg(d, T)
    rd = T.get("red", (248, 113, 113))
    ac2 = T.get("accent2", (251, 191, 36))
    ac = T.get("accent", (56, 189, 248))
    gr = T.get("green", (74, 222, 128))
    txt = T.get("text", (241, 245, 249))
    mu = T.get("muted", (148, 163, 184))
    colors = [rd, ac2, ac, gr]

    n = min(len(steps), 4)
    if n == 0:
        return img

    bw = min(165, (W - 40) // n - 14)
    bh = 78
    total_w = n * bw + (n - 1) * 14
    sx = (W - total_w) // 2
    cy = H // 2
    f = _font(20)

    for i, step in enumerate(steps[:n]):
        bx = sx + i * (bw + 14)
        col = colors[i % len(colors)]
        d.rounded_rectangle([bx + 4, cy - bh // 2 + 4, bx + bw + 4, cy + bh // 2 + 4],
                             12, fill=tuple(c // 4 for c in col))
        d.rounded_rectangle([bx, cy - bh // 2, bx + bw, cy + bh // 2], 12, fill=col)
        lns = _wrap(d, step[:28], f, bw - 12)
        ly = cy - len(lns) * 12
        for ln in lns[:3]:
            d.text((bx + bw // 2, ly), ln, font=f, fill=(10, 18, 35), anchor="mt")
            ly += 24
        if i < n - 1:
            _arrow_h(d, bx + bw + 2, cy, 12, txt)

    stage_labels = ["Cause", "Factor", "Effect", "Outcome"]
    for i in range(n):
        bx = sx + i * (bw + 14)
        d.text((bx + bw // 2, cy + bh // 2 + 10), stage_labels[i],
               font=_font(16), fill=mu, anchor="mt")

    d.text((W // 2, H - 20), "Cause → Effect", font=_font(17), fill=mu, anchor="mm")
    return img


# ── tree ──────────────────────────────────────────────────────────────────────

def tree(root, branches, leaves, T):
    """leaves: dict {branch: [leaf1, leaf2]}"""
    img = Image.new("RGB", (W, H), T.get("card", (20, 32, 55)))
    d = ImageDraw.Draw(img)
    _bg(d, T)
    ac = T.get("accent", (56, 189, 248))
    ac2 = T.get("accent2", (251, 191, 36))
    gr = T.get("green", (74, 222, 128))
    pu = T.get("purple", (167, 139, 250))
    txt = T.get("text", (241, 245, 249))
    mu = T.get("muted", (148, 163, 184))
    colors = [ac, ac2, gr, pu]

    rx, ry = W // 2, 44
    d.rounded_rectangle([rx - 68, ry - 18, rx + 68, ry + 18], 8, fill=ac)
    d.text((rx, ry), root[:18], font=_font(19, bold=True), fill=(10, 18, 35), anchor="mm")

    n = min(len(branches), 4)
    bw = max(100, (W - 40) // max(n, 1) - 10)
    bh = 42

    for i, branch in enumerate(branches[:n]):
        col = colors[i % len(colors)]
        bx = 24 + i * (bw + (W - 48 - n * bw) // max(n - 1, 1))
        by = 148

        d.line([(rx, ry + 18), (bx + bw // 2, by - 2)], fill=col, width=2)
        d.rounded_rectangle([bx, by, bx + bw, by + bh], 7, fill=col)
        d.text((bx + bw // 2, by + bh // 2), branch[:15],
               font=_font(17, bold=True), fill=(10, 18, 35), anchor="mm")

        lf = _font(14)
        for j, leaf in enumerate(leaves.get(branch, [])[:3]):
            ly2 = by + bh + 18 + j * 34
            lx2 = bx + bw // 2
            d.line([(lx2, by + bh), (lx2, ly2 - 2)], fill=mu, width=1)
            d.rounded_rectangle([lx2 - 46, ly2, lx2 + 46, ly2 + 26], 6,
                                 fill=tuple(int(c * 0.55) for c in col))
            d.text((lx2, ly2 + 13), leaf[:16], font=lf, fill=txt, anchor="mm")

    d.text((W // 2, H - 20), "Hierarchy", font=_font(17), fill=mu, anchor="mm")
    return img


# ── annotated_body ────────────────────────────────────────────────────────────

def annotated_body(labels, T):
    """labels: [{"name": str, "region": str}]"""
    img = Image.new("RGB", (W, H), T.get("card", (20, 32, 55)))
    d = ImageDraw.Draw(img)
    _bg(d, T)
    ac = T.get("accent", (56, 189, 248))
    ac2 = T.get("accent2", (251, 191, 36))
    gr = T.get("green", (74, 222, 128))
    rd = T.get("red", (248, 113, 113))
    pu = T.get("purple", (167, 139, 250))
    txt = T.get("text", (241, 245, 249))
    mu = T.get("muted", (148, 163, 184))

    cx = W // 2
    # body outline
    d.ellipse([cx - 42, 28, cx + 42, 112], outline=ac, width=3)
    d.line([(cx - 16, 112), (cx - 16, 142)], fill=ac, width=3)
    d.line([(cx + 16, 112), (cx + 16, 142)], fill=ac, width=3)
    d.rounded_rectangle([cx - 65, 142, cx + 65, 320], 14, outline=ac, width=3)
    d.line([(cx - 65, 160), (cx - 118, 272)], fill=ac, width=3)
    d.line([(cx + 65, 160), (cx + 118, 272)], fill=ac, width=3)
    d.ellipse([cx - 130, 268, cx - 106, 294], outline=ac, width=2)
    d.ellipse([cx + 106, 268, cx + 130, 294], outline=ac, width=2)
    d.line([(cx - 32, 320), (cx - 40, 460)], fill=ac, width=3)
    d.line([(cx + 32, 320), (cx + 40, 460)], fill=ac, width=3)
    d.line([(cx - 40, 460), (cx - 68, 470)], fill=ac, width=3)
    d.line([(cx + 40, 460), (cx + 68, 470)], fill=ac, width=3)

    anchors = {
        "brain":   (cx, 68),
        "head":    (cx, 68),
        "heart":   (cx - 22, 192),
        "lungs":   (cx + 18, 178),
        "chest":   (cx, 215),
        "abdomen": (cx, 285),
        "gut":     (cx, 290),
        "arm":     (cx - 100, 225),
        "leg":     (cx - 38, 400),
    }
    colors = [ac2, gr, rd, pu, ac]

    for i, lbl in enumerate(labels[:6]):
        name = lbl.get("name", "")
        reg = lbl.get("region", "chest").lower()
        ax, ay = anchors.get(reg, (cx - 65 - 70 * (i // 3), 180 + 36 * (i % 3)))
        col = colors[i % len(colors)]
        d.ellipse([ax - 9, ay - 9, ax + 9, ay + 9], fill=col)
        lx = 28 if ax >= cx else W - 28
        d.line([(ax, ay), (lx, ay)], fill=mu, width=1)
        bw = 96
        x0 = lx - bw // 2
        d.rounded_rectangle([x0, ay - 13, x0 + bw, ay + 13], 7,
                             fill=tuple(int(c * 0.28) for c in col), outline=col, width=1)
        d.text((x0 + bw // 2, ay), name[:13], font=_font(16), fill=txt, anchor="mm")

    d.text((W // 2, H - 20), "Body Diagram", font=_font(17), fill=mu, anchor="mm")
    return img


# ── atom_orbital ──────────────────────────────────────────────────────────────

def atom_orbital(element, T):
    img = Image.new("RGB", (W, H), T.get("card", (20, 32, 55)))
    d = ImageDraw.Draw(img)
    _bg(d, T)
    ac = T.get("accent", (56, 189, 248))
    ac2 = T.get("accent2", (251, 191, 36))
    pu = T.get("purple", (167, 139, 250))
    gr = T.get("green", (74, 222, 128))
    mu = T.get("muted", (148, 163, 184))

    cx, cy = W // 2, H // 2
    # nucleus glow
    for extra in range(32, 0, -8):
        d.ellipse([cx - extra, cy - extra, cx + extra, cy + extra],
                  fill=tuple(int(c * 0.07) for c in ac2))
    d.ellipse([cx - 32, cy - 32, cx + 32, cy + 32], fill=ac2)
    d.text((cx, cy), element[:2].upper(),
           font=_font(28, bold=True), fill=(10, 18, 35), anchor="mm")

    orbit_colors = [ac, pu, gr]
    for i, ang_off in enumerate([0, 55, 115]):
        rad = math.radians(ang_off)
        rx_orb, ry_orb = int(W * 0.37), int(H * 0.27)
        pts = []
        for deg in range(0, 361, 4):
            a = math.radians(deg)
            x = rx_orb * math.cos(a)
            y = ry_orb * math.sin(a)
            pts.append((cx + x * math.cos(rad) - y * math.sin(rad),
                        cy + x * math.sin(rad) + y * math.cos(rad)))
        col = orbit_colors[i]
        for j in range(len(pts) - 1):
            d.line([pts[j], pts[j + 1]], fill=col, width=2)
        # electron dot
        ep_idx = len(pts) * 3 // 4
        ep = pts[ep_idx]
        d.ellipse([ep[0] - 10, ep[1] - 10, ep[0] + 10, ep[1] + 10], fill=col)

    d.text((cx, H - 28), f"{element} — Atomic Structure",
           font=_font(19, bold=True), fill=mu, anchor="mm")
    return img


# ── central dispatcher ────────────────────────────────────────────────────────

def make_visual(visual_type, spec, T):
    """Return a 860x540 Pillow Image for visual_type with spec params and theme T."""
    vt = visual_type.lower()
    try:
        if vt == "process_flow":
            return process_flow(spec.get("steps", []), T)
        if vt == "cycle":
            return cycle(spec.get("steps", []), T)
        if vt == "comparison":
            return comparison(
                spec.get("left_label", "A"), spec.get("right_label", "B"),
                spec.get("left_items", []), spec.get("right_items", []), T)
        if vt in ("chart_bar", "chart"):
            return chart_bar(spec.get("labels", []), spec.get("values", []),
                             spec.get("title", ""), T)
        if vt == "chart_line":
            return chart_line(spec.get("labels", []), spec.get("values", []),
                              spec.get("title", ""), T)
        if vt == "timeline":
            return timeline(spec.get("events", []), T)
        if vt == "concept_map":
            return concept_map(spec.get("center", ""), spec.get("concepts", []), T)
        if vt == "analogy_split":
            return analogy_split(
                spec.get("familiar_label", ""), spec.get("familiar_items", []),
                spec.get("target_label",   ""), spec.get("target_items",   []), T)
        if vt == "statement":
            return statement(spec.get("text", ""), spec.get("source", ""), T)
        if vt == "checklist":
            items = spec.get("items", [])
            checked = spec.get("checked", [True] * len(items))
            return checklist(items, checked, T)
        if vt == "cause_effect":
            return cause_effect(spec.get("steps", []), T)
        if vt == "tree":
            return tree(spec.get("root", ""), spec.get("branches", []),
                        spec.get("leaves", {}), T)
        if vt in ("annotated_diagram", "annotated_body"):
            return annotated_body(spec.get("labels", []), T)
        if vt == "atom_orbital":
            return atom_orbital(spec.get("element", "X"), T)
        # fallback
        return concept_map(spec.get("title", vt), spec.get("items", []), T)
    except Exception as e:
        img = Image.new("RGB", (W, H), T.get("card", (20, 32, 55)))
        d = ImageDraw.Draw(img)
        d.text((W // 2, H // 2), visual_type,
               font=_font(28, bold=True), fill=T.get("accent", (56, 189, 248)), anchor="mm")
        d.text((W // 2, H // 2 + 40), str(e)[:55],
               font=_font(14), fill=T.get("muted", (148, 163, 184)), anchor="mm")
        return img


# ── heuristic visual chooser ──────────────────────────────────────────────────

def choose_visual_spec(scene):
    """Return (visual_type, spec_dict) for a scene using content heuristics."""
    icon     = getattr(scene, "icon", "book")
    bullets  = getattr(scene, "bullets", [])
    title    = getattr(scene, "title", "")
    combined = (title + " " + " ".join(bullets)).lower()

    # Timeline / history
    if any(w in combined for w in ["year", "century", "history", "timeline",
                                    "evolution", "development", "age of"]):
        events = []
        for b in bullets[:5]:
            m = re.search(r"\b(\d{4}|\d+s)\b", b)
            events.append({"label": b[:28], "date": m.group(0) if m else "", "detail": ""})
        return "timeline", {"events": events}

    # Steps / process
    if any(w in combined for w in ["step", "process", "how to", "procedure",
                                    "workflow", "stage", "phase", "method"]):
        return "process_flow", {"steps": [b[:28] for b in bullets[:5]]}

    # Compare
    if any(w in combined for w in ["compare", "versus", "vs ", "difference",
                                    "similar", "contrast", "unlike", "both"]):
        half = len(bullets) // 2 or 1
        return "comparison", {
            "left_label": title[:18] + " A",
            "right_label": title[:18] + " B",
            "left_items":  [b[:34] for b in bullets[:half]],
            "right_items": [b[:34] for b in bullets[half:]],
        }

    # Cycle
    if any(w in combined for w in ["cycle", "loop", "lifecycle", "circular",
                                    "repeat", "revolv", "rotation"]):
        return "cycle", {"steps": [b[:24] for b in bullets[:6]]}

    # Numbers → bar chart
    nums, lbls = [], []
    for b in bullets[:6]:
        m = re.search(r"(\d+(?:\.\d+)?)\s*(%|million|billion|thousand)?", b)
        if m:
            nums.append(float(m.group(1)))
            lbls.append(b[:16])
    if len(nums) >= 2:
        return "chart_bar", {"labels": lbls, "values": nums, "title": title[:38]}

    # Icon-based routing
    if icon == "health":
        regions = []
        for b in bullets[:5]:
            bl = b.lower()
            if any(w in bl for w in ["brain", "head", "mental"]):  reg = "brain"
            elif any(w in bl for w in ["heart", "blood", "cardiac"]): reg = "heart"
            elif any(w in bl for w in ["lung", "breath", "respir"]):  reg = "lungs"
            elif any(w in bl for w in ["gut", "digest", "stomach"]):  reg = "gut"
            else: reg = "chest"
            regions.append({"name": b[:16], "region": reg})
        return "annotated_body", {"labels": regions}

    if icon == "science" and any(w in combined for w in
                                  ["atom", "element", "electron", "proton", "nucleus", "molecule"]):
        words = title.split()
        element = next((w[:2].upper() for w in words if len(w) >= 2), "X")
        return "atom_orbital", {"element": element}

    if icon == "warning" or any(w in combined for w in
                                  ["cause", "effect", "result", "leads to", "because", "therefore"]):
        return "cause_effect", {"steps": [b[:26] for b in bullets[:4]]}

    if icon == "check" or any(w in combined for w in
                               ["prevent", "protect", "must", "should", "recommend", "checklist"]):
        done = [True] * (len(bullets) // 2) + [False] * (len(bullets) - len(bullets) // 2)
        return "checklist", {"items": bullets[:6], "checked": done[:6]}

    if icon == "people":
        return "concept_map", {"center": title[:18], "concepts": [b[:20] for b in bullets[:6]]}

    if icon == "code":
        return "process_flow", {"steps": [b[:24] for b in bullets[:5]]}

    # Default: concept map
    return "concept_map", {"center": title[:18], "concepts": [b[:20] for b in bullets[:7]]}
