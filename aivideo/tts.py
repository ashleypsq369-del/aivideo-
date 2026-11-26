"""Narration engines.

Priority / fallback chain (auto mode):
  1. edge_tts  — Microsoft neural voices, human-sounding, free, no model download
                 pip install edge-tts   (already installed)
  2. kokoro    — offline Kokoro-82M, Apache 2.0
                 pip install kokoro soundfile misaki[en]
  3. espeak    — robotic fallback, always available on Linux
  4. mock      — silent click-track, TEST ONLY — never use in production

Edge TTS voices (best quality, recommended):
  en-US-AriaNeural       — warm American female  (default)
  en-US-GuyNeural        — natural American male
  en-US-JennyNeural      — friendly American female
  en-GB-SoniaNeural      — British female
  en-GB-RyanNeural       — British male
  en-AU-NatashaNeural    — Australian female
  en-IN-NeerjaNeural     — Indian female

Set AIVIDEO_TTS_ENGINE=edge_tts or kokoro or espeak in .env
Set AIVIDEO_TTS_VOICE=en-US-GuyNeural (etc.) to change voice
"""
import asyncio
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
    """Silent click-track. For pipeline smoke-testing ONLY."""
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


# ── edge_tts (Microsoft Neural — primary production engine) ──────────────────

def synth_edge_tts(text: str, path: str,
                   voice: str = "en-US-AriaNeural", **_) -> str:
    """Human-quality speech via Microsoft Edge TTS (free, no model download).

    Requires: pip install edge-tts
    Voices:   en-US-AriaNeural, en-US-GuyNeural, en-GB-SoniaNeural, etc.
    Output:   24 kHz mono WAV (resampled from edge-tts MP3 via FFmpeg)
    """
    try:
        import edge_tts as _edge
    except ImportError:
        raise RuntimeError("edge-tts not installed. Run: pip install edge-tts")

    from .video import _find
    ffmpeg = _find("ffmpeg")

    # edge-tts writes an MP3; we convert to 24 kHz mono WAV
    tmp_mp3 = path + ".tmp.mp3"

    async def _speak():
        comm = _edge.Communicate(text, voice)
        await comm.save(tmp_mp3)

    # Run async in a fresh event loop (safe even inside a thread)
    try:
        loop = asyncio.new_event_loop()
        loop.run_until_complete(_speak())
    finally:
        loop.close()

    # Convert MP3 → 24 kHz mono WAV
    subprocess.run(
        [ffmpeg, "-y", "-loglevel", "error",
         "-i", tmp_mp3,
         "-ar", str(RATE), "-ac", "1",
         "-acodec", "pcm_s16le", path],
        check=True
    )
    os.remove(tmp_mp3)
    return path


# ── kokoro (offline Kokoro-82M) ───────────────────────────────────────────────

_KOKORO_PIPE = None


def synth_kokoro(text: str, path: str, voice: str = "af_heart", **_) -> str:
    """Natural offline speech via Kokoro-82M (Apache 2.0).
    Requires: pip install kokoro soundfile misaki[en]
    """
    global _KOKORO_PIPE
    try:
        import numpy as np
        import soundfile as sf
        from kokoro import KPipeline
    except ImportError as exc:
        raise RuntimeError(
            f"Kokoro deps missing: {exc}. Run: pip install kokoro soundfile misaki[en]"
        ) from exc

    if _KOKORO_PIPE is None:
        lang = "b" if voice.startswith("b") else "a"
        _KOKORO_PIPE = KPipeline(lang_code=lang)

    chunks = [audio for _, _, audio in _KOKORO_PIPE(text, voice=voice)]
    if not chunks:
        raise RuntimeError("Kokoro returned no audio chunks.")

    import soundfile as sf
    import numpy as np
    sf.write(path, np.concatenate(chunks), RATE)
    return path


# ── espeak (robotic fallback) ─────────────────────────────────────────────────

def synth_espeak(text: str, path: str, voice: str = "en-us", **_) -> str:
    from .video import _find
    exe = shutil.which("espeak-ng") or shutil.which("espeak")
    if not exe:
        raise RuntimeError(
            "espeak-ng not found. "
            "Windows: winget install espeak-ng  |  Linux: apt install espeak-ng"
        )
    ffmpeg = _find("ffmpeg")
    tmp = path + ".raw.wav"
    subprocess.run([exe, "-v", voice, "-w", tmp, text], check=True)
    subprocess.run([ffmpeg, "-y", "-loglevel", "error",
                    "-i", tmp, "-ar", str(RATE), "-ac", "1", path], check=True)
    os.remove(tmp)
    return path


# ── auto-detect ───────────────────────────────────────────────────────────────

def _detect_engine() -> str:
    """Return best available engine — never imports the package itself."""
    env = os.environ.get("AIVIDEO_TTS_ENGINE", "").lower()
    if env in ("edge_tts", "kokoro", "espeak", "mock"):
        return env

    import importlib.metadata

    # 1. edge-tts (best quality, no model download)
    try:
        importlib.metadata.version("edge-tts")
        return "edge_tts"
    except Exception:
        pass

    # 2. kokoro (offline, needs model weights on first run)
    try:
        importlib.metadata.version("kokoro")
        return "kokoro"
    except Exception:
        pass

    # 3. espeak (robotic but always works)
    if shutil.which("espeak-ng") or shutil.which("espeak"):
        return "espeak"

    return "mock"


# ── dispatch ──────────────────────────────────────────────────────────────────

ENGINES = {
    "mock":     synth_mock,
    "espeak":   synth_espeak,
    "kokoro":   synth_kokoro,
    "edge_tts": synth_edge_tts,
}

DEFAULT_VOICES = {
    "edge_tts": os.environ.get("AIVIDEO_TTS_VOICE", "en-US-AriaNeural"),
    "kokoro":   os.environ.get("AIVIDEO_TTS_VOICE", "af_heart"),
    "espeak":   "en-us",
    "mock":     None,
}


def synthesize(text: str, path: str,
               engine: str = "auto",
               voice: str | None = None) -> str:
    """Synthesise text → 24 kHz mono WAV.

    engine: "edge_tts" | "kokoro" | "espeak" | "mock" | "auto"
    voice:  engine-specific voice name; None = use default
    """
    if engine in ("", None, "auto"):
        engine = _detect_engine()

    if engine not in ENGINES:
        raise ValueError(f"Unknown engine '{engine}'. Choose from {list(ENGINES)}")

    if voice is None:
        voice = DEFAULT_VOICES.get(engine)

    kwargs = {"voice": voice} if voice else {}

    try:
        result = ENGINES[engine](text, path, **kwargs)
        print(f"[tts] {engine} ({voice}) → {os.path.basename(path)}")
        return result
    except Exception as exc:
        # Fallback chain
        if engine == "edge_tts":
            print(f"[tts] edge_tts failed ({exc}), trying kokoro...")
            try:
                return synthesize(text, path, engine="kokoro", voice=None)
            except Exception as exc2:
                print(f"[tts] kokoro failed ({exc2}), trying espeak...")
                try:
                    return synthesize(text, path, engine="espeak", voice=None)
                except Exception as exc3:
                    print(f"[tts] espeak failed ({exc3}), using mock (silent).")
                    return synth_mock(text, path)
        elif engine == "kokoro":
            print(f"[tts] kokoro failed ({exc}), trying espeak...")
            try:
                return synthesize(text, path, engine="espeak", voice=None)
            except Exception as exc2:
                print(f"[tts] espeak failed ({exc2}), using mock.")
                return synth_mock(text, path)
        elif engine == "espeak":
            print(f"[tts] espeak failed ({exc}), using mock.")
            return synth_mock(text, path)
        raise
