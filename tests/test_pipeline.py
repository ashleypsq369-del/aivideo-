"""Core pipeline tests.

All tests run with MOCK_LLM=1 and engine=mock so no network calls are made.
"""
import os
import shutil
import subprocess
import tempfile

import pytest

os.environ.setdefault("MOCK_LLM", "1")

from aivideo.planner import plan_with_rules, _icon_for
from aivideo.pipeline import build_video

LESSON = open(
    os.path.join(os.path.dirname(__file__), "..", "samples", "lesson.txt")
).read()


# ── planner ───────────────────────────────────────────────────────────────────

def test_plan_structure():
    p = plan_with_rules(LESSON)
    kinds = [s.kind for s in p.scenes]
    assert kinds[0] == "title"
    assert kinds[-1] == "summary"
    assert "quiz" in kinds


def test_icon_uses_whole_words():
    assert _icon_for("the story was spread widely") == "book"
    assert _icon_for("malaria patients at the clinic") == "health"


def test_empty_text_rejected():
    with pytest.raises(ValueError):
        plan_with_rules("   ")


# ── ingest ────────────────────────────────────────────────────────────────────

def test_ingest_txt():
    from aivideo.ingest import ingest_sources
    with tempfile.TemporaryDirectory() as d:
        result = ingest_sources(
            [os.path.join(os.path.dirname(__file__), "..", "samples", "lesson.txt")], d
        )
        assert result["chunk_count"] >= 1
        assert result["total_words"] > 0
        assert all("id" in c for c in result["chunks"])


def test_ingest_stable_ids():
    """Same text produces same chunk IDs on repeated runs."""
    from aivideo.ingest import ingest_sources
    src = os.path.join(os.path.dirname(__file__), "..", "samples", "lesson.txt")
    with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
        r1 = ingest_sources([src], d1)
        r2 = ingest_sources([src], d2)
        ids1 = [c["id"] for c in r1["chunks"]]
        ids2 = [c["id"] for c in r2["chunks"]]
        assert ids1 == ids2, "Chunk IDs are not stable"


def test_ingest_verify_quote():
    from aivideo.ingest import ingest_sources
    from aivideo.ingest.chunker import verify_quote
    with tempfile.TemporaryDirectory() as d:
        result = ingest_sources([LESSON], d)
        chunks = result["chunks"]
        first  = chunks[0]
        # Quote that IS in the chunk
        assert verify_quote(first["text"][:30], first["id"], chunks) is True
        # Quote that is NOT
        assert verify_quote("this invented phrase xyz123", first["id"], chunks) is False


# ── understand ────────────────────────────────────────────────────────────────

def test_analyze_mock():
    from aivideo.ingest import ingest_sources
    from aivideo.understand import analyze
    with tempfile.TemporaryDirectory() as d:
        chunks  = ingest_sources([LESSON], d)
        result  = analyze(chunks, d, topic="Malaria")
        assert "concepts"      in result
        assert "facts"         in result
        assert "outline"       in result
        assert "_violations"   in result
        assert result.get("_mock") is True  # MOCK_LLM=1


# ── creative ─────────────────────────────────────────────────────────────────

def test_analogies_mock():
    from aivideo.ingest import ingest_sources
    from aivideo.understand import analyze
    from aivideo.creative.analogies import generate_analogies
    with tempfile.TemporaryDirectory() as d:
        chunks   = ingest_sources([LESSON], d)
        analysis = analyze(chunks, d)
        creative = generate_analogies(analysis, d)
        assert "analogies" in creative
        assert len(creative["analogies"]) >= 1
        for a in creative["analogies"]:
            assert "domain"   in a
            assert "analogy"  in a
            assert "mapping"  in a
            assert len(a["mapping"]) >= 3


def test_visual_chooser():
    from aivideo.creative.visual_chooser import choose_visual, assign_visuals
    from aivideo.storyboard.planner import ALLOWED_VISUAL_TYPES

    # Basic routing
    vt, _ = choose_visual("Steps to prevent disease", ["Use nets", "Take vaccine"], "bullets", "check")
    assert vt in ALLOWED_VISUAL_TYPES

    # Kind overrides
    vt_title, _ = choose_visual("My Topic", [], "title", "book")
    assert vt_title == "statement"

    vt_quiz, _ = choose_visual("Quiz Time", [], "quiz", "check")
    assert vt_quiz == "quiz"

    # No consecutive duplicates
    scenes = [
        {"kind": "bullets", "title": "A", "bullets": [], "icon": "book"},
        {"kind": "bullets", "title": "B", "bullets": [], "icon": "book"},
        {"kind": "bullets", "title": "C", "bullets": [], "icon": "book"},
    ]
    assigned = assign_visuals(scenes, [])
    types = [s["visual_type"] for s in assigned]
    for i in range(len(types) - 1):
        if types[i] == types[i+1] and types[i] not in {"statement", "quiz"}:
            assert False, f"Consecutive duplicate: {types}"


# ── storyboard ────────────────────────────────────────────────────────────────

def test_storyboard_validation():
    from aivideo.ingest import ingest_sources
    from aivideo.understand import analyze
    from aivideo.creative.analogies import generate_analogies
    from aivideo.storyboard import build_storyboard
    from aivideo.storyboard.planner import ALLOWED_VISUAL_TYPES

    with tempfile.TemporaryDirectory() as d:
        chunks   = ingest_sources([LESSON], d)
        analysis = analyze(chunks, d)
        creative = generate_analogies(analysis, d)
        sb       = build_storyboard(analysis, creative, d)

        assert len(sb["scenes"]) >= 3
        for scene in sb["scenes"]:
            # Visual type must be allowed
            assert scene["visual_type"] in ALLOWED_VISUAL_TYPES, \
                f"Invalid visual_type: {scene['visual_type']}"
            # target_seconds in range
            ts = scene.get("target_seconds", 25)
            assert 12 <= ts <= 60, f"target_seconds {ts} out of range"
            # on_screen_text limits
            ost = scene.get("on_screen_text", [])
            assert len(ost) <= 4
            for item in ost:
                assert len(item.split()) <= 12, f"on_screen_text item too long: {item!r}"
            # beats at_phrase in narration
            narr = scene.get("narration", "")
            for beat in scene.get("beats", []):
                phrase = beat.get("at_phrase", "")
                assert phrase.lower() in narr.lower(), \
                    f"beat phrase {phrase!r} not in narration"


def test_storyboard_rejects_ungrounded():
    """Validator should drop beats whose at_phrase isn't in narration."""
    from aivideo.storyboard.planner import _validate_storyboard
    sb = {
        "scenes": [{
            "id": "s01",
            "purpose": "explain",
            "visual_type": "concept_map",
            "visual_spec": {},
            "narration": "Malaria is spread by mosquitoes.",
            "beats": [
                {"at_phrase": "Malaria is spread", "action": "reveal", "target": "node"},
                {"at_phrase": "this phrase does not exist in narration", "action": "reveal", "target": "x"},
            ],
            "on_screen_text": [],
            "facts_used": [],
            "target_seconds": 20,
        }]
    }
    cleaned, violations = _validate_storyboard(sb, [])
    # The bad beat should have been dropped
    assert len(cleaned["scenes"][0]["beats"]) == 1
    assert any("not in narration" in v for v in violations)


# ── end-to-end video ─────────────────────────────────────────────────────────

@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg not installed")
def test_end_to_end_video_matches_timeline():
    with tempfile.TemporaryDirectory() as d:
        r = build_video(LESSON, d, engine="mock", quality="draft")
        video_path = os.path.join(d, "lesson.mp4")
        assert os.path.exists(video_path), "lesson.mp4 not created"
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", video_path],
            capture_output=True, text=True
        ).stdout.strip()
        video_dur = float(out)
        assert abs(video_dur - r["total_seconds"]) < 2.0, \
            f"Video duration {video_dur:.1f}s != timeline {r['total_seconds']:.1f}s"


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg not installed")
def test_qa_report_created():
    with tempfile.TemporaryDirectory() as d:
        r = build_video(LESSON, d, engine="mock", quality="draft")
        assert "qa" in r
        assert os.path.exists(os.path.join(d, "07_qa_report.json"))
        assert r["qa"]["total"] > 0
