import os
import shutil
import subprocess
import tempfile

import pytest

from aivideo.planner import plan_with_rules, _icon_for
from aivideo.pipeline import build_video

LESSON = open(os.path.join(os.path.dirname(__file__), "..", "samples", "lesson.txt")).read()


def test_plan_structure():
    p = plan_with_rules(LESSON)
    kinds = [s.kind for s in p.scenes]
    assert kinds[0] == "title" and kinds[-1] == "summary" and "quiz" in kinds


def test_icon_uses_whole_words():
    assert _icon_for("the story was spread widely") == "book"
    assert _icon_for("malaria patients at the clinic") == "health"


def test_empty_text_rejected():
    with pytest.raises(ValueError):
        plan_with_rules("   ")


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg not installed")
def test_end_to_end_video_matches_timeline():
    with tempfile.TemporaryDirectory() as d:
        r = build_video(LESSON, d)
        out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", r["video"]],
                             capture_output=True, text=True).stdout
        assert abs(float(out) - r["total_seconds"]) < 1.5
