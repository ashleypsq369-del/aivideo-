# aivideo Studio

An intelligent video generator that turns lesson text into a narrated explainer video with animated diagrams, charts, mind maps, flashcards, quizzes and a full HTML report.

## What is built

### Intelligent pipeline (M0–M3)

| Stage | File | What it does |
|---|---|---|
| Ingest | `aivideo/ingest/chunker.py` | Splits txt/pdf/docx/url into stable chunks with IDs |
| Understand | `aivideo/understand/analyze.py` | Extracts concepts, facts, misconceptions, teaching arc |
| Creative | `aivideo/creative/analogies.py` | Generates analogies (diverge→map→score→converge→critique) |
| Visual choice | `aivideo/creative/visual_chooser.py` | Maps content to 1 of 14 visual types by rules |
| Storyboard | `aivideo/storyboard/planner.py` | Builds validated scene plan with beats and grounding |

### Visual engine (14 diagram types)

`aivideo/assets.py` — all drawn with Pillow, no external dependencies:

`process_flow` · `cycle` · `comparison` · `chart_bar` · `chart_line` · `timeline` · `concept_map` · `analogy_split` · `statement` · `checklist` · `cause_effect` · `tree` · `annotated_body` · `atom_orbital`

### Slide renderer

`aivideo/slides.py` — two-column layout (text left 0–1005px, diagram right 1020–1900px), 4 visual styles (auto/dark, classic/light, whiteboard, kawaii), 1920×1080 PNG.

### Animation

`aivideo/animator.py` — MoviePy animated clips per scene type (title slides in, bullets stagger, quiz options fly, summary confetti, flashcard flip). Falls back to static FFmpeg path if MoviePy unavailable.

### Voice (natural speech)

`aivideo/tts.py` — priority chain:
1. **edge-tts** (Microsoft Neural — default, no model download, requires internet)
2. **Kokoro-82M** (offline, `pip install kokoro soundfile misaki[en]`)
3. **eSpeak** (robotic fallback)
4. **mock** (silent tones — test only)

### Studio UI

`app.py` + `static/index.html` — FastAPI backend, 3-panel UI with:
- Customise modal (format, length, visual style, animation quality, voice selector, focus prompt)
- Video player with clickable timeline
- Scenes, Flashcards, Quiz, Mind Map, Infographic, Report tabs
- Download panel

### Database

`aivideo/db.py` — SQLite job store (upgradeable to Postgres). Every generated video is indexed for history and analysis.

## Run it

```bash
# Install
pip install -r requirements.txt
# also needs ffmpeg on PATH: winget install Gyan.FFmpeg

# Studio (port 8080 — port 8000 may be in use)
uvicorn app:app --port 8080
# open http://localhost:8080

# CLI
python -m aivideo samples/lesson.txt -o output

# Tests (all pass with MOCK_LLM=1, no API key needed)
MOCK_LLM=1 python -m pytest tests/ -v
```

## Configuration

Copy `.env.example` to `.env` and fill in:

```
ANTHROPIC_API_KEY=sk-ant-...   # optional: Claude-powered planning
AIVIDEO_TTS_ENGINE=edge_tts    # edge_tts | kokoro | espeak
AIVIDEO_TTS_VOICE=en-US-AriaNeural  # Microsoft Neural voice
MAX_JOB_COST_USD=0.50          # per-job cost cap
MOCK_LLM=0                     # set to 1 for CI
PORT=8080
```

## Voices (edge-tts)

| Voice | Character |
|---|---|
| `en-US-AriaNeural` | Warm American female (default) |
| `en-US-JennyNeural` | Friendly American female |
| `en-US-GuyNeural` | Natural American male |
| `en-GB-SoniaNeural` | British female |
| `en-GB-RyanNeural` | British male |
| `en-AU-NatashaNeural` | Australian female |
| `en-IN-NeerjaNeural` | Indian female |

## What is not yet built

- Remotion animated renderer (M5) — currently uses MoviePy + FFmpeg
- Whisper caption alignment (M4) — captions not yet word-synced
- Loudness normalisation (M4) — FFmpeg `loudnorm` not yet applied
- LLM visual critic loop (M6) — diagram generation is rules-based only
- Evaluation set + rubric scoring (M7)
- Studio edit/regenerate-scene endpoints (M8)
- Manim equation scenes (M9)

## Decisions

See `DECISIONS.md` for every architectural choice and its reasoning.

## Licenses

See `LICENSES.md` for every model, font, library and their licenses.
