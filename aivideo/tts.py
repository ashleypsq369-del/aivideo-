"""Narration engines. Each returns the path of a 24 kHz mono WAV.

  * mock   - no model needed; quiet clicks per word, duration ~ real speech. For testing the pipeline.
  * kokoro - open-source Kokoro-82M (pip install kokoro soundfile). Check its license before commercial use.
  * espeak - uses the espeak-ng command if installed (robotic but real speech).
"""
import math
import os
import shutil
import struct
import subprocess
import wave

RATE = 24000
WORDS_PER_SEC = 2.6


def duration_for(text):
    return max(1.5, len(text.split()) / WORDS_PER_SEC)


def synth_mock(text, path, **_):
    n = int(duration_for(text) * RATE)
    words = max(1, len(text.split()))
    beat = n // words
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


def synth_espeak(text, path, voice="en-us", **_):
    exe = shutil.which("espeak-ng") or shutil.which("espeak")
    if not exe:
        raise RuntimeError("espeak-ng not installed")
    tmp = path + ".raw.wav"
    subprocess.run([exe, "-v", voice, "-w", tmp, text], check=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", tmp, "-ar", str(RATE), "-ac", "1", path], check=True)
    os.remove(tmp)
    return path


def synth_kokoro(text, path, voice="af_heart", **_):
    import numpy as np
    import soundfile as sf
    from kokoro import KPipeline
    pipe = KPipeline(lang_code="a")
    chunks = [audio for _, _, audio in pipe(text, voice=voice)]
    sf.write(path, np.concatenate(chunks), RATE)
    return path


ENGINES = {"mock": synth_mock, "espeak": synth_espeak, "kokoro": synth_kokoro}


def synthesize(text, path, engine="mock", voice=None):
    if engine not in ENGINES:
        raise ValueError(f"Unknown TTS engine '{engine}'. Choose from {list(ENGINES)}")
    kwargs = {"voice": voice} if voice else {}
    return ENGINES[engine](text, path, **kwargs)
