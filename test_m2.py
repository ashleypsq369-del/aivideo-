"""M2 creative direction smoke test."""
import os
os.environ["MOCK_LLM"] = "1"

from aivideo.ingest import ingest_sources
from aivideo.understand import analyze
from aivideo.creative.analogies import generate_analogies
from aivideo.creative.visual_chooser import choose_visual, assign_visuals

# M1 chain
chunks   = ingest_sources(["samples/lesson.txt"], "output/test_creative")
analysis = analyze(chunks, "output/test_creative", topic="Malaria Prevention")
creative = generate_analogies(analysis, "output/test_creative")

print("Analogies:", len(creative["analogies"]))
print("Domains:", creative["domains_used_this_video"])
assert len(creative["analogies"]) >= 1, "Expected at least 1 analogy"

# Test visual chooser
test_scenes = [
    {"kind": "title",   "title": "Malaria Prevention",         "bullets": [],                                                "icon": "health"},
    {"kind": "bullets", "title": "How mosquitoes spread",       "bullets": ["Mosquito bites", "Parasite enters blood"],       "icon": "health"},
    {"kind": "bullets", "title": "Steps to prevent malaria",   "bullets": ["Use bed nets", "Take vaccines", "See doctor"],   "icon": "check"},
    {"kind": "bullets", "title": "Infection statistics",        "bullets": ["40 percent of children", "2 million cases"],    "icon": "money"},
    {"kind": "quiz",    "title": "Knowledge Check",             "bullets": [],                                                "icon": "check"},
    {"kind": "summary", "title": "Summary",                     "bullets": ["Nets work", "Vaccines help"],                    "icon": "book"},
]
assigned = assign_visuals(test_scenes, creative["analogies"])

print("\nVisual assignments:")
for s in assigned:
    vt  = s["visual_type"]
    by  = s["visual_spec_hint"].get("_chosen_by", "?")
    print(f"  {s['kind']:10} -> {vt:20} (chosen_by: {by})")

# No two consecutive non-statement/quiz scenes share a visual type
prev = None
ALLOW_REPEAT = {"statement", "quiz"}
for s in assigned:
    vt = s["visual_type"]
    if prev and vt == prev and vt not in ALLOW_REPEAT:
        raise AssertionError(f"Consecutive duplicate visual type: {vt}")
    prev = vt

# Statement visual type assigned to title scenes
title_scene = next(s for s in assigned if s["kind"] == "title")
assert title_scene["visual_type"] == "statement", f"Title should be statement, got {title_scene['visual_type']}"

# Quiz visual type assigned to quiz scenes
quiz_scene = next(s for s in assigned if s["kind"] == "quiz")
assert quiz_scene["visual_type"] == "quiz", f"Quiz should be quiz, got {quiz_scene['visual_type']}"

print("\nAll M2 assertions passed.")
