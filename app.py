"""Studio backend.  uvicorn app:app --port 8000  → http://localhost:8000"""
import json
import os
import threading
import uuid

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from aivideo.pipeline import build_video

BASE = os.path.dirname(os.path.abspath(__file__))
JOBS_DIR = os.path.join(BASE, "output", "jobs")
os.makedirs(JOBS_DIR, exist_ok=True)

app = FastAPI(title="aivideo Studio")

# ── persistent job store ──────────────────────────────────────────────────────
_LOCK = threading.Lock()
_STATE_FILE = os.path.join(BASE, "output", "jobs_state.json")


def _load_jobs():
    if os.path.exists(_STATE_FILE):
        try:
            with open(_STATE_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save_jobs(jobs):
    with open(_STATE_FILE, "w") as f:
        json.dump(jobs, f)


def _update_job(job_id, **kwargs):
    with _LOCK:
        jobs = _load_jobs()
        jobs.setdefault(job_id, {}).update(kwargs)
        _save_jobs(jobs)


def _get_job(job_id):
    with _LOCK:
        return _load_jobs().get(job_id)


# ── request model ─────────────────────────────────────────────────────────────
class JobRequest(BaseModel):
    text: str
    topic: str | None = None
    engine: str = "mock"
    voice: str | None = None
    use_claude: bool = False
    format: str = "deep_dive"
    length: str = "default"
    focus: str = ""
    style: str = "auto"
    quality: str = "standard"  # draft | standard | cinematic


# ── background worker ─────────────────────────────────────────────────────────
def _run(job_id, req):
    try:
        result = build_video(
            req.text,
            os.path.join(JOBS_DIR, job_id),
            req.topic,
            req.engine,
            req.voice,
            req.use_claude,
            fmt=req.format,
            length=req.length,
            focus=req.focus,
            style=req.style,
            quality=req.quality,
            progress=lambda m: _update_job(job_id, status=m),
        )
        _update_job(
            job_id,
            state="done",
            status="Done ✓",
            plan=result["plan"],
            timeline=result["timeline"],
            total_seconds=result["total_seconds"],
            mindmap_json=result["mindmap_json"],
            format=result["format"],
            length=result["length"],
            style=result.get("style", "auto"),
            quality=result.get("quality", "standard"),
            video_url=f"/files/{job_id}/lesson.mp4",
            mindmap_url=f"/files/{job_id}/mindmap.png",
            infographic_url=f"/files/{job_id}/infographic.png",
            report_url=f"/files/{job_id}/report.html",
        )
    except Exception as e:
        import traceback
        _update_job(job_id, state="error", status=f"Failed: {e}",
                    traceback=traceback.format_exc())


# ── API ───────────────────────────────────────────────────────────────────────
@app.post("/api/jobs")
def create_job(req: JobRequest):
    if len(req.text.strip()) < 20:
        raise HTTPException(400, "Paste at least a couple of sentences of lesson text.")
    if len(req.text) > 20000:
        raise HTTPException(400, "Lesson text is limited to 20,000 characters.")
    if req.format not in ("deep_dive", "brief", "critique", "debate"):
        raise HTTPException(400, "Invalid format.")
    if req.length not in ("short", "default", "long"):
        raise HTTPException(400, "Invalid length.")
    if req.quality not in ("draft", "standard", "cinematic"):
        raise HTTPException(400, "Invalid quality.")
    job_id = uuid.uuid4().hex[:10]
    _update_job(job_id, id=job_id, state="running", status="Starting…",
                format=req.format, length=req.length)
    threading.Thread(target=_run, args=(job_id, req), daemon=True).start()
    return _get_job(job_id)


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    job = _get_job(job_id)
    if job is None:
        raise HTTPException(404, "Unknown job")
    return job


@app.get("/api/health")
def health():
    return {"ok": True, "claude_planning": bool(os.environ.get("ANTHROPIC_API_KEY"))}


class SuggestRequest(BaseModel):
    text: str


@app.post("/api/suggest-topics")
def suggest_topics(req: SuggestRequest):
    """Return 3 AI-suggested focus topic chips from the lesson text."""
    import re
    from collections import Counter
    STOPWORDS = set("a an the and or but of to in on for with as at by from is are was were be it its this that "
                    "these those can will would should not so than too very into about their there which what "
                    "when where who how also more most such other each many any some you we they them he she".split())
    words = [w for w in re.findall(r"[A-Za-z][A-Za-z'\-]+", req.text.lower())
             if w not in STOPWORDS and len(w) > 4]
    top = [w.capitalize() for w, _ in Counter(words).most_common(12)]
    # Group into 3 meaningful phrases using pairs
    suggestions = []
    for i in range(0, min(6, len(top)-1), 2):
        suggestions.append(f"{top[i]} & {top[i+1]}")
    suggestions = suggestions[:3]
    if len(suggestions) < 3:
        suggestions += [top[j] for j in range(len(suggestions)*2, len(top))][:3-len(suggestions)]
    return {"topics": suggestions[:3]}


app.mount("/files", StaticFiles(directory=JOBS_DIR), name="files")


@app.get("/")
def index():
    return FileResponse(os.path.join(BASE, "static", "index.html"))
