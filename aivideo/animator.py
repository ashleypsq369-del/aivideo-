"""Animated clip renderer — MoviePy + NumPy + Pillow.

Each scene kind gets its own animated treatment:
  title     — badge scales in, title slides from left, subtitle fades, particles scatter
  bullets   — accent bar draws down, badge pops, title slides, bullets stagger up,
               right-panel visual fades in (from assets.py)
  quiz      — question slides down, options fly in from right
  summary   — bullets fly up, completion band rises, confetti falls
  flashcard — cards flip in sequentially

Falls back to static video.make_clip() if MoviePy unavailable or quality=="draft".
"""
import math
import os
import wave

from PIL import Image, ImageDraw, ImageFont

ANIMATION_AVAILABLE = False
try:
    import numpy as np
    from moviepy import VideoClip, AudioFileClip, concatenate_videoclips
    ANIMATION_AVAILABLE = True
except ImportError:
    np = None

from . import slides as _slides
from . import video  as _video

W, H, FPS = 1920, 1080, 24
FONT_DIRS  = ["C:/Windows/Fonts", "/usr/share/fonts/truetype/dejavu",
              "/usr/share/fonts/dejavu", "/Library/Fonts"]


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


def _clamp(v, lo=0.0, hi=1.0):
    return max(lo, min(hi, v))


def _prog(t, start, dur):
    return _clamp((t - start) / max(dur, 0.001))


def _ease_out(p):
    return 1 - (1 - p) ** 3


def _ease_in_out(p):
    return 3 * p * p - 2 * p * p * p


def _bounce(p):
    return 4 * p * p * p if p < 0.5 else 1 - (-2 * p + 2) ** 3 / 2


def _pil_to_np(img):
    if img.mode != "RGB":
        img = img.convert("RGB")
    return np.array(img, dtype=np.uint8)


def _np_to_pil(arr):
    return Image.fromarray(arr.astype(np.uint8), "RGB")


def _blend(base, overlay_pil, x, y, alpha=1.0):
    """Alpha-blend overlay_pil onto base numpy array at (x, y)."""
    if np is None:
        return base
    ow, oh = overlay_pil.size
    x0, y0 = int(x), int(y)
    x1, y1 = x0 + ow, y0 + oh
    bx0 = max(0, x0);  bx1 = min(W, x1)
    by0 = max(0, y0);  by1 = min(H, y1)
    if bx0 >= bx1 or by0 >= by1:
        return base
    ox0 = bx0 - x0;  ox1 = ox0 + (bx1 - bx0)
    oy0 = by0 - y0;  oy1 = oy0 + (by1 - by0)
    ov     = np.array(overlay_pil.crop((ox0, oy0, ox1, oy1)).convert("RGB"), dtype=np.float32)
    base_r = base[by0:by1, bx0:bx1].astype(np.float32)
    res    = base.copy()
    res[by0:by1, bx0:bx1] = (base_r * (1 - alpha) + ov * alpha).astype(np.uint8)
    return res


def _wav_dur(path):
    try:
        with wave.open(path, "rb") as wf:
            return wf.getnframes() / wf.getframerate()
    except Exception:
        return 3.0


def _make_base(T):
    img  = Image.new("RGB", (W, H))
    draw = ImageDraw.Draw(img)
    _slides._bg(draw, T)
    return _pil_to_np(img)


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


def _get_visual(scene, T):
    """Pre-render the right-panel visual for a bullets scene."""
    try:
        from .assets import make_visual, choose_visual_spec
        vt, spec = choose_visual_spec(scene)
        return _pil_to_np(make_visual(vt, spec, T))
    except Exception:
        return None


# ── per-kind frame builders ───────────────────────────────────────────────────

def _frame_title(t, scene, T, base, visual, dur):
    img  = _np_to_pil(base.copy())
    draw = ImageDraw.Draw(img)
    ac   = T.get("accent",  (56, 189, 248))
    ac2  = T.get("accent2", (251, 191, 36))
    txt  = T.get("text",    (241, 245, 249))
    mu   = T.get("muted",   (148, 163, 184))

    # badge scales in
    r = int(100 * _ease_out(_prog(t, 0.15, 0.4)))
    if r > 5:
        _slides._badge(draw, scene.icon, W // 2, 270, r, T)

    # title slides from left
    p  = _ease_out(_prog(t, 0.3, 0.55))
    xo = int((1 - p) * -320)
    if p > 0:
        f     = _font(96, bold=True)
        lines = _wrap(draw, scene.title, f, W - 320)
        y     = 448
        for ln in lines[:3]:
            draw.text((W // 2 + xo, y), ln, font=f, fill=txt, anchor="mt")
            y += 110

    # subtitle fades in
    sa = _prog(t, 0.9, 0.5)
    if sa > 0 and scene.narration:
        f  = _font(40)
        y2 = 700
        sc = tuple(int(c * sa) for c in mu)
        for ln in _wrap(draw, scene.narration[:140], f, W - 400)[:2]:
            draw.text((W // 2, y2), ln, font=f, fill=sc, anchor="mt")
            y2 += 54

    # scatter particles
    import random as _r
    rng = _r.Random(42)
    for _ in range(8):
        px  = int(rng.uniform(W // 2 - 220, W // 2 + 220))
        py  = int(rng.uniform(180, 380))
        pr  = int(rng.randint(4, 11) * _ease_out(_prog(t, rng.uniform(0, 0.5), 0.3)))
        if pr > 0:
            draw.ellipse([px - pr, py - pr, px + pr, py + pr], fill=ac2)

    draw.rectangle([0, H - 12, W, H], fill=ac)
    return img


def _frame_bullets(t, scene, T, base, visual, dur):
    img  = _np_to_pil(base.copy())
    draw = ImageDraw.Draw(img)
    from .slides import ICON_COLOR_KEY, TEXT_W, VIS_X, VIS_Y, VIS_W, VIS_H
    color = T.get(ICON_COLOR_KEY.get(scene.icon, "accent"), T.get("accent", (56, 189, 248)))
    txt   = T.get("text",   (241, 245, 249))
    card  = T.get("card",   (20, 32, 55))

    # Accent bar draws downward
    bh = int(H * _ease_out(_prog(t, 0.0, 0.3)))
    draw.rectangle([0, 0, 14, bh], fill=color)

    # Right panel background appears
    rp_alpha = _prog(t, 0.1, 0.3)
    if rp_alpha > 0:
        rp_bg = tuple(max(0, c - 4) for c in card)
        rp_img = Image.new("RGB", (VIS_W + 16, VIS_H + 34), rp_bg)
        base_arr = _pil_to_np(img)
        base_arr = _blend(base_arr, rp_img, VIS_X - 8, VIS_Y - 10, rp_alpha)
        img  = _np_to_pil(base_arr)
        draw = ImageDraw.Draw(img)

    # Badge pops in with bounce
    r = int(58 * _bounce(_prog(t, 0.18, 0.3)))
    if r > 4:
        _slides._badge(draw, scene.icon, 128, 128, r, T)

    # Title slides from left
    p  = _ease_out(_prog(t, 0.28, 0.4))
    xo = int((1 - p) * -260)
    ft = _font(68, bold=True)
    tl = _wrap(draw, scene.title, ft, TEXT_W - 220)
    ty = 88
    for ln in tl[:2]:
        draw.text((224 + xo, ty), ln, font=ft, fill=txt)
        ty += 80
    if p > 0.5:
        uw = min(580, int(draw.textlength(scene.title, font=ft) * p))
        draw.rectangle([224, ty + 4, 224 + uw, ty + 10], fill=color)

    # Bullet cards stagger upward
    f_b   = _font(46)
    f_num = _font(28, bold=True)
    y0    = ty + 46
    for i, b in enumerate(scene.bullets[:4]):
        if y0 > H - 230:
            break
        blines = _wrap(draw, b, f_b, TEXT_W - 220)
        ch2    = len(blines[:2]) * 56 + 22
        p2     = _ease_out(_prog(t, 0.55 + i * 0.42, 0.35))
        yo     = int((1 - p2) * 55)
        if p2 < 0.02:
            y0 += ch2 + 20
            continue
        # card background
        ci    = Image.new("RGB", (TEXT_W - 160, ch2), card)
        cdraw = ImageDraw.Draw(ci)
        cdraw.rounded_rectangle([0, 0, TEXT_W - 162, ch2], 10, fill=card)
        # number circle
        cdraw.ellipse([-24, ch2 // 2 - 24, 24, ch2 // 2 + 24], fill=color)
        cdraw.text((0, ch2 // 2), str(i + 1), font=f_num, fill=(10, 18, 35), anchor="mm")
        by2 = 10
        for ln in blines[:2]:
            cdraw.text((38, by2), ln, font=f_b, fill=txt)
            by2 += 56
        arr  = _pil_to_np(img)
        arr  = _blend(arr, ci, 138, y0 + yo, p2)
        img  = _np_to_pil(arr)
        draw = ImageDraw.Draw(img)
        y0  += ch2 + 20

    # Visual fades in on right panel
    if visual is not None:
        ga = _ease_in_out(_prog(t, 0.9, 0.5))
        if ga > 0.02:
            vis_pil = _np_to_pil(visual)
            # Resize to fit panel exactly
            if vis_pil.size != (VIS_W, VIS_H):
                vis_pil = vis_pil.resize((VIS_W, VIS_H), Image.LANCZOS)
            arr = _pil_to_np(img)
            arr = _blend(arr, vis_pil, VIS_X, VIS_Y, ga)
            img = _np_to_pil(arr)

    return img


def _frame_quiz(t, scene, T, base, visual, dur):
    img  = _np_to_pil(base.copy())
    draw = ImageDraw.Draw(img)
    ac2  = T.get("accent2", (251, 191, 36))
    txt  = T.get("text",    (241, 245, 249))
    ac   = T.get("accent",  (56, 189, 248))
    gr   = T.get("green",   (74, 222, 128))
    rd   = T.get("red",     (248, 113, 113))
    pu   = T.get("purple",  (167, 139, 250))

    draw.rectangle([0, 0, 14, H], fill=ac2)
    _slides._badge(draw, "check", 128, 118, 54, T)
    draw.text((218, 88), "KNOWLEDGE CHECK", font=_font(44, bold=True), fill=ac2)

    # Question slides down
    p  = _ease_out(_prog(t, 0.25, 0.5))
    yo = int((1 - p) * -90)
    if p > 0:
        fq = _font(52, bold=True)
        y  = 196 + yo
        for ln in _wrap(draw, scene.question, fq, W - 220)[:3]:
            draw.text((108, y), ln, font=fq, fill=txt)
            y += 68

    # Options fly in from right
    opt_colors = [ac, gr, rd, pu]
    y2 = 430
    for i, opt in enumerate(scene.options[:4]):
        p2  = _ease_out(_prog(t, 0.7 + i * 0.38, 0.35))
        xo2 = int((1 - p2) * 420)
        if p2 < 0.02:
            y2 += 116
            continue
        col     = opt_colors[i % len(opt_colors)]
        correct = i == scene.answer_index
        bg = tuple(int(c * 0.15) for c in col) if T.get("dark") \
             else tuple(min(255, int(c * 0.12) + 235) for c in col)
        draw.rounded_rectangle([108 + xo2, y2, W - 108 + xo2, y2 + 92], 16,
                               fill=bg,
                               outline=col if correct else T.get("line", (30, 48, 80)),
                               width=3 if correct else 1)
        draw.ellipse([124 + xo2, y2 + 18, 164 + xo2, y2 + 58], fill=col)
        draw.text((144 + xo2, y2 + 38), "ABCD"[i],
                  font=_font(28, bold=True), fill=(255, 255, 255), anchor="mm")
        draw.text((188 + xo2, y2 + 46), opt[:74],
                  font=_font(42), fill=txt, anchor="lm")
        y2 += 116
    return img


def _frame_summary(t, scene, T, base, visual, dur):
    img  = _np_to_pil(base.copy())
    draw = ImageDraw.Draw(img)
    gr   = T.get("green",   (74, 222, 128))
    ac2  = T.get("accent2", (251, 191, 36))
    txt  = T.get("text",    (241, 245, 249))

    draw.rectangle([0, 0, 14, H], fill=gr)
    _slides._badge(draw, "check", 128, 118, 60, T)
    draw.text((218, 86), scene.title, font=_font(70, bold=True), fill=gr)
    draw.rectangle([218, 168, 680, 174], fill=ac2)

    f  = _font(46)
    y  = 214
    for i, b in enumerate(scene.bullets[:5]):
        if y > H - 250:
            break
        p  = _ease_out(_prog(t, 0.25 + i * 0.28, 0.38))
        yo = int((1 - p) * 65)
        if p < 0.02:
            y += 70
            continue
        for ln in _wrap(draw, b, f, W - 270)[:2]:
            draw.text((218, y + yo), ln, font=f, fill=txt)
            y += 56
        y += 14

    # Completion band slides up
    band_p = _ease_out(_prog(t, dur - 1.6, 0.5))
    if band_p > 0.02:
        band = (15, 35, 15) if T.get("dark") else (220, 255, 220)
        draw.rectangle([0, H - 128, W, H - 50], fill=band)
        draw.text((W // 2, H - 89), "🎓  Lesson complete! Well done.",
                  font=_font(36, bold=True), fill=gr, anchor="mm")

    # Confetti particles
    if t > dur - 2.2:
        import random as _r
        rng  = _r.Random(77)
        cols = [gr, ac2, T.get("accent", (56, 189, 248)), T.get("purple", (167, 139, 250))]
        for _ in range(22):
            cx2 = int(rng.uniform(0, W))
            spd = rng.uniform(90, 220)
            cy2 = int((t - (dur - 2.2)) * spd * 100 % H)
            cr  = rng.randint(5, 14)
            draw.rectangle([cx2, cy2, cx2 + cr * 2, cy2 + cr],
                           fill=cols[rng.randint(0, len(cols) - 1)])
    return img


def _frame_flashcard(t, scene, T, base, visual, dur):
    img  = _np_to_pil(base.copy())
    draw = ImageDraw.Draw(img)
    pu   = T.get("purple", (167, 139, 250))
    txt  = T.get("text",   (241, 245, 249))
    ac   = T.get("accent", (56, 189, 248))

    draw.rectangle([0, 0, 14, H], fill=pu)
    _slides._badge(draw, "book", 128, 108, 50, T)
    draw.text((208, 83), "FLASHCARDS", font=_font(50, bold=True), fill=txt)

    cards = scene.flashcards[:4]
    if not cards:
        return img

    cols2 = 2
    cw    = (W - 160) // cols2
    ch    = min((H - 300) // max(math.ceil(len(cards) / cols2), 1), 240)

    for i, card in enumerate(cards):
        col2, row = i % cols2, i // cols2
        x0, y0   = 80 + col2 * cw, 220 + row * ch
        p        = _ease_out(_prog(t, 0.25 + i * 0.55, 0.42))
        fp       = p * 2
        scale_x  = 1 - fp if fp < 1 else fp - 1
        is_front = fp < 1
        cx_card  = x0 + cw // 2
        hw       = int((cw - 20) * scale_x / 2)
        if hw < 2:
            continue
        fill_c = pu if is_front else ac
        draw.rounded_rectangle([cx_card - hw, y0, cx_card + hw, y0 + ch - 20],
                               12, fill=fill_c)
        if hw > 22:
            label = card["front"][:30] if is_front else card["back"][:30]
            draw.text((cx_card, y0 + ch // 2 - 10), label,
                      font=_font(26), fill=(10, 18, 35), anchor="mm")
    return img


def _frame_generic(t, scene, T, base, visual, dur):
    return _np_to_pil(base)


BUILDERS = {
    "title":     _frame_title,
    "bullets":   _frame_bullets,
    "quiz":      _frame_quiz,
    "summary":   _frame_summary,
    "flashcard": _frame_flashcard,
}


# ── public entry points ───────────────────────────────────────────────────────

def make_animated_clip(scene, slide_image_path, audio_path, out_path,
                       style="auto", quality="standard"):
    """Render an animated MP4 clip. Returns duration in seconds."""
    if quality == "draft" or not ANIMATION_AVAILABLE:
        return _video.make_clip(slide_image_path, audio_path, out_path)

    # Ensure FFmpeg is findable
    try:
        from .video import _find as _ff
        os.environ["FFMPEG_BINARY"] = _ff("ffmpeg")
    except Exception:
        pass

    from moviepy import VideoClip, AudioFileClip

    T         = _slides.THEMES.get(style, _slides.THEMES["auto"])
    audio_dur = _wav_dur(audio_path)
    duration  = audio_dur + 0.8
    base_arr  = _make_base(T)

    # Pre-render the visual for bullet scenes (done once, not per frame)
    visual = None
    if scene.kind in ("bullets",):
        visual = _get_visual(scene, T)

    builder = BUILDERS.get(scene.kind, _frame_generic)

    def make_frame(t):
        try:
            img  = builder(t, scene, T, base_arr, visual, duration)
            draw = ImageDraw.Draw(img)
            # Progress bar on every frame
            pw = W - 160
            pf = int(pw * min(t / max(duration, 0.1), 1.0))
            draw.rounded_rectangle([80, H - 28, 80 + pw, H - 20], 4,
                                   fill=T.get("line", (30, 48, 80)))
            if pf > 0:
                draw.rounded_rectangle([80, H - 28, 80 + pf, H - 20], 4,
                                       fill=T.get("accent", (56, 189, 248)))
            # Takeaway strip slides up in last 1.5s
            if scene.takeaway and t > duration - 1.5:
                _slides._takeaway_strip(draw, scene.takeaway, T)
            return np.array(img, dtype=np.uint8)
        except Exception:
            return base_arr.copy()

    try:
        clip  = VideoClip(make_frame, duration=duration)
        audio = AudioFileClip(audio_path)
        clip  = clip.with_audio(audio)
        clip.write_videofile(
            out_path, fps=FPS,
            codec="libx264", audio_codec="aac",
            preset="veryfast", ffmpeg_params=["-pix_fmt", "yuv420p"],
            logger=None,
        )
        clip.close()
        audio.close()
    except Exception as e:
        print(f"[animator] MoviePy failed ({e}), falling back to static clip.")
        return _video.make_clip(slide_image_path, audio_path, out_path)

    return duration


def concat_with_transitions(clip_paths, out_path, transition_duration=0.4):
    """Concatenate clips with crossfades. Falls back to FFmpeg concat."""
    if not ANIMATION_AVAILABLE or len(clip_paths) < 2:
        return _video.concat(clip_paths, out_path)
    try:
        from moviepy import VideoFileClip, concatenate_videoclips
        clips = [VideoFileClip(p) for p in clip_paths]
        final = concatenate_videoclips(clips, method="compose")
        final.write_videofile(
            out_path, fps=FPS,
            codec="libx264", audio_codec="aac",
            preset="veryfast", ffmpeg_params=["-pix_fmt", "yuv420p"],
            logger=None,
        )
        for c in clips:
            c.close()
        final.close()
    except Exception as e:
        print(f"[animator] concat fallback: {e}")
        _video.concat(clip_paths, out_path)
    return out_path
