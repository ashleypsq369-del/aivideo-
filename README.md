# aivideo

A NotebookLM-style "Studio" that turns lesson text into a narrated explainer video.

    text -> scene plan -> slide images -> narration -> FFmpeg -> MP4

## What is built

| Part | File | Notes |
|---|---|---|
| Scene planner | `aivideo/planner.py` | Offline rules by default; optional Claude planner returns structured JSON |
| Slides | `aivideo/slides.py` | Pillow, 1920x1080, title / bullets / quiz / summary layouts |
| Narration | `aivideo/tts.py` | `mock` (test tones), `espeak`, `kokoro` (Kokoro-82M, check its license) |
| Video | `aivideo/video.py` | Each slide lasts exactly as long as its narration |
| Pipeline + CLI | `aivideo/pipeline.py`, `aivideo/cli.py` | Writes `scene_plan.json` and `timeline.json` |
| Studio | `app.py`, `static/index.html` | FastAPI job API, video player, clickable scene timeline |

## Run it

    pip install -r requirements.txt     # also needs ffmpeg on your PATH
    python -m aivideo samples/lesson.txt -o output          # CLI
    uvicorn app:app --reload                                # Studio at http://localhost:8000
    python -m pytest tests                                  # tests

Real voice: `pip install kokoro soundfile`, then choose Kokoro in the Studio or use `--engine kokoro`.
Claude planning: set `ANTHROPIC_API_KEY` and tick the Claude option (or use `--claude`).

## Not built yet

- Animated scenes (the next step is Remotion or Manim for real motion; slides are still images today)
- Generated illustrations, captions (Whisper), loudness normalisation (FFmpeg `loudnorm`)
- Job queue and database (jobs live in memory and are lost on restart), authentication
