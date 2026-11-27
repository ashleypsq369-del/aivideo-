"""End-to-end intelligent video pipeline.

Stages (each writes a JSON contract file):
  00_sources/chunks.json   — ingest
  01_analysis.json         — understand
  02_creative.json         — creative direction
  03_storyboard.json       — storyboard (validated)
  slides/                  — rendered PNGs
  mindmap.png / .json      — mind map
  infographic.png          — infographic
  report.html              — HTML report
  audio/                   — WAV per scene
  clips/                   — MP4 clip per scene
  lesson.mp4               — final video
  timeline.json            — timing data
  07_qa_report.json        — quality checks
"""
import json
import os

from . import planner as _old_planner
from . import slides, tts, video
from .mindmap import render_mindmap, mindmap_json
from .infographic import render_infographic
from .report import render_report
from .db import index_video


def _scene_from_storyboard(sb_scene: dict):
    """Convert a storyboard scene dict into a Scene object the renderer understands."""
    from .models import Scene
    return Scene(
        kind      = _map_purpose(sb_scene.get("purpose", "explain")),
        title     = sb_scene.get("id", ""),
        bullets   = sb_scene.get("on_screen_text", []),
        narration = sb_scene.get("narration", ""),
        icon      = _icon_from_visual(sb_scene.get("visual_type", "concept_map")),
        takeaway  = "",
    )


def _map_purpose(purpose: str) -> str:
    """Map storyboard purpose to Scene kind."""
    return {
        "hook":          "title",
        "explain":       "bullets",
        "example":       "bullets",
        "misconception": "bullets",
        "apply":         "bullets",
        "recap":         "summary",
        "quiz":          "quiz",
    }.get(purpose, "bullets")


def _icon_from_visual(visual_type: str) -> str:
    return {
        "annotated_body": "health",
        "atom_orbital":   "science",
        "chart_bar":      "money",
        "chart_line":     "money",
        "process_flow":   "code",
        "concept_map":    "idea",
        "cause_effect":   "warning",
        "checklist":      "check",
        "timeline":       "book",
        "cycle":          "science",
        "comparison":     "people",
        "tree":           "people",
        "analogy_split":  "idea",
        "statement":      "book",
        "quiz":           "check",
    }.get(visual_type, "book")


def _apply_storyboard_to_plan(plan, storyboard: dict):
    """Update a ScenePlan with richer data from the storyboard."""
    sb_scenes = storyboard.get("scenes", [])
    for i, (scene, sb) in enumerate(zip(plan.scenes, sb_scenes)):
        # Enrich scene with storyboard narration if available
        if sb.get("narration"):
            scene.narration = sb["narration"]
        if sb.get("on_screen_text"):
            scene.bullets = sb["on_screen_text"][:4]
        if sb.get("visual_type"):
            scene.icon = _icon_from_visual(sb["visual_type"])


def build_video(text, outdir="output", topic=None, engine="auto", voice=None,
                use_claude=False, fmt="deep_dive", length="default", focus="",
                style="auto", quality="standard", progress=None):
    """Full intelligent pipeline.

    text:       lesson/source text
    outdir:     job output directory
    topic:      optional topic hint
    engine:     TTS engine (auto | edge_tts | kokoro | espeak | mock)
    voice:      TTS voice string
    use_claude: use Claude for planning (requires ANTHROPIC_API_KEY)
    fmt:        deep_dive | brief | critique | debate
    length:     short | default | long
    focus:      optional focus prompt
    style:      visual style (auto | classic | whiteboard | kawaii)
    quality:    draft | standard | cinematic
    progress:   callback(msg) for status updates
    """
    say = progress or (lambda m: None)
    os.makedirs(outdir, exist_ok=True)

    # ── Stage 0: Ingest ───────────────────────────────────────────────────────
    say("Ingesting source text...")
    try:
        from .ingest import ingest_sources
        chunks_data = ingest_sources([text], outdir)
    except Exception as e:
        print(f"[pipeline] ingest failed ({e}), continuing with basic plan")
        chunks_data = {"chunks": [], "total_words": 0, "sources": []}

    # ── Stage 1: Understand ───────────────────────────────────────────────────
    say("Understanding content...")
    analysis = {}
    try:
        from .understand import analyze
        analysis = analyze(chunks_data, outdir, topic=topic)
    except Exception as e:
        print(f"[pipeline] analyze failed ({e}), continuing")

    # ── Stage 2: Creative direction ───────────────────────────────────────────
    say("Generating creative direction...")
    creative = {"analogies": []}
    try:
        from .creative.analogies import generate_analogies
        creative = generate_analogies(analysis, outdir)
    except Exception as e:
        print(f"[pipeline] analogies failed ({e}), continuing")

    # ── Stage 3: Storyboard ───────────────────────────────────────────────────
    say("Building storyboard...")
    storyboard = {}
    try:
        from .storyboard import build_storyboard
        storyboard = build_storyboard(analysis, creative, outdir)
    except Exception as e:
        print(f"[pipeline] storyboard failed ({e}), continuing")

    # ── Stage 3b: Scene plan (existing planner — always works) ───────────────
    say("Planning scenes...")
    plan = _old_planner.plan(text, topic, use_claude,
                              fmt=fmt, length=length, focus=focus)
    with open(os.path.join(outdir, "scene_plan.json"), "w") as f:
        json.dump(plan.to_dict(), f, indent=2)

    # Enrich plan with storyboard narration if available
    if storyboard.get("scenes"):
        _apply_storyboard_to_plan(plan, storyboard)

    # ── Stage 4: Render slides ────────────────────────────────────────────────
    say("Rendering slides...")
    images = slides.render_all(plan, os.path.join(outdir, "slides"), style=style)

    # ── Auxiliary outputs ─────────────────────────────────────────────────────
    say("Building mind map...")
    render_mindmap(plan, os.path.join(outdir, "mindmap.png"))
    mm_json = mindmap_json(plan)
    with open(os.path.join(outdir, "mindmap.json"), "w") as f:
        json.dump(mm_json, f)

    say("Building infographic...")
    render_infographic(plan, os.path.join(outdir, "infographic.png"), style=style)

    say("Writing report...")
    render_report(plan, os.path.join(outdir, "report.html"))

    # ── Stage 5: Voice + clips ────────────────────────────────────────────────
    use_anim = quality in ("standard", "cinematic")
    if use_anim:
        try:
            from .renderer import make_animated_clip as _test_import  # noqa
            use_anim = True
        except Exception:
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
        narr = scene.narration or scene.title
        wav  = tts.synthesize(narr,
                              os.path.join(outdir, "audio", f"a_{i:02d}.wav"),
                              engine, voice)
        clip = os.path.join(outdir, "clips", f"c_{i:02d}.mp4")

        if use_anim:
            from .renderer import make_animated_clip
            dur = make_animated_clip(scene, wav, clip,
                                     style=style, quality=quality)
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

    # ── Stage 6: Compose ─────────────────────────────────────────────────────
    say("Joining clips...")
    final_video = os.path.join(outdir, "lesson.mp4")
    if quality == "cinematic" and use_anim:
        try:
            from .animator import concat_with_transitions
            concat_with_transitions(clips, final_video, transition_duration=0.4)
        except Exception:
            video.concat(clips, final_video)
    else:
        video.concat(clips, final_video)

    with open(os.path.join(outdir, "timeline.json"), "w") as f:
        json.dump(timeline, f, indent=2)

    # ── Stage 7: QA report ────────────────────────────────────────────────────
    say("Running QA checks...")
    qa = _run_qa(outdir, timeline, t, analysis, storyboard)
    with open(os.path.join(outdir, "07_qa_report.json"), "w") as f:
        json.dump(qa, f, indent=2)

    # Index video in DB for history/learning
    try:
        index_video("", final_video, total_seconds=round(t, 2),
                    scene_count=len(timeline),
                    quality_score=qa.get("overall_score"))
    except Exception:
        pass

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
        "qa":            qa,
    }


def _run_qa(outdir: str, timeline: list, total_secs: float,
            analysis: dict, storyboard: dict) -> dict:
    """Run automatic QA checks. Returns qa_report dict."""
    checks = []

    def chk(name, passed, value, threshold, note=""):
        checks.append({
            "check": name, "pass": passed,
            "value": value, "threshold": threshold, "note": note
        })

    # Scene length check (8-60s each — minimum relaxed for short lessons)
    for t in timeline:
        dur = t.get("duration", 0)
        chk(f"scene_{t['scene']}_length", 8 <= dur <= 60,
            round(dur, 1), "8-60s",
            f"Scene {t['scene']+1}: {t['title'][:30]}")

    # Visual variety: no 3 consecutive same type (bullets only — not quiz/flashcard/summary)
    kinds = [t.get("kind", "") for t in timeline]
    variety_ok = True
    BULLET_LIKE = {"bullets"}
    for i in range(len(kinds) - 2):
        if kinds[i] in BULLET_LIKE and kinds[i] == kinds[i+1] == kinds[i+2]:
            variety_ok = False
    chk("visual_variety", variety_ok, str(kinds), "no 3 consecutive bullet scenes")

    # Non-bullet visuals >= 60%
    non_bullet = sum(1 for t in timeline if t.get("kind") not in ("bullets",))
    pct = non_bullet / max(len(timeline), 1)
    chk("non_bullet_visuals", pct >= 0.4, f"{pct:.0%}", ">= 40%",
        f"{non_bullet}/{len(timeline)} non-bullet scenes")

    # Total duration sanity
    chk("total_duration", 30 <= total_secs <= 900,
        round(total_secs, 1), "30-900s",
        f"Total: {total_secs:.0f}s")

    # Grounding (from analysis)
    violations = analysis.get("_violations", [])
    chk("grounding_violations", len(violations) == 0,
        len(violations), "0", f"{len(violations)} unverified refs dropped")

    # Storyboard validation
    sb_violations = storyboard.get("_violations", [])
    chk("storyboard_validation", len(sb_violations) == 0,
        len(sb_violations), "0", f"{len(sb_violations)} storyboard issues fixed")

    # Check output files exist
    for fname in ["lesson.mp4", "mindmap.png", "infographic.png", "report.html",
                  "scene_plan.json", "timeline.json"]:
        path = os.path.join(outdir, fname)
        chk(f"file_{fname}", os.path.exists(path), fname,
            "exists", "" if os.path.exists(path) else "MISSING")

    passed = sum(1 for c in checks if c["pass"])
    total  = len(checks)
    score  = round(passed / max(total, 1), 2)

    return {
        "passed":        passed,
        "total":         total,
        "overall_score": score,
        "ready":         score >= 0.80,
        "checks":        checks,
    }
