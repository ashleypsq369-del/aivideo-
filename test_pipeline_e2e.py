"""Full end-to-end pipeline test with edge_tts voice and draft quality."""
import os, json
os.environ["MOCK_LLM"] = "1"

from aivideo.pipeline import build_video

lesson = open("samples/lesson.txt").read()
result = build_video(
    lesson,
    outdir="output/test_e2e_full",
    topic="Malaria Prevention",
    engine="edge_tts",
    voice="en-US-AriaNeural",
    quality="draft",
    style="auto",
    fmt="deep_dive",
    progress=print,
)

print("\n=== RESULTS ===")
print(f"total_seconds : {result['total_seconds']}")
print(f"scenes        : {len(result['timeline'])}")
print(f"format        : {result['format']}")
print(f"style         : {result['style']}")
print(f"quality       : {result['quality']}")
print(f"QA score      : {result['qa']['overall_score']:.0%}  ({result['qa']['passed']}/{result['qa']['total']} checks passed)")
print(f"QA ready      : {result['qa']['ready']}")

print("\nQA checks:")
for c in result["qa"]["checks"]:
    icon = "OK" if c["pass"] else "FAIL"
    print(f"  [{icon}] {c['check']:35} {str(c['value']):10} (threshold: {c['threshold']})"
          + (f"  -- {c['note']}" if c["note"] else ""))

# Assertions
assert result["total_seconds"] > 10, "Video too short"
assert result["qa"]["passed"] >= result["qa"]["total"] * 0.60, "QA score too low"
assert os.path.exists("output/test_e2e_full/lesson.mp4"), "lesson.mp4 missing"
assert os.path.exists("output/test_e2e_full/07_qa_report.json"), "qa_report missing"
assert os.path.exists("output/test_e2e_full/01_analysis.json"), "analysis missing"
assert os.path.exists("output/test_e2e_full/02_creative.json"), "creative missing"
assert os.path.exists("output/test_e2e_full/03_storyboard.json"), "storyboard missing"

print("\nAll end-to-end assertions passed.")
