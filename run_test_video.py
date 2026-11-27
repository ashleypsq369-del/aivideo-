"""Generate a full test video with rich visuals and check every output."""
import os, json, wave
os.environ["MOCK_LLM"] = "1"   # no API key needed

from aivideo.pipeline import build_video

lesson = open("samples/rich_lesson.txt").read()
print(f"Lesson: {len(lesson.split())} words\n")

result = build_video(
    lesson,
    outdir="output/test_rich_video",
    topic="The Human Immune System",
    engine="edge_tts",
    voice="en-US-AriaNeural",
    quality="draft",   # fast static render for verification
    style="auto",
    fmt="deep_dive",
    length="default",
    progress=print,
)

print("\n" + "="*60)
print("VIDEO GENERATION COMPLETE")
print("="*60)
print(f"Duration       : {result['total_seconds']:.1f}s")
print(f"Scenes         : {len(result['timeline'])}")
print(f"Format         : {result['format']}")
print(f"Style          : {result['style']}")
print(f"Quality        : {result['quality']}")
print(f"QA score       : {result['qa']['overall_score']:.0%}  ({result['qa']['passed']}/{result['qa']['total']} checks)")
print(f"QA ready       : {result['qa']['ready']}")

print("\nScene breakdown:")
for t in result["timeline"]:
    print(f"  Scene {t['scene']+1:2d}  {t['kind']:10}  {t['duration']:5.1f}s  {t['title'][:45]}")

print("\nOutput files:")
outdir = "output/test_rich_video"
for fname in ["lesson.mp4","mindmap.png","infographic.png","report.html",
              "01_analysis.json","02_creative.json","03_storyboard.json","07_qa_report.json"]:
    path = os.path.join(outdir, fname)
    size = os.path.getsize(path) if os.path.exists(path) else 0
    icon = "OK" if size > 0 else "MISSING"
    print(f"  [{icon}] {fname:30} {size//1024:6} KB")

print("\nQA checks:")
for c in result["qa"]["checks"]:
    icon = "OK  " if c["pass"] else "FAIL"
    note = f"  -- {c['note']}" if c["note"] else ""
    print(f"  [{icon}] {c['check']:35} {str(c['value']):8}{note}")

# Check all slides rendered
slides_dir = os.path.join(outdir, "slides")
slides = [f for f in os.listdir(slides_dir) if f.endswith(".png")] if os.path.exists(slides_dir) else []
print(f"\nSlide PNGs      : {len(slides)}")

# Check WAV files have real audio
audio_dir = os.path.join(outdir, "audio")
if os.path.exists(audio_dir):
    wavs = [f for f in os.listdir(audio_dir) if f.endswith(".wav")]
    total_audio = 0
    for wav in sorted(wavs):
        with wave.open(os.path.join(audio_dir, wav)) as w:
            dur = w.getnframes() / w.getframerate()
            total_audio += dur
    print(f"Audio WAVs      : {len(wavs)} files, {total_audio:.1f}s total")

print("\nDone. Open output/test_rich_video/lesson.mp4 to watch the video.")
print("Open http://localhost:8080 to generate via the Studio UI.")
