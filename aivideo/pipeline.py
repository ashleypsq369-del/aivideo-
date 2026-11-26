"""End-to-end: text -> plan -> slides -> narration -> MP4."""
import json
import os

from . import planner, slides, tts, video


def build_video(text, outdir="output", topic=None, engine="mock", voice=None, use_claude=False, progress=None):
    say = progress or (lambda msg: None)
    os.makedirs(outdir, exist_ok=True)

    say("Planning scenes")
    plan = planner.plan(text, topic, use_claude)
    with open(os.path.join(outdir, "scene_plan.json"), "w") as f:
        json.dump(plan.to_dict(), f, indent=2)

    say("Rendering slides")
    images = slides.render_all(plan, os.path.join(outdir, "slides"))

    clips, timeline, t = [], [], 0.0
    os.makedirs(os.path.join(outdir, "audio"), exist_ok=True)
    os.makedirs(os.path.join(outdir, "clips"), exist_ok=True)
    for i, (scene, img) in enumerate(zip(plan.scenes, images)):
        say(f"Narrating and encoding scene {i + 1}/{len(plan.scenes)}")
        wav = tts.synthesize(scene.narration or scene.title, os.path.join(outdir, "audio", f"a_{i:02d}.wav"), engine, voice)
        clip = os.path.join(outdir, "clips", f"c_{i:02d}.mp4")
        dur = video.make_clip(img, wav, clip)
        clips.append(clip)
        timeline.append({"scene": i, "kind": scene.kind, "title": scene.title, "start": round(t, 2), "duration": round(dur, 2)})
        t += dur

    say("Joining clips")
    final = video.concat(clips, os.path.join(outdir, "lesson.mp4"))
    with open(os.path.join(outdir, "timeline.json"), "w") as f:
        json.dump(timeline, f, indent=2)
    say("Done")
    return {"video": final, "plan": plan.to_dict(), "timeline": timeline, "total_seconds": round(t, 2)}
