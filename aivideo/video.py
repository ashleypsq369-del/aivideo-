"""Assemble slide images + audio into an MP4 with FFmpeg.
Each slide is shown for exactly the length of its narration (plus a small pad)."""
import os
import subprocess

PAD = 0.6


def audio_seconds(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                         capture_output=True, text=True, check=True).stdout.strip()
    return float(out)


def _run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError("ffmpeg failed:\n" + r.stderr[-1500:])


def make_clip(image, audio, out):
    dur = audio_seconds(audio) + PAD
    _run(["ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-framerate", "24", "-i", image, "-i", audio,
          "-t", f"{dur:.2f}", "-af", f"apad=pad_dur={PAD}", "-c:v", "libx264", "-preset", "veryfast",
          "-pix_fmt", "yuv420p", "-vf", "scale=1920:1080", "-c:a", "aac", "-ar", "24000", "-ac", "1",
          "-shortest", out])
    return dur


def concat(clips, out):
    listfile = out + ".txt"
    with open(listfile, "w") as f:
        for c in clips:
            f.write(f"file '{os.path.abspath(c)}'\n")
    _run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", listfile, "-c", "copy", out])
    os.remove(listfile)
    return out
