"""End-to-end pipeline: text -> plan -> all outputs."""
import json
import os

from . import planner, slides, tts, video
from .mindmap import render_mindmap, mindmap_json
from .infographic import render_infographic
from .report import render_report


def build_video(text, outdir="output", topic=None, engine="mock", voice=None,
                use_claude=False, fmt="deep_dive", length="default", focus="",
                style="auto", quality="standard", progress=None):
    say = progress or (lambda m: None)
    os.makedirs(outdir, exist_ok=True)

    say("Planning scenes...")
    plan = planner.plan(text, topic, use_claude, fmt=fmt, length=length, focus=focus)
    with open(os.path.join(outdir, "scene_plan.json"), "w") as f:
        json.dump(plan.to_dict(), f, indent=2)

    say("Rendering slides...")
    images = slides.render_all(plan, os.path.join(outdir, "slides"), style=style)

    say("Building mind map...")
    render_mindmap(plan, os.path.join(outdir, "mindmap.png"))
    mm_json = mindmap_json(plan)
    with open(os.path.join(outdir, "mindmap.json"), "w") as f:
        json.dump(mm_json, f)

    say("Building infographic...")
    render_infographic(plan, os.path.join(outdir, "infographic.png"))

    say("Writing report...")
    render_report(plan, os.path.join(outdir, "report.html"))

    # choose renderer
    use_anim = quality in ("standard", "cinematic")
    if use_anim:
        try:
            from .animator import ANIMATION_AVAILABLE
            use_anim = ANIMATION_AVAILABLE
        except Exception:
            use_anim = False

    clips, timeline, t = [], [], 0.0
    os.makedirs(os.path.join(outdir, "audio"), exist_ok=True)
    os.makedirs(os.path.join(outdir, "clips"), exist_ok=True)

    for i, (scene, img) in enumerate(zip(plan.scenes, images)):
        verb = "Animating" if use_anim else "Rendering"
        say(f"{verb} scene {i+1}/{len(plan.scenes)}...")
        wav  = tts.synthesize(scene.narration or scene.title,
                              os.path.join(outdir, "audio", f"a_{i:02d}.wav"),
                              engine, voice)
        clip = os.path.join(outdir, "clips", f"c_{i:02d}.mp4")

        if use_anim:
            from .animator import make_animated_clip
            dur = make_animated_clip(scene, img, wav, clip, style=style, quality=quality)
        else:
            dur = video.make_clip(img, wav, clip)

        clips.append(clip)
        timeline.append({
            "scene":    i,
            "kind":     scene.kind,
            "title":    scene.title,
            "takeaway": scene.takeaway,
            "start":    round(t, 2),
            "duration": round(dur, 2),
        })
        t += dur

    say("Joining clips...")
    if quality == "cinematic" and use_anim:
        try:
            from .animator import concat_with_transitions
            concat_with_transitions(clips, os.path.join(outdir, "lesson.mp4"),
                                    transition_duration=0.4)
        except Exception:
            video.concat(clips, os.path.join(outdir, "lesson.mp4"))
    else:
        video.concat(clips, os.path.join(outdir, "lesson.mp4"))

    with open(os.path.join(outdir, "timeline.json"), "w") as f:
        json.dump(timeline, f, indent=2)

    say("Done")
    return {
        "plan":          plan.to_dict(),
        "timeline":      timeline,
        "total_seconds": round(t, 2),
        "mindmap_json":  mm_json,
        "format":        plan.format,
        "length":        plan.length,
        "style":         style,
        "quality":       quality,
    }
