"""Final integration test — full pipeline with captions, captions download, DB index."""
import os, json
os.environ["MOCK_LLM"] = "1"

from aivideo.pipeline import build_video

lesson = """
The water cycle describes how water moves continuously through Earth's environment.
Water evaporates from oceans and lakes when heat from the sun turns liquid water into water vapour.
This water vapour rises into the atmosphere, cools, and condenses into clouds through a process called condensation.
When enough water droplets collect in clouds, they fall back to Earth as precipitation — rain, snow, sleet or hail.
Water that falls on land either flows into rivers and streams as runoff, soaks into the ground as groundwater, or is taken up by plants through their roots.
Plants release water vapour back into the air through their leaves in a process called transpiration.
The entire cycle then repeats continuously, distributing fresh water across the planet.
Understanding the water cycle helps scientists predict droughts, floods, and climate change effects.
Human activities such as deforestation reduce transpiration and alter local rainfall patterns significantly.
Conservation of forests and wetlands helps maintain the natural balance of the water cycle.
"""

result = build_video(
    lesson.strip(),
    outdir="output/test_final",
    topic="The Water Cycle",
    engine="edge_tts",
    voice="en-US-JennyNeural",
    quality="draft",
    style="auto",
    fmt="deep_dive",
    length="default",
    progress=print,
)

print("\n" + "="*55)
print("FINAL TEST RESULTS")
print("="*55)
sc = result["timeline"]
print(f"Duration  : {result['total_seconds']:.1f}s")
print(f"Scenes    : {len(sc)}")
print(f"QA score  : {result['qa']['overall_score']:.0%}  ({result['qa']['passed']}/{result['qa']['total']})")

# Check all required outputs
outdir = "output/test_final"
required = ["lesson.mp4","mindmap.png","infographic.png","report.html",
            "captions.srt","captions.vtt","words.json",
            "scene_plan.json","01_analysis.json","02_creative.json",
            "03_storyboard.json","07_qa_report.json"]

print("\nOutput files:")
all_ok = True
for fname in required:
    path = os.path.join(outdir, fname)
    exists = os.path.exists(path)
    size_bytes = os.path.getsize(path) if exists else 0
    size_kb = size_bytes // 1024
    icon = "OK  " if exists and size_bytes > 0 else "FAIL"
    if not (exists and size_bytes > 0): all_ok = False
    print(f"  [{icon}] {fname:30} {size_kb:5} KB  ({size_bytes} bytes)")

# Check captions have content
srt = open(os.path.join(outdir,"captions.srt")).read()
assert len(srt) > 50, "SRT file is empty"
assert "-->" in srt, "SRT has no timestamps"

# Check scene titles are reasonable
plan = result["plan"]
for s in plan["scenes"]:
    title = s["title"]
    assert len(title) > 2, f"Scene title too short: {title!r}"
    assert title not in ("Immune System","Cells Body","Like Innate"), \
        f"Bad auto-generated title: {title!r}"
print("\nScene titles:")
for s in plan["scenes"]:
    print(f"  {s['kind']:10} {s['title'][:55]}")

print(f"\nAll outputs {'OK' if all_ok else 'SOME MISSING'}")
assert all_ok, "Some required output files are missing"
print("\nFINAL TEST PASSED")
