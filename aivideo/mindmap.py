"""Generate a mind map from a ScenePlan.

Produces two things:
  1. A PNG (Pillow) for embedding in video / download
  2. A JSON graph for the interactive D3 viewer in the browser
"""
import json
import math
import os
from PIL import Image, ImageDraw, ImageFont

W, H = 1920, 1080
CX, CY = W // 2, H // 2

THEME = {
    "bg":      (10, 18, 35),
    "center":  (56, 189, 248),
    "node_a":  (251, 191, 36),
    "node_b":  (74, 222, 128),
    "node_c":  (248, 113, 113),
    "node_d":  (167, 139, 250),
    "text":    (241, 245, 249),
    "muted":   (148, 163, 184),
    "line":    (51, 65, 85),
}
NODE_COLORS = [THEME["node_a"], THEME["node_b"], THEME["node_c"], THEME["node_d"]]

FONT_DIRS = ["C:/Windows/Fonts", "/usr/share/fonts/truetype/dejavu", "/Library/Fonts"]


def _font(size, bold=False):
    names = ["arialbd.ttf", "DejaVuSans-Bold.ttf"] if bold else ["arial.ttf", "DejaVuSans.ttf"]
    for d in FONT_DIRS:
        for n in names:
            p = os.path.join(d, n)
            if os.path.exists(p):
                return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def _wrap_center(draw, text, font, max_w):
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


def _draw_node(draw, cx, cy, r, color, label, font_size=22, text_color=None):
    # glow / shadow
    for extra in range(8, 0, -2):
        alpha_color = tuple(int(c * 0.15) for c in color)
        draw.ellipse([cx - r - extra, cy - r - extra, cx + r + extra, cy + r + extra],
                     fill=alpha_color)
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color)
    # label
    f = _font(font_size)
    tc = text_color or THEME["bg"]
    lines = _wrap_center(draw, label, f, r * 1.7)
    line_h = font_size + 4
    y_start = cy - (len(lines) * line_h) // 2
    for ln in lines:
        w = draw.textlength(ln, font=f)
        draw.text((cx - w // 2, y_start), ln, font=f, fill=tc)
        y_start += line_h


def _curved_line(draw, x1, y1, x2, y2, color, width=2):
    # approximate bezier with many line segments
    mx, my = (x1 + x2) / 2, (y1 + y2) / 2
    # offset control point perpendicular to line
    dx, dy = x2 - x1, y2 - y1
    length = math.hypot(dx, dy) or 1
    perp_x, perp_y = -dy / length * 40, dx / length * 40
    cx_ctrl, cy_ctrl = mx + perp_x, my + perp_y
    pts = []
    for i in range(21):
        t = i / 20
        px = (1-t)**2 * x1 + 2*(1-t)*t * cx_ctrl + t**2 * x2
        py = (1-t)**2 * y1 + 2*(1-t)*t * cy_ctrl + t**2 * y2
        pts.append((px, py))
    for i in range(len(pts) - 1):
        draw.line([pts[i], pts[i+1]], fill=color, width=width)


def render_mindmap(plan, path):
    img = Image.new("RGB", (W, H), THEME["bg"])
    draw = ImageDraw.Draw(img)

    # subtle radial grid
    for r in range(100, 600, 100):
        draw.ellipse([CX-r, CY-r, CX+r, CY+r], outline=(25, 35, 55), width=1)

    # centre node
    center_r = 90
    draw.ellipse([CX-center_r, CY-center_r, CX+center_r, CY+center_r], fill=THEME["center"])
    f_title = _font(26, bold=True)
    topic_lines = _wrap_center(draw, plan.topic, f_title, center_r * 1.8)
    lh = 32
    y0 = CY - (len(topic_lines) * lh) // 2
    for ln in topic_lines:
        w = draw.textlength(ln, font=f_title)
        draw.text((CX - w // 2, y0), ln, font=f_title, fill=THEME["bg"])
        y0 += lh

    # branch scenes (skip title/flashcard/quiz kind for cleaner map)
    branch_scenes = [s for s in plan.scenes if s.kind in ("bullets", "summary", "critique",
                                                            "dialogue", "debate")][:8]
    n = len(branch_scenes)
    if n == 0:
        img.save(path)
        return path

    radius = 340
    for i, scene in enumerate(branch_scenes):
        angle = (2 * math.pi * i / n) - math.pi / 2
        nx = int(CX + radius * math.cos(angle))
        ny = int(CY + radius * math.sin(angle))
        color = NODE_COLORS[i % len(NODE_COLORS)]

        # connector
        _curved_line(draw, CX, CY, nx, ny, color, width=2)

        # branch node
        node_r = 65
        _draw_node(draw, nx, ny, node_r, color, scene.title, font_size=20)

        # leaf bullets
        bullet_r = 30
        bullets = scene.bullets[:3]
        nb = len(bullets)
        spread = math.pi / 4
        for j, b in enumerate(bullets):
            leaf_angle = angle + spread * (j - (nb - 1) / 2) * (0.5 if nb > 1 else 0)
            leaf_dist = node_r + 120
            lx = int(nx + leaf_dist * math.cos(leaf_angle))
            ly = int(ny + leaf_dist * math.sin(leaf_angle))
            # clip to canvas
            lx = max(bullet_r + 10, min(W - bullet_r - 10, lx))
            ly = max(bullet_r + 10, min(H - bullet_r - 10, ly))
            leaf_color = tuple(max(0, c - 60) for c in color)
            _curved_line(draw, nx, ny, lx, ly, leaf_color, width=1)
            _draw_node(draw, lx, ly, bullet_r, leaf_color,
                       b[:30] + ("…" if len(b) > 30 else ""), font_size=14)

    # watermark
    wm = _font(22)
    draw.text((W - 20, H - 30), "aivideo Studio", font=wm, fill=THEME["muted"], anchor="rs")

    img.save(path)
    return path


def mindmap_json(plan):
    """Return a D3-compatible node/link graph."""
    nodes = [{"id": "root", "label": plan.topic, "kind": "root", "r": 60}]
    links = []
    branch_scenes = [s for s in plan.scenes if s.kind in ("bullets", "summary")]
    for i, scene in enumerate(branch_scenes):
        sid = f"s{i}"
        nodes.append({"id": sid, "label": scene.title, "kind": scene.kind,
                       "icon": scene.icon, "takeaway": scene.takeaway, "r": 40})
        links.append({"source": "root", "target": sid})
        for j, b in enumerate(scene.bullets[:3]):
            bid = f"s{i}b{j}"
            nodes.append({"id": bid, "label": b, "kind": "bullet", "r": 22})
            links.append({"source": sid, "target": bid})
    return {"nodes": nodes, "links": links}
