"""Test caption generation with real audio files."""
import os, json
from aivideo.captions import generate_captions, get_word_timestamps, write_srt, write_vtt

os.makedirs("output/test_captions", exist_ok=True)

# Build a mock timeline pointing at the existing test audio
timeline = [
    {"scene": 0, "kind": "title",   "start": 0.0,  "duration": 6.8,
     "narration": "Your body has an incredible defence system. Today we explore how it works.",
     "title": "The Human Immune System"},
    {"scene": 1, "kind": "bullets", "start": 6.8,  "duration": 12.4,
     "narration": "Your immune system has two branches. The innate system reacts instantly to any threat. The adaptive system learns your specific enemy and remembers it forever.",
     "title": "Two Branches of Immunity"},
    {"scene": 2, "kind": "summary", "start": 19.2, "duration": 6.4,
     "narration": "To summarise: your immune system combines speed and intelligence to keep you safe.",
     "title": "What You Learned"},
]

# Copy audio files to test_captions dir
import shutil
for i in range(3):
    src = f"output/test_anim/audio/a_{i:02d}.wav"
    dst = f"output/test_captions/a_{i:02d}.wav"
    if os.path.exists(src):
        shutil.copy(src, dst)

result = generate_captions(timeline, "output/test_captions", "output/test_captions",
                           use_whisper=False)

print(f"Lines:    {result['line_count']}")
print(f"Words:    {result['word_count']}")
print()

# Show SRT preview
with open(result["srt_path"]) as f:
    content = f.read()
    print("=== captions.srt (first 600 chars) ===")
    print(content[:600])

# Assertions
assert result["line_count"] > 0,  "Expected caption lines"
assert result["word_count"] > 0,  "Expected word timestamps"
assert os.path.exists(result["srt_path"]), "SRT file missing"
assert os.path.exists(result["vtt_path"]), "VTT file missing"
assert os.path.exists(result["words_path"]), "words.json missing"

# Check words.json structure
words = json.load(open(result["words_path"]))
assert all("word" in w and "start" in w and "end" in w for w in words[:5])
assert words[0]["start"] >= 0.0
# Second scene words should start after first scene ends
second_scene_words = [w for w in words if w["start"] >= 6.8]
assert len(second_scene_words) > 0, "Second scene words should start at offset 6.8s+"

print(f"\nSample words: {[w['word'] for w in words[:8]]}")
print(f"Word timing check: word[0].start={words[0]['start']:.2f}s, "
      f"second_scene[0].start={second_scene_words[0]['start']:.2f}s")
print("\nAll caption tests passed.")
