"""Assemble slide images + audio into an MP4 with FFmpeg.
Each slide is shown for exactly the length of its narration (plus a small pad)."""
import os
import shutil
import subprocess

PAD = 0.6


def _find(name):
    """Locate ffmpeg/ffprobe. On Windows also searches the Machine and User PATH
    from the registry, so the server doesn't need to have been launched after
    FFmpeg was installed."""
    # 1. Normal PATH inherited by this process
    found = shutil.which(name)
    if found:
        return found

    if os.name == "nt":
        import winreg

        # 2. Machine PATH (HKLM) — correct key for system-wide entries
        reg_paths = []
        try:
            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment",
            )
            reg_paths.append(winreg.QueryValueEx(key, "PATH")[0])
        except OSError:
            pass

        # 3. User PATH (HKCU) — correct key for per-user entries (winget installs here)
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Environment",
            )
            reg_paths.append(winreg.QueryValueEx(key, "PATH")[0])
        except OSError:
            pass

        extended = os.pathsep.join(reg_paths)
        found = shutil.which(name, path=extended)
        if found:
            return found

    raise RuntimeError(
        f"'{name}' not found on PATH. Install FFmpeg and ensure it is on your system PATH."
    )


FFMPEG = None
FFPROBE = None


def _ffmpeg():
    global FFMPEG
    if FFMPEG is None:
        FFMPEG = _find("ffmpeg")
    return FFMPEG


def _ffprobe():
    global FFPROBE
    if FFPROBE is None:
        FFPROBE = _find("ffprobe")
    return FFPROBE


def audio_seconds(path):
    out = subprocess.run([_ffprobe(), "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                         capture_output=True, text=True, check=True).stdout.strip()
    return float(out)


def _run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError("ffmpeg failed:\n" + r.stderr[-1500:])


def make_clip(image, audio, out):
    dur = audio_seconds(audio) + PAD
    _run([_ffmpeg(), "-y", "-loglevel", "error", "-loop", "1", "-framerate", "24", "-i", image, "-i", audio,
          "-t", f"{dur:.2f}", "-af", f"apad=pad_dur={PAD}", "-c:v", "libx264", "-preset", "veryfast",
          "-pix_fmt", "yuv420p", "-vf", "scale=1920:1080", "-c:a", "aac", "-ar", "24000", "-ac", "1",
          "-shortest", out])
    return dur


def concat(clips, out):
    listfile = out + ".txt"
    with open(listfile, "w") as f:
        for c in clips:
            f.write(f"file '{os.path.abspath(c)}'\n")
    _run([_ffmpeg(), "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", listfile, "-c", "copy", out])
    os.remove(listfile)
    return out
