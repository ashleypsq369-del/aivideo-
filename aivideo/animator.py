"""Animated clip renderer using MoviePy + NumPy + Pillow.
Falls back to static video.make_clip() if MoviePy unavailable or quality==draft.
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
from . import video as _video

W, H, FPS = 1920, 1080, 24
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
    ov      = np.array(overlay_pil.crop((ox0, oy0, ox1, oy1)).convert("RGB"), dtype=np.float32)
    base_r  = base[by0:by1, bx0:bx1].astype(np.float32)
    result  = base.copy()
    result[by0:by1, bx0:bx1] = (base_r * (1 - alpha) + ov * alpha).astype(np.uint8)
    return result


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


# ── per-kind frame builders ───────────────────────────────────────────────────

def _frame_title(t, scene, T, base, graphic, dur):
    img  = _np_to_pil(base.copy())
    draw = ImageDraw.Draw(img)
    ac   = T.get("accent",  (56, 189, 248))
    ac2  = T.get("accent2", (251, 191, 36))
    txt  = T.get("text",    (241, 245, 249))
    mu   = T.get("muted",   (148, 163, 184))

    r = int(95 * _ease_out(_prog(t, 0.2, 0.4)))
    if r > 5:
        _slides._badge(draw, scene.icon, W//2, 290, r, T)

    p  = _ease_out(_prog(t, 0.3, 0.6))
    xo = int((1 - p) * -300)
    if p > 0:
        f     = _font(96, bold=True)
        lines = _wrap(draw, scene.title, f, W - 320)
        y     = 460
        for ln in lines[:3]:
            draw.text((W//2 + xo, y), ln, font=f, fill=txt, anchor="mt")
            y += 110

    sa = _prog(t, 1.0, 0.5)
    if sa > 0 and scene.narration:
        f  = _font(40)
        y  = 700
        sc = tuple(int(c * sa) for c in mu)
        for ln in _wrap(draw, scene.narration[:130], f, W - 400)[:2]:
            draw.text((W//2, y), ln, font=f, fill=sc, anchor="mt")
            y += 54

    import random as _r
    rng = _r.Random(42)
    for _ in range(6):
        px  = int(rng.uniform(W//2 - 200, W//2 + 200))
        py  = int(rng.uniform(200, 380))
        pr  = int(rng.randint(4, 10) * _ease_out(_prog(t, rng.uniform(0, 0.5), 0.3)))
        if pr > 0:
            draw.ellipse([px-pr, py-pr, px+pr, py+pr], fill=ac2)

    draw.rectangle([0, H-12, W, H], fill=ac)
    return img


def _frame_bullets(t, scene, T, base, graphic, dur):
    img  = _np_to_pil(base.copy())
    draw = ImageDraw.Draw(img)
    from .slides import ICON_COLOR_KEY
    color = T.get(ICON_COLOR_KEY.get(scene.icon, "accent"), T.get("accent", (56, 189, 248)))
    txt   = T.get("text", (241, 245, 249))
    card  = T.get("card", (20, 32, 55))

    bh = int(H * _ease_out(_prog(t, 0, 0.3)))
    draw.rectangle([0, 0, 14, bh], fill=color)

    r = int(60 * _bounce(_prog(t, 0.2, 0.3)))
    if r > 4:
        _slides._badge(draw, scene.icon, 130, 130, r, T)

    p  = _ease_out(_prog(t, 0.3, 0.4))
    xo = int((1 - p) * -250)
    ft = _font(72, bold=True)
    tl = _wrap(draw, scene.title, ft, W - 300)
    ty = 90
    for ln in tl[:2]:
        draw.text((230 + xo, ty), ln, font=ft, fill=txt)
        ty += 84
    if p > 0.5:
        uw = min(620, int(draw.textlength(scene.title, font=ft) * p))
        draw.rectangle([230, ty+4, 230+uw, ty+10], fill=color)

    fb  = _font(50)
    fn2 = _font(30, bold=True)
    y0  = ty + 50
    for i, b in enumerate(scene.bullets[:4]):
        if y0 > H - 220:
            break
        blines = _wrap(draw, b, fb, W - 310)
        ch = len(blines[:2]) * 60 + 24
        p2 = _ease_out(_prog(t, 0.6 + i * 0.45, 0.35))
        yo = int((1 - p2) * 50)
        if p2 < 0.01:
            y0 += ch + 22
            continue
        ci   = Image.new("RGB", (W - 220, ch), card)
        cdraw = ImageDraw.Draw(ci)
        cdraw.rounded_rectangle([0, 0, W-222, ch], 10, fill=card)
        cdraw.ellipse([0-26, ch//2-26, 0+26, ch//2+26], fill=color)
        cdraw.text((0, ch//2), str(i+1), font=fn2, fill=(10, 18, 35), anchor="mm")
        by2 = 12
        for ln in blines[:2]:
            cdraw.text((40, by2), ln, font=fb, fill=txt)
            by2 += 60
        arr  = _pil_to_np(img)
        arr  = _blend(arr, ci, 140, y0 + yo, p2)
        img  = _np_to_pil(arr)
        draw = ImageDraw.Draw(img)
        y0  += ch + 22

    if graphic is not None:
        ga = _ease_in_out(_prog(t, 1.0, 0.5))
        if ga > 0.01:
            arr  = _pil_to_np(img)
            arr  = _blend(arr, _np_to_pil(graphic), 1020, 180, ga)
            img  = _np_to_pil(arr)
    return img


def _frame_quiz(t, scene, T, base, graphic, dur):
    img  = _np_to_pil(base.copy())
    draw = ImageDraw.Draw(img)
    ac2 = T.get("accent2", (251, 191, 36))
    txt = T.get("text",    (241, 245, 249))
    ac  = T.get("accent",  (56, 189, 248))
    gr  = T.get("green",   (74, 222, 128))
    rd  = T.get("red",     (248, 113, 113))
    pu  = T.get("purple",  (167, 139, 250))

    draw.rectangle([0, 0, 14, H], fill=ac2)
    _slides._badge(draw, "check", 130, 120, 55, T)
    draw.text((220, 90), "KNOWLEDGE CHECK", font=_font(44, bold=True), fill=ac2)

    p  = _ease_out(_prog(t, 0.3, 0.5))
    yo = int((1 - p) * -80)
    if p > 0:
        fq = _font(54, bold=True)
        y  = 200 + yo
        for ln in _wrap(draw, scene.question, fq, W - 220)[:3]:
            draw.text((110, y), ln, font=fq, fill=txt)
            y += 70

    colors = [ac, gr, rd, pu]
    y2 = 440
    for i, opt in enumerate(scene.options[:4]):
        p2  = _ease_out(_prog(t, 0.8 + i * 0.4, 0.35))
        xo  = int((1 - p2) * 400)
        if p2 < 0.01:
            y2 += 125
            continue
        correct = i == scene.answer_index
        oc  = colors[i % len(colors)]
        bg  = tuple(int(c * 0.15) for c in oc) if T.get("dark") \
              else tuple(min(255, int(c * 0.12) + 235) for c in oc)
        draw.rounded_rectangle([110+xo, y2, W-110+xo, y2+100], 16,
                                fill=bg, outline=oc if correct else T.get("line", (30, 48, 80)),
                                width=3 if correct else 1)
        draw.ellipse([126+xo, y2+22, 170+xo, y2+66], fill=oc)
        draw.text((148+xo, y2+44), "ABCD"[i], font=_font(30, bold=True),
                  fill=(255, 255, 255), anchor="mm")
        draw.text((195+xo, y2+50), opt[:72], font=_font(44), fill=txt, anchor="lm")
        y2 += 125
    return img


def _frame_summary(t, scene, T, base, graphic, dur):
    img  = _np_to_pil(base.copy())
    draw = ImageDraw.Draw(img)
    gr  = T.get("green",   (74, 222, 128))
    ac2 = T.get("accent2", (251, 191, 36))
    txt = T.get("text",    (241, 245, 249))

    draw.rectangle([0, 0, 14, H], fill=gr)
    _slides._badge(draw, "check", 130, 120, 60, T)
    draw.text((220, 88), scene.title, font=_font(72, bold=True), fill=gr)
    draw.rectangle([220, 170, 700, 176], fill=ac2)

    f = _font(48)
    y = 220
    for i, b in enumerate(scene.bullets[:5]):
        if y > H - 250:
            break
        p  = _ease_out(_prog(t, 0.3 + i * 0.3, 0.4))
        yo = int((1 - p) * 60)
        if p < 0.01:
            y += 74
            continue
        for ln in _wrap(draw, b, f, W - 280)[:2]:
            draw.text((220, y + yo), ln, font=f, fill=txt)
            y += 58
        y += 16

    if _prog(t, dur - 1.5, 0.5) > 0.01:
        band = (15, 35, 15) if T.get("dark") else (220, 255, 220)
        draw.rectangle([0, H-130, W, H-50], fill=band)
        draw.text((W//2, H-90), "Lesson complete! Well done.",
                  font=_font(38, bold=True), fill=gr, anchor="mm")

    if t > dur - 2.0:
        import random as _r
        rng  = _r.Random(99)
        cols = [gr, ac2, T.get("accent", (56, 189, 248)), T.get("purple", (167, 139, 250))]
        for _ in range(20):
            cx2 = int(rng.uniform(0, W))
            spd = rng.uniform(80, 200)
            cy2 = int((t - (dur - 2.0)) * spd * 100 % H)
            cr  = rng.randint(5, 12)
            draw.rectangle([cx2, cy2, cx2+cr*2, cy2+cr],
                           fill=cols[rng.randint(0, len(cols)-1)])
    return img


def _frame_flashcard(t, scene, T, base, graphic, dur):
    img  = _np_to_pil(base.copy())
    draw = ImageDraw.Draw(img)
    pu  = T.get("purple", (167, 139, 250))
    txt = T.get("text",   (241, 245, 249))
    ac  = T.get("accent", (56, 189, 248))

    draw.rectangle([0, 0, 14, H], fill=pu)
    _slides._badge(draw, "book", 130, 110, 50, T)
    draw.text((210, 85), "FLASHCARDS", font=_font(50, bold=True), fill=txt)

    cards = scene.flashcards[:4]
    if not cards:
        return img
    cols = 2
    cw   = (W - 160) // cols
    ch   = min((H - 300) // max(math.ceil(len(cards) / cols), 1), 240)
    for i, card in enumerate(cards):
        col2, row = i % cols, i // cols
        x0, y0   = 80 + col2 * cw, 220 + row * ch
        p        = _ease_out(_prog(t, 0.3 + i * 0.6, 0.4))
        fp       = p * 2
        scale_x  = 1 - fp if fp < 1 else fp - 1
        is_front = fp < 1
        cx2      = x0 + cw // 2
        hw       = int((cw - 20) * scale_x / 2)
        if hw < 2:
            continue
        draw.rounded_rectangle([cx2-hw, y0, cx2+hw, y0+ch-20], 12,
                                fill=pu if is_front else ac)
        if hw > 20:
            label = card["front"][:30] if is_front else card["back"][:30]
            draw.text((cx2, y0 + ch//2 - 10), label, font=_font(26),
                      fill=(10, 18, 35), anchor="mm")
    return img


def _frame_generic(t, scene, T, base, graphic, dur):
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

    graphic = None
    if scene.kind == "bullets":
        try:
            from .visual_engine import make_graphic
            graphic = _pil_to_np(make_graphic(scene, T, size=(860, 500)))
        except Exception:
            pass

    builder = BUILDERS.get(scene.kind, _frame_generic)

    def make_frame(t):
        try:
            img  = builder(t, scene, T, base_arr, graphic, duration)
            draw = ImageDraw.Draw(img)
            pw   = W - 160
            pf   = int(pw * min(t / max(duration, 0.1), 1.0))
            draw.rounded_rectangle([80, H-28, 80+pw, H-20], 4,
                                   fill=T.get("line", (30, 48, 80)))
            if pf > 0:
                draw.rounded_rectangle([80, H-28, 80+pf, H-20], 4,
                                       fill=T.get("accent", (56, 189, 248)))
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
            out_path, fps=FPS, codec="libx264", audio_codec="aac",
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
            out_path, fps=FPS, codec="libx264", audio_codec="aac",
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
