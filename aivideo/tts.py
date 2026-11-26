"""Narration engine.

Production engine: kokoro  (natural, human-sounding — pip install kokoro soundfile)
Fallback engine:   espeak  (robotic but always available)
Test engine:       mock    (silent tones — NEVER use in production video)

The engine is chosen by:
  1. The `engine` argument passed to synthesize()
  2. The AIVIDEO_TTS_ENGINE environment variable
  3. Auto-detect: try kokoro, fall back to espeak, fall back to mock

Voices (Kokoro):
  af_heart   – warm, friendly American female  (default)
  af_sky     – brighter American female
  am_michael – authoritative American male
  am_adam    – calm American male
  bf_emma    – British female
  bm_george  – British male
"""
import math
import os
import shutil
import struct
import subprocess
import wave

RATE = 24_000
WORDS_PER_SEC = 2.6


def duration_for(text: str) -> float:
    return max(1.5, len(text.split()) / WORDS_PER_SEC)


# ── mock (test only) ──────────────────────────────────────────────────────────

def synth_mock(text: str, path: str, **_) -> str:
    """Silent click-track. For pipeline smoke-testing only."""
    n     = int(duration_for(text) * RATE)
    words = max(1, len(text.split()))
    beat  = n // words
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        frames = bytearray()
        for i in range(n):
            pos = i % beat
            amp = 3000 * math.exp(-pos / (RATE * 0.03)) if pos < RATE * 0.15 else 0
            frames += struct.pack("<h", int(amp * math.sin(2 * math.pi * 220 * i / RATE)))
        w.writeframes(bytes(frames))
    return path


# ── espeak (robotic fallback) ─────────────────────────────────────────────────

def synth_espeak(text: str, path: str, voice: str = "en-us", **_) -> str:
    from .video import _find
    exe = shutil.which("espeak-ng") or shutil.which("espeak")
    if not exe:
        raise RuntimeError(
            "espeak-ng not found. Install it: "
            "Windows: choco install espeak-ng  |  Linux: apt install espeak-ng"
        )
    tmp = path + ".raw.wav"
    subprocess.run([exe, "-v", voice, "-w", tmp, text], check=True)
    ffmpeg = _find("ffmpeg")
    subprocess.run([ffmpeg, "-y", "-loglevel", "error",
                    "-i", tmp, "-ar", str(RATE), "-ac", "1", path], check=True)
    os.remove(tmp)
    return path


# ── Kokoro (natural, production) ──────────────────────────────────────────────

_KOKORO_PIPE = None   # module-level cache so the model loads only once


def synth_kokoro(text: str, path: str, voice: str = "af_heart", **_) -> str:
    """Natural speech via Kokoro-82M (Apache 2.0).

    Voices: af_heart, af_sky, am_michael, am_adam, bf_emma, bm_george
    Requires: pip install kokoro soundfile
    """
    global _KOKORO_PIPE
    try:
        import numpy as np
        import soundfile as sf
        from kokoro import KPipeline
    except ImportError as exc:
        raise RuntimeError(
            "Kokoro not installed. Run: pip install kokoro soundfile\n"
            f"Original error: {exc}"
        ) from exc

    if _KOKORO_PIPE is None:
        # lang_code: 'a' = American English, 'b' = British English
        lang = "b" if voice.startswith("b") else "a"
        _KOKORO_PIPE = KPipeline(lang_code=lang)

    # Re-create pipeline if voice language changed
    lang = "b" if voice.startswith("b") else "a"
    pipe = _KOKORO_PIPE

    chunks = []
    for _, _, audio in pipe(text, voice=voice):
        chunks.append(audio)

    if not chunks:
        raise RuntimeError("Kokoro returned no audio chunks.")

    audio_data = np.concatenate(chunks)
    sf.write(path, audio_data, RATE)
    return path


# ── auto-detect ───────────────────────────────────────────────────────────────

def _detect_engine() -> str:
    """Return the best available engine.
    Uses pip metadata to check for kokoro — never imports it (avoids model-download hang)."""
    env = os.environ.get("AIVIDEO_TTS_ENGINE", "").lower()
    if env in ("kokoro", "espeak", "mock"):
        return env
    # Check kokoro via pip metadata only (no import, no timeout risk)
    try:
        import importlib.metadata
        importlib.metadata.version("kokoro")
        return "kokoro"   # installed — use it
    except Exception:
        pass
    if shutil.which("espeak-ng") or shutil.which("espeak"):
        return "espeak"
    return "mock"


ENGINES = {
    "mock":   synth_mock,
    "espeak": synth_espeak,
    "kokoro": synth_kokoro,
}

DEFAULT_VOICES = {
    "kokoro": os.environ.get("AIVIDEO_TTS_VOICE", "af_heart"),
    "espeak": "en-us",
    "mock":   None,
}


def synthesize(text: str, path: str, engine: str = "auto",
               voice: str | None = None) -> str:
    """Synthesise `text` to a 24 kHz mono WAV at `path`.

    engine:  "kokoro" | "espeak" | "mock" | "auto"
             "auto" picks the best available engine.
    voice:   engine-specific voice string; None = use default.
    Returns: `path`
    """
    if engine == "auto":
        engine = _detect_engine()

    if engine not in ENGINES:
        raise ValueError(
            f"Unknown TTS engine '{engine}'. Choose from {list(ENGINES)}"
        )

    if voice is None:
        voice = DEFAULT_VOICES.get(engine)

    kwargs = {"voice": voice} if voice else {}

    try:
        return ENGINES[engine](text, path, **kwargs)
    except Exception as exc:
        # Fallback chain: kokoro -> espeak -> mock
        if engine == "kokoro":
            print(f"[tts] Kokoro failed ({exc}), trying espeak...")
            try:
                return synth_espeak(text, path)
            except Exception as exc2:
                print(f"[tts] eSpeak failed ({exc2}), using mock.")
                return synth_mock(text, path)
        elif engine == "espeak":
            print(f"[tts] eSpeak failed ({exc}), using mock.")
            return synth_mock(text, path)
        raise
