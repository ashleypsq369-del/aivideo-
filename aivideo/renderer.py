"""Rich animated frame renderer.

Generates one numpy frame array per time-step using pure Pillow + NumPy.
Each scene type gets a fully bespoke animated treatment — not a generic slide.

Animation vocabulary (consistent, not random):
  - Text reveals: characters appear left-to-right (typewriter)
  - Diagrams build: elements appear sequentially with ease-out scale+fade
  - Charts grow: bars/lines animate from 0 to final value
  - Bullets: each card slides up with stagger
  - Background: topic-specific particle field (subtle, not distracting)
  - Progress: glowing dot travels across timeline bar
"""
import math
import os
import random

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H = 1920, 1080

FONT_DIRS = [
    "C:/Windows/Fonts",
    "/usr/share/fonts/truetype/dejavu",
    "/usr/share/fonts/dejavu",
    "/Library/Fonts",
]

# ── fonts ─────────────────────────────────────────────────────────────────────

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


# ── easing ────────────────────────────────────────────────────────────────────

def _clamp(v, lo=0.0, hi=1.0):  return max(lo, min(hi, v))
def _p(t, start, dur):           return _clamp((t - start) / max(dur, 0.001))
def _ease_out(p):                return 1 - (1 - p) ** 3
def _ease_in(p):                 return p ** 3
def _ease_in_out(p):             return 3*p*p - 2*p*p*p
def _spring(p):
    # slight overshoot
    if p >= 1: return 1.0
    return 1 - math.exp(-6*p) * math.cos(10*p)


# ── colour helpers ────────────────────────────────────────────────────────────

def _lerp_col(c1, c2, t):
    return tuple(int(c1[i] + (c2[i]-c1[i])*t) for i in range(3))


def _alpha_col(color, alpha):
    """Return colour with components scaled by alpha (0-1)."""
    return tuple(int(c * alpha) for c in color[:3])


# ── background generators ─────────────────────────────────────────────────────

def _bg_gradient(T):
    """Create the base gradient background as a numpy array (cached)."""
    img  = Image.new("RGB", (W, H))
    draw = ImageDraw.Draw(img)
    for y in range(H):
        t  = y / H
        t2 = t * 2 if t < 0.5 else (t - 0.5) * 2
        if t < 0.5:
            c = tuple(int(T["bg_top"][i]*(1-t2) + T["bg_mid"][i]*t2) for i in range(3))
        else:
            c = tuple(int(T["bg_mid"][i]*(1-t2) + T["bg_bot"][i]*t2) for i in range(3))
        draw.line([(0, y), (W, y)], fill=c)
    return np.array(img, dtype=np.float32)


def _topic_particles(icon, T, seed=42):
    """Pre-generate a particle field appropriate for the topic."""
    rng    = random.Random(seed)
    ac     = T.get("accent", (56, 189, 248))
    ac2    = T.get("accent2", (251, 191, 36))
    muted  = T.get("muted",  (148, 163, 184))
    dark   = T.get("dark", True)
    alpha  = 0.06 if dark else 0.04

    img    = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw   = ImageDraw.Draw(img)

    if icon == "health":
        # cell-like circles
        for _ in range(40):
            x  = rng.randint(0, W);  y  = rng.randint(0, H)
            r  = rng.randint(20, 80)
            col = ac if rng.random() > 0.5 else ac2
            a   = int(255 * alpha * rng.uniform(0.5, 1.5))
            draw.ellipse([x-r, y-r, x+r, y+r], outline=(*col, a), width=2)

    elif icon == "science":
        # grid dots
        for x in range(60, W, 80):
            for y in range(40, H, 80):
                xj = x + rng.randint(-10, 10)
                yj = y + rng.randint(-10, 10)
                a  = int(255 * alpha * rng.uniform(0.5, 1.5))
                draw.ellipse([xj-3, yj-3, xj+3, yj+3], fill=(*ac, a))

    elif icon == "code":
        # binary-ish vertical lines
        for x in range(40, W, 60):
            xj = x + rng.randint(-5, 5)
            a  = int(255 * alpha * rng.uniform(0.3, 1.0))
            draw.line([(xj, 0), (xj, H)], fill=(*muted, a), width=1)

    elif icon == "people":
        # connecting lines (network feel)
        pts = [(rng.randint(0, W), rng.randint(0, H)) for _ in range(12)]
        for i, (x1, y1) in enumerate(pts):
            for x2, y2 in pts[i+1:i+3]:
                a = int(255 * alpha * 0.8)
                draw.line([(x1, y1), (x2, y2)], fill=(*ac, a), width=1)

    else:
        # subtle floating squares (default)
        for _ in range(30):
            x = rng.randint(0, W);  y = rng.randint(0, H)
            s = rng.randint(4, 16)
            a = int(255 * alpha * rng.uniform(0.3, 1.0))
            rot = rng.uniform(0, 45)
            draw.rectangle([x, y, x+s, y+s], outline=(*muted, a), width=1)

    return np.array(img, dtype=np.float32)


# ── text helpers ──────────────────────────────────────────────────────────────

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
            if cur: lines.append(cur)
            cur = w
    if cur: lines.append(cur)
    return lines


def _typewriter(text, progress):
    """Return partial text based on animation progress (0-1)."""
    n = max(1, int(len(text) * progress))
    return text[:n]


# ── compositing ───────────────────────────────────────────────────────────────

def _pil_to_np(img):
    if img.mode != "RGB": img = img.convert("RGB")
    return np.array(img, dtype=np.float32)


def _np_to_pil(arr):
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGB")


def _blend_layer(base, layer_rgba, alpha_mult=1.0):
    """Blend RGBA layer onto float32 base."""
    if layer_rgba.shape[2] == 4:
        a = layer_rgba[:, :, 3:4] / 255.0 * alpha_mult
        base = base * (1 - a) + layer_rgba[:, :, :3] * a
    else:
        base = base * (1 - alpha_mult) + layer_rgba * alpha_mult
    return base


def _draw_on(base, draw_fn):
    """Call draw_fn(draw, img) on a fresh PIL layer, blend onto base."""
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw  = ImageDraw.Draw(layer)
    draw_fn(draw, layer)
    return _blend_layer(base, np.array(layer, dtype=np.float32))


# ── reusable animated components ──────────────────────────────────────────────

def draw_growing_bar(draw, bx, by, bw, bh, fill_pct, color, label="", val_str="", f_label=None, f_val=None, T=None):
    """Draw a single animated bar filled to fill_pct (0-1)."""
    T = T or {}
    mu = T.get("muted", (148, 163, 184))
    txt = T.get("text", (241, 245, 249))
    # track
    draw.rounded_rectangle([bx, by, bx+bw, by+bh], 6,
                           fill=tuple(c//4 for c in color))
    # fill
    filled_h = int(bh * fill_pct)
    if filled_h > 4:
        draw.rounded_rectangle([bx, by+bh-filled_h, bx+bw, by+bh], 6, fill=color)
    # value label
    if val_str and f_val:
        draw.text((bx+bw//2, by-8), val_str, font=f_val, fill=color, anchor="mb")
    # x-axis label
    if label and f_label:
        draw.text((bx+bw//2, by+bh+10), label[:14], font=f_label, fill=mu, anchor="mt")


def draw_animated_line(draw, pts, progress, color, width=3):
    """Draw a line path animated to `progress` (0-1)."""
    n = max(2, int(len(pts) * progress))
    sub = pts[:n]
    for i in range(len(sub)-1):
        draw.line([sub[i], sub[i+1]], fill=color, width=width)
    # dot at current position
    if sub:
        x, y = sub[-1]
        draw.ellipse([x-6, y-6, x+6, y+6], fill=color)


def draw_node(draw, cx, cy, r, color, label, font, T, pop_p=1.0):
    """Draw a diagram node with scale-pop animation (pop_p 0-1)."""
    r2 = int(r * pop_p)
    if r2 < 2: return
    # glow
    for extra in range(16, 0, -4):
        glow = tuple(int(c*0.06) for c in color)
        draw.ellipse([cx-r2-extra, cy-r2-extra, cx+r2+extra, cy+r2+extra], fill=glow)
    draw.ellipse([cx-r2, cy-r2, cx+r2, cy+r2], fill=color)
    if pop_p > 0.3:
        lns = _wrap(draw, label[:16], font, r2*1.8)
        ly  = cy - len(lns)*9
        for ln in lns[:2]:
            draw.text((cx, ly), ln, font=font, fill=(10,18,35), anchor="mm")
            ly += 18


def draw_arrow(draw, x1, y1, x2, y2, color, progress=1.0, width=3, head=14):
    """Draw arrow from (x1,y1) to (x2,y2) animated to progress."""
    ex = x1 + (x2-x1)*progress
    ey = y1 + (y2-y1)*progress
    draw.line([(x1,y1),(ex,ey)], fill=color, width=width)
    if progress > 0.9:
        angle = math.atan2(y2-y1, x2-x1)
        for da in [0.4, -0.4]:
            hx = ex - head*math.cos(angle+da)
            hy = ey - head*math.sin(angle+da)
            draw.line([(ex,ey),(int(hx),int(hy))], fill=color, width=width)


def draw_progress_bar(draw, t, duration, T):
    """Full-width progress bar at bottom of frame."""
    bw = W - 160
    x0 = 80; y = H - 24
    pf = int(bw * min(t/max(duration,0.1), 1.0))
    # track
    draw.rounded_rectangle([x0, y, x0+bw, y+6], 3, fill=T.get("line",(30,48,80)))
    # glow fill
    if pf > 0:
        draw.rounded_rectangle([x0, y, x0+pf, y+6], 3, fill=T.get("accent",(56,189,248)))
        # glowing dot
        draw.ellipse([x0+pf-5, y-3, x0+pf+5, y+9], fill=T.get("accent2",(251,191,36)))


def draw_takeaway(draw, text, alpha, T):
    """Takeaway strip at bottom."""
    if not text or alpha < 0.02: return
    ac2 = T.get("accent2", (251,191,36))
    bg  = tuple(int(c*0.15*alpha) for c in ac2)
    draw.rectangle([80, H-98, W-80, H-48], fill=bg)
    draw.rectangle([80, H-100, 90, H-48], fill=tuple(int(c*alpha) for c in ac2))
    t = text[:115] + ("..." if len(text)>115 else "")
    col = tuple(int(c*alpha) for c in ac2)
    draw.text((110, H-74), "KEY INSIGHT  →  " + t, font=_font(26), fill=col)


# ── scene-specific frame builders ─────────────────────────────────────────────

class SceneRenderer:
    """Base: manages background, particles, progress bar, takeaway."""

    def __init__(self, scene, T, duration, fps=24):
        self.scene    = scene
        self.T        = T
        self.duration = duration
        self.fps      = fps
        self.ac       = T.get("accent",  (56, 189, 248))
        self.ac2      = T.get("accent2", (251, 191, 36))
        self.gr       = T.get("green",   (74, 222, 128))
        self.rd       = T.get("red",     (248, 113, 113))
        self.pu       = T.get("purple",  (167, 139, 250))
        self.txt      = T.get("text",    (241, 245, 249))
        self.mu       = T.get("muted",   (148, 163, 184))
        self.card     = T.get("card",    (20, 32, 55))

        # Pre-compute static layers
        self._bg       = _bg_gradient(T)
        self._particles = _topic_particles(scene.icon, T, seed=hash(scene.title) & 0xFFFF)

    def base_frame(self, t):
        """Build the base frame: gradient + particles."""
        frame = self._bg.copy()
        frame = _blend_layer(frame, self._particles, 1.0)
        return frame

    def render(self, t):
        """Override in subclasses. Must return uint8 numpy array (H,W,3)."""
        frame = self.base_frame(t)
        img   = _np_to_pil(frame)
        draw  = ImageDraw.Draw(img)
        draw_progress_bar(draw, t, self.duration, self.T)
        tk_alpha = _ease_in_out(_p(t, self.duration-1.4, 0.6))
        draw_takeaway(draw, self.scene.takeaway, tk_alpha, self.T)
        return np.array(img, dtype=np.uint8)


class TitleRenderer(SceneRenderer):
    def render(self, t):
        frame = self.base_frame(t)
        img   = _np_to_pil(frame)
        draw  = ImageDraw.Draw(img)

        # Large decorative circle behind badge
        circle_p = _spring(_p(t, 0.0, 0.5))
        cr = int(140 * circle_p)
        if cr > 5:
            for extra in range(40, 0, -8):
                draw.ellipse([W//2-cr-extra, 180-cr-extra, W//2+cr+extra, 180+cr+extra],
                             fill=tuple(int(c*0.05) for c in self.ac))
            draw.ellipse([W//2-cr, 180-cr, W//2+cr, 180+cr],
                         fill=tuple(int(c*0.15) for c in self.ac))

        # Icon badge pops in
        from .slides import _badge, ICON_COLOR_KEY
        r2 = int(80 * _spring(_p(t, 0.1, 0.45)))
        if r2 > 5:
            _badge(draw, self.scene.icon, W//2, 180, r2, self.T)

        # Accent line draws in
        line_p = _ease_out(_p(t, 0.4, 0.3))
        lw = int(380 * line_p)
        if lw > 2:
            draw.rectangle([W//2-lw, 310, W//2+lw, 316], fill=self.ac)

        # Title types in
        type_p = _ease_out(_p(t, 0.5, 0.6))
        if type_p > 0:
            f    = _font(88, bold=True)
            full = self.scene.title
            text = _typewriter(full, type_p)
            lns  = _wrap(draw, text, f, W-320)
            y    = 350
            for ln in lns[:3]:
                draw.text((W//2, y), ln, font=f, fill=self.txt, anchor="mt")
                y += 105

        # Subtitle fades in
        sub_p = _p(t, 1.1, 0.5)
        if sub_p > 0 and self.scene.narration:
            f2   = _font(38)
            col  = tuple(int(c*sub_p) for c in self.mu)
            lns2 = _wrap(draw, self.scene.narration[:140], f2, W-400)
            y2   = 580
            for ln in lns2[:2]:
                draw.text((W//2, y2), ln, font=f2, fill=col, anchor="mt")
                y2 += 52

        # Particle burst at start
        if t < 1.0:
            burst_rng = random.Random(99)
            for _ in range(12):
                angle = burst_rng.uniform(0, 2*math.pi)
                dist  = burst_rng.uniform(60, 180) * min(t*2, 1.0)
                px    = int(W//2 + dist*math.cos(angle))
                py    = int(180  + dist*math.sin(angle) * 0.5)
                pr    = int(burst_rng.randint(3,9) * max(0, 1-t))
                col2  = self.ac if burst_rng.random()>0.5 else self.ac2
                if pr > 0:
                    draw.ellipse([px-pr, py-pr, px+pr, py+pr], fill=col2)

        # Bottom bar draws in
        bar_p = _ease_out(_p(t, 0.3, 0.4))
        if bar_p > 0:
            bw = int(W * bar_p)
            x0 = (W - bw) // 2
            draw.rectangle([x0, H-10, x0+bw, H], fill=self.ac)

        draw_progress_bar(draw, t, self.duration, self.T)
        draw_takeaway(draw, self.scene.takeaway, _ease_in_out(_p(t, self.duration-1.4, 0.6)), self.T)
        return np.array(img, dtype=np.uint8)


class BulletsRenderer(SceneRenderer):
    def __init__(self, scene, T, duration, fps=24):
        super().__init__(scene, T, duration, fps)
        # Pre-render the visual graphic for the right panel
        self._visual = self._make_visual()

    def _make_visual(self):
        try:
            from .assets import make_visual, choose_visual_spec
            vt, spec = choose_visual_spec(self.scene)
            img = make_visual(vt, spec, self.T)
            return np.array(img.resize((860, 540), Image.LANCZOS), dtype=np.float32)
        except Exception:
            return None

    def render(self, t):
        from .slides import ICON_COLOR_KEY, _badge
        frame = self.base_frame(t)
        img   = _np_to_pil(frame)
        draw  = ImageDraw.Draw(img)

        color = self.T.get(ICON_COLOR_KEY.get(self.scene.icon, "accent"), self.ac)

        # LEFT accent bar draws downward
        bar_h = int(H * _ease_out(_p(t, 0.0, 0.25)))
        draw.rectangle([0, 0, 14, bar_h], fill=color)

        # Right panel background fades in
        rp_alpha = _ease_out(_p(t, 0.05, 0.3))
        if rp_alpha > 0:
            rp_col = tuple(min(255, c + 8) for c in self.card)
            rp_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            rp_d = ImageDraw.Draw(rp_layer)
            rp_d.rounded_rectangle([1012, VIS_Y - 14, 1912, VIS_Y + 558],
                                   14, fill=(*rp_col, int(220 * rp_alpha)))
            img.paste(rp_layer, (0, 0), mask=rp_layer.split()[3])
            draw = ImageDraw.Draw(img)

        # Icon badge bounces in
        r2 = int(58 * _spring(_p(t, 0.15, 0.3)))
        if r2 > 4:
            _badge(draw, self.scene.icon, 128, 128, r2, self.T)

        # Title slides from left
        p  = _ease_out(_p(t, 0.22, 0.38))
        xo = int((1-p) * -270)
        ft = _font(66, bold=True)
        tl = _wrap(draw, self.scene.title, ft, 980)
        ty = 86
        for ln in tl[:2]:
            draw.text((224+xo, ty), ln, font=ft, fill=self.txt)
            ty += 78
        # Underline draws in
        if p > 0.5:
            uw = min(560, int(draw.textlength(self.scene.title, font=ft)*p))
            draw.rectangle([224, ty+3, 224+uw, ty+9], fill=color)

        # Bullet cards stagger upward
        f_b   = _font(44)
        f_num = _font(26, bold=True)
        y0    = ty + 44
        for i, b in enumerate(self.scene.bullets[:4]):
            if y0 > H-230: break
            blines = _wrap(draw, b, f_b, 820)
            ch2    = len(blines[:2])*54 + 20
            p2     = _spring(_p(t, 0.5 + i*0.38, 0.32))
            yo     = int((1-p2)*58)
            if p2 < 0.02: y0 += ch2+18; continue

            # Card
            ci   = Image.new("RGBA", (860, ch2), (0,0,0,0))
            cd   = ImageDraw.Draw(ci)
            cd.rounded_rectangle([0, 0, 858, ch2], 10,
                                 fill=(*self.card, int(240*p2)))
            # Number circle
            cd.ellipse([-24, ch2//2-24, 24, ch2//2+24], fill=color)
            cd.text((0, ch2//2), str(i+1), font=f_num, fill=(10,18,35), anchor="mm")
            # Text typewriter
            by2 = 10
            for ln in blines[:2]:
                cd.text((42, by2), _typewriter(ln, min(1.0, (p2-0.1)/0.5)),
                        font=f_b, fill=self.txt)
                by2 += 54
            # Accent left border
            cd.rectangle([0, 0, 5, ch2], fill=color)

            # Paste card onto img using alpha mask
            paste_x = 138
            paste_y = max(0, min(H - ch2, y0 + yo))
            img.paste(ci, (paste_x, paste_y), mask=ci.split()[3])
            draw = ImageDraw.Draw(img)
            y0  += ch2 + 18

        # Visual panel fades in with slide
        if self._visual is not None:
            vis_alpha = _ease_in_out(_p(t, 0.9, 0.5))
            if vis_alpha > 0.02:
                vis_pil = Image.fromarray(np.clip(self._visual, 0, 255).astype(np.uint8))
                # Create alpha-blended version
                bg_crop = img.crop((1020, VIS_Y, 1020+860, VIS_Y+540))
                blended = Image.blend(bg_crop, vis_pil, vis_alpha)
                img.paste(blended, (1020, VIS_Y))
                draw = ImageDraw.Draw(img)

        draw_progress_bar(draw, t, self.duration, self.T)
        draw_takeaway(draw, self.scene.takeaway,
                      _ease_in_out(_p(t, self.duration-1.4, 0.6)), self.T)
        return np.array(img, dtype=np.uint8)


VIS_Y = 220  # match slides.py VIS_Y


class QuizRenderer(SceneRenderer):
    def render(self, t):
        from .slides import _badge
        frame = self.base_frame(t)
        img   = _np_to_pil(frame)
        draw  = ImageDraw.Draw(img)

        draw.rectangle([0, 0, 14, H], fill=self.ac2)
        _badge(draw, "check", 128, 118, 54, self.T)

        # "KNOWLEDGE CHECK" types in
        kc_p = _ease_out(_p(t, 0.1, 0.4))
        draw.text((218, 86), _typewriter("KNOWLEDGE CHECK", kc_p),
                  font=_font(44, bold=True), fill=self.ac2)

        # Question slides down
        q_p = _ease_out(_p(t, 0.3, 0.5))
        yo  = int((1-q_p)*-80)
        if q_p > 0:
            fq = _font(50, bold=True)
            y  = 194+yo
            for ln in _wrap(draw, self.scene.question, fq, W-230)[:3]:
                draw.text((108, y), ln, font=fq, fill=self.txt)
                y += 66

        # Options fly from right
        opt_colors = [self.ac, self.gr, self.rd, self.pu]
        y2 = 420
        for i, opt in enumerate(self.scene.options[:4]):
            p2 = _ease_out(_p(t, 0.65+i*0.35, 0.3))
            xo = int((1-p2)*440)
            if p2 < 0.02: y2+=114; continue
            correct = i == self.scene.answer_index
            oc  = opt_colors[i%len(opt_colors)]
            bg  = tuple(int(c*0.15) for c in oc) if self.T.get("dark") \
                  else tuple(min(255,int(c*0.12)+235) for c in oc)
            draw.rounded_rectangle([108+xo, y2, W-108+xo, y2+92], 16, fill=bg,
                                   outline=oc if correct else self.T.get("line",(30,48,80)),
                                   width=3 if correct else 1)
            draw.ellipse([124+xo, y2+18, 164+xo, y2+58], fill=oc)
            draw.text((144+xo, y2+38), "ABCD"[i], font=_font(28,bold=True),
                      fill=(255,255,255), anchor="mm")
            draw.text((188+xo, y2+46), opt[:74], font=_font(40), fill=self.txt, anchor="lm")
            if correct and t > self.duration*0.7:
                pulse = abs(math.sin(t*4)) * 0.5 + 0.5
                draw.text((W-128+xo, y2+46), "✓ Correct",
                          font=_font(28,bold=True),
                          fill=tuple(int(c*pulse) for c in oc), anchor="rm")
            y2 += 114

        draw_progress_bar(draw, t, self.duration, self.T)
        return np.array(img, dtype=np.uint8)


class SummaryRenderer(SceneRenderer):
    def render(self, t):
        from .slides import _badge
        frame = self.base_frame(t)
        img   = _np_to_pil(frame)
        draw  = ImageDraw.Draw(img)

        draw.rectangle([0, 0, 14, H], fill=self.gr)
        _badge(draw, "check", 128, 118, 60, self.T)
        draw.text((218, 86), self.scene.title, font=_font(68,bold=True), fill=self.gr)
        draw.rectangle([218, 164, 660, 170], fill=self.ac2)

        f  = _font(44)
        y  = 208
        for i, b in enumerate(self.scene.bullets[:5]):
            if y > H-250: break
            p  = _spring(_p(t, 0.22+i*0.26, 0.36))
            yo = int((1-p)*65)
            if p < 0.02: y+=70; continue
            draw.text((158, y+yo), "▸", font=f, fill=self.ac2)
            for ln in _wrap(draw, b, f, W-270)[:2]:
                draw.text((218, y+yo), ln, font=f, fill=self.txt)
                y += 54
            y += 12

        # Completion band
        band_p = _ease_out(_p(t, self.duration-1.5, 0.5))
        if band_p > 0.01:
            band_col = (15,35,15) if self.T.get("dark") else (220,255,220)
            draw.rectangle([0, H-128, W, H-50], fill=band_col)
            draw.text((W//2, H-89), "🎓  Lesson complete! Well done.",
                      font=_font(36,bold=True), fill=self.gr, anchor="mm")

        # Confetti
        if t > self.duration-2.0:
            rng  = random.Random(77)
            cols = [self.gr, self.ac2, self.ac, self.pu]
            for _ in range(24):
                cx2 = int(rng.uniform(0,W)); spd=rng.uniform(90,220)
                cy2 = int((t-(self.duration-2.0))*spd*100%H)
                cr  = rng.randint(5,14)
                draw.rectangle([cx2,cy2,cx2+cr*2,cy2+cr], fill=cols[rng.randint(0,len(cols)-1)])

        draw_progress_bar(draw, t, self.duration, self.T)
        draw_takeaway(draw, self.scene.takeaway,
                      _ease_in_out(_p(t, self.duration-1.4, 0.6)), self.T)
        return np.array(img, dtype=np.uint8)


class FlashcardRenderer(SceneRenderer):
    def render(self, t):
        from .slides import _badge
        frame = self.base_frame(t)
        img   = _np_to_pil(frame)
        draw  = ImageDraw.Draw(img)

        pu = self.pu
        draw.rectangle([0, 0, 14, H], fill=pu)
        _badge(draw, "book", 128, 108, 50, self.T)
        draw.text((208, 83), "FLASHCARDS", font=_font(50,bold=True), fill=self.txt)

        cards = self.scene.flashcards[:4]
        if not cards:
            draw_progress_bar(draw, t, self.duration, self.T)
            return np.array(img, dtype=np.uint8)

        cols2 = 2; cw=(W-160)//cols2
        ch    = min((H-300)//max(math.ceil(len(cards)/cols2),1), 240)

        for i, card in enumerate(cards):
            col2, row = i%cols2, i//cols2
            x0, y0   = 80+col2*cw, 220+row*ch
            p        = _spring(_p(t, 0.2+i*0.5, 0.42))
            fp       = p*2
            scale_x  = 1-fp if fp<1 else fp-1
            is_front = fp<1
            cx2      = x0+cw//2
            hw       = int((cw-20)*scale_x/2)
            if hw < 2: continue
            fill_c = pu if is_front else self.ac
            draw.rounded_rectangle([cx2-hw, y0, cx2+hw, y0+ch-20], 12, fill=fill_c)
            if hw > 24:
                # Typewriter label
                label = card["front"][:30] if is_front else card["back"][:30]
                tw_p  = min(1.0, (p-0.1)/0.5) if p>0.1 else 0
                draw.text((cx2, y0+ch//2-10), _typewriter(label, tw_p),
                          font=_font(26), fill=(10,18,35) if is_front else (10,18,35),
                          anchor="mm")

        draw_progress_bar(draw, t, self.duration, self.T)
        return np.array(img, dtype=np.uint8)


# ── dispatcher ────────────────────────────────────────────────────────────────

SCENE_RENDERERS = {
    "title":     TitleRenderer,
    "bullets":   BulletsRenderer,
    "quiz":      QuizRenderer,
    "summary":   SummaryRenderer,
    "flashcard": FlashcardRenderer,
}


def make_animated_clip(scene, audio_path, out_path, style="auto",
                       quality="standard", fps=24):
    """Render a fully animated MP4 clip for one scene.
    Returns duration in seconds.
    Falls back to static clip if MoviePy unavailable.
    """
    from .video import _find as _ff, make_clip as _static_clip
    if quality == "draft":
        # Static path: render one slide frame and use FFmpeg
        from .slides import render_scene, THEMES
        import tempfile
        T = THEMES.get(style, THEMES["auto"])
        with tempfile.TemporaryDirectory() as td:
            slide_path = os.path.join(td, "slide.png")
            render_scene(scene, 0, 1, slide_path, style)
            return _static_clip(slide_path, audio_path, out_path)

    try:
        import numpy as _np
        from moviepy import VideoClip, AudioFileClip
    except ImportError:
        from .slides import render_scene
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            slide_path = os.path.join(td, "slide.png")
            render_scene(scene, 0, 1, slide_path, style)
        return _static_clip(slide_path, audio_path, out_path)

    # Set FFmpeg path for MoviePy
    try:
        os.environ["FFMPEG_BINARY"] = _ff("ffmpeg")
    except Exception:
        pass

    from .slides import THEMES
    import wave as _wave
    T = THEMES.get(style, THEMES["auto"])

    # Audio duration
    try:
        with _wave.open(audio_path, "rb") as wf:
            audio_dur = wf.getnframes() / wf.getframerate()
    except Exception:
        audio_dur = 3.0
    duration = audio_dur + 0.7

    # Build renderer
    RendererClass = SCENE_RENDERERS.get(scene.kind, BulletsRenderer)
    renderer = RendererClass(scene, T, duration, fps)

    def make_frame(t):
        try:
            return renderer.render(t)
        except Exception:
            # Fallback: black frame
            return _np.zeros((H, W, 3), dtype=_np.uint8)

    try:
        clip  = VideoClip(make_frame, duration=duration)
        audio = AudioFileClip(audio_path)
        clip  = clip.with_audio(audio)
        clip.write_videofile(
            out_path, fps=fps,
            codec="libx264", audio_codec="aac",
            preset="veryfast", ffmpeg_params=["-pix_fmt", "yuv420p"],
            logger=None,
        )
        clip.close()
        audio.close()
    except Exception as e:
        print(f"[renderer] MoviePy failed ({e}), using static fallback.")
        from .slides import render_scene
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            slide_path = os.path.join(td, "slide.png")
            render_scene(scene, 0, 1, slide_path, style)
        return _static_clip(slide_path, audio_path, out_path)

    return duration
