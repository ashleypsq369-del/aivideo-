"""M3 storyboard smoke test."""
import os, json
os.environ["MOCK_LLM"] = "1"

from aivideo.ingest import ingest_sources
from aivideo.understand import analyze
from aivideo.creative.analogies import generate_analogies
from aivideo.storyboard import build_storyboard
from aivideo.storyboard.planner import ALLOWED_VISUAL_TYPES

# Full M1+M2+M3 chain
chunks    = ingest_sources(["samples/lesson.txt"], "output/test_storyboard")
analysis  = analyze(chunks, "output/test_storyboard", topic="Malaria Prevention")
creative  = generate_analogies(analysis, "output/test_storyboard")
storyboard = build_storyboard(analysis, creative, "output/test_storyboard")

scenes = storyboard["scenes"]
print(f"Scenes: {len(scenes)}")
for s in scenes:
    print(f"  {s['id']} {s['purpose']:14} vt={s['visual_type']:20} ~{s['target_seconds']}s")

# Validation rules
assert len(scenes) >= 3, "Expected at least 3 scenes"

# 1. All visual types allowed
for s in scenes:
    vt = s["visual_type"]
    assert vt in ALLOWED_VISUAL_TYPES, f"Invalid visual_type {vt!r} in {s['id']}"

# 2. No consecutive duplicate non-statement/quiz
ALLOW_REPEAT = {"statement", "quiz"}
prev = None
for s in scenes:
    vt = s["visual_type"]
    if prev and vt == prev and vt not in ALLOW_REPEAT:
        raise AssertionError(f"Consecutive duplicate visual type {vt!r} in {s['id']}")
    prev = vt

# 3. All beats at_phrase exist in narration
for s in scenes:
    for beat in s.get("beats", []):
        phrase = beat.get("at_phrase", "")
        narr   = s.get("narration", "")
        assert phrase.lower() in narr.lower(), (
            f"{s['id']}: beat phrase {phrase!r} not found in narration"
        )

# 4. target_seconds in range
for s in scenes:
    ts = s.get("target_seconds", 25)
    assert 12 <= ts <= 60, f"{s['id']}: target_seconds {ts} out of range"

# 5. on_screen_text max 4 items each <= 12 words
for s in scenes:
    ost = s.get("on_screen_text", [])
    assert len(ost) <= 4, f"{s['id']}: {len(ost)} on_screen_text items > 4"
    for item in ost:
        wc = len(item.split())
        assert wc <= 12, f"{s['id']}: on_screen_text item {wc} words > 12: {item!r}"

# 6. 03_storyboard.json was written
assert os.path.exists("output/test_storyboard/03_storyboard.json"), "03_storyboard.json missing"

print("\nAll M3 assertions passed.")
