"""Generate a 3-scene animated video to verify renderer + MoviePy pipeline."""
import os, wave
os.environ["MOCK_LLM"] = "1"

from aivideo.models import Scene
from aivideo.renderer import make_animated_clip
from aivideo.video import concat
from aivideo.tts import synthesize

os.makedirs("output/test_anim", exist_ok=True)
os.makedirs("output/test_anim/audio", exist_ok=True)
os.makedirs("output/test_anim/clips", exist_ok=True)

scenes = [
    Scene("title",   "The Human Immune System",
          narration="Your body has an incredible defence system. Today we explore how it works.",
          icon="health", takeaway="The immune system protects you from pathogens."),
    Scene("bullets", "Two Branches of Immunity",
          bullets=["Innate immunity: fast, non-specific, responds in minutes",
                   "Adaptive immunity: slow but precise, 7-14 days to activate",
                   "Memory cells persist for decades after first exposure"],
          narration="Your immune system has two branches. The innate system reacts instantly to any threat. The adaptive system learns your specific enemy and remembers it forever.",
          icon="health", takeaway="Innate is fast; adaptive is smart and remembers."),
    Scene("summary", "What You Learned",
          bullets=["Innate immunity: immediate barrier defence",
                   "Adaptive immunity: targeted, long-lasting protection",
                   "Vaccines exploit immune memory to prevent disease"],
          narration="To summarise: your immune system combines speed and intelligence to keep you safe.",
          icon="check", takeaway="Your immune system is both fast and smart."),
]

clips = []
t_total = 0.0
timeline = []

for i, scene in enumerate(scenes):
    print(f"\nRendering scene {i+1}/{len(scenes)}: {scene.title}")
    wav  = f"output/test_anim/audio/a_{i:02d}.wav"
    clip = f"output/test_anim/clips/c_{i:02d}.mp4"

    # Synthesise voice
    synthesize(scene.narration, wav, engine="edge_tts", voice="en-US-AriaNeural")
    with wave.open(wav) as w:
        dur = w.getnframes() / w.getframerate()
    print(f"  Audio: {dur:.1f}s")

    # Animated clip
    clip_dur = make_animated_clip(scene, wav, clip, style="auto", quality="standard")
    print(f"  Clip:  {clip_dur:.1f}s -> {clip}")
    clips.append(clip)
    timeline.append({"scene": i, "kind": scene.kind, "title": scene.title,
                      "start": round(t_total,2), "duration": round(clip_dur,2)})
    t_total += clip_dur

print(f"\nJoining {len(clips)} clips...")
concat(clips, "output/test_anim/lesson.mp4")

total_size = os.path.getsize("output/test_anim/lesson.mp4") // 1024
print(f"\n{'='*55}")
print(f"ANIMATED VIDEO COMPLETE")
print(f"Duration  : {t_total:.1f}s")
print(f"File size : {total_size} KB")
print(f"Output    : output/test_anim/lesson.mp4")
print(f"\nTimeline:")
for t in timeline:
    print(f"  Scene {t['scene']+1}: {t['kind']:10} {t['duration']:.1f}s  {t['title']}")
print(f"\nOpen output/test_anim/lesson.mp4 to watch the animated video.")
