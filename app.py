"""Studio backend.
Run:  uvicorn app:app --port 8080
      open http://localhost:8080
"""
import hashlib
import os
import threading
import uuid

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from aivideo.db import init_db, create_job, update_job, get_job, list_jobs, index_video
from aivideo.pipeline import build_video

BASE     = os.path.dirname(os.path.abspath(__file__))
JOBS_DIR = os.path.join(BASE, "output", "jobs")
os.makedirs(JOBS_DIR, exist_ok=True)

# Initialise SQLite on startup
init_db()

app = FastAPI(title="aivideo Studio")


# ── request model ─────────────────────────────────────────────────────────────
class JobRequest(BaseModel):
    text: str
    topic: str | None = None
    engine: str = "edge_tts"       # edge_tts is the production default (natural human voice)
    voice: str | None = None
    use_claude: bool = False
    format: str = "deep_dive"       # deep_dive | brief | critique | debate
    length: str = "default"         # short | default | long
    focus: str = ""
    style: str = "auto"             # auto | classic | whiteboard | kawaii
    quality: str = "standard"       # draft | standard | cinematic


# ── background worker ─────────────────────────────────────────────────────────
def _run(job_id: str, req: JobRequest) -> None:
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
            progress=lambda m: update_job(job_id, status=m),
        )
        update_job(
            job_id,
            state="done",
            status="Done",
            result_json=result,
        )
        # Index the video for analysis and future learning
        video_path = os.path.join(JOBS_DIR, job_id, "lesson.mp4")
        if os.path.exists(video_path):
            index_video(
                job_id,
                video_path,
                total_seconds=result.get("total_seconds", 0),
                scene_count=len(result.get("timeline", [])),
                quality_score=result.get("qa", {}).get("overall_score"),
            )
    except Exception as e:
        import traceback as _tb
        update_job(job_id, state="error",
                   status=f"Failed: {e}",
                   traceback=_tb.format_exc())


def _job_response(job_id: str) -> dict:
    """Build the JSON response the UI expects from a job row."""
    job = get_job(job_id)
    if job is None:
        return {}
    # Attach file URLs if the job is done
    if job.get("state") == "done":
        base = f"/files/{job_id}"
        job.setdefault("video_url",       f"{base}/lesson.mp4")
        job.setdefault("mindmap_url",     f"{base}/mindmap.png")
        job.setdefault("infographic_url", f"{base}/infographic.png")
        job.setdefault("report_url",      f"{base}/report.html")
        job.setdefault("srt_url",         f"{base}/captions.srt")
        job.setdefault("vtt_url",         f"{base}/captions.vtt")
    return job


# ── API ───────────────────────────────────────────────────────────────────────
@app.post("/api/jobs")
def create_job_endpoint(req: JobRequest):
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
    src_hash = hashlib.sha256(req.text.encode()).hexdigest()[:16]
    create_job(
        job_id,
        state="running", status="Starting...",
        format=req.format, length=req.length,
        style=req.style, quality=req.quality,
        engine=req.engine, topic=req.topic,
        source_hash=src_hash,
    )
    threading.Thread(target=_run, args=(job_id, req), daemon=True).start()
    return _job_response(job_id)


@app.get("/api/jobs/{job_id}")
def get_job_endpoint(job_id: str):
    job = _job_response(job_id)
    if not job:
        raise HTTPException(404, "Unknown job")
    return job


@app.get("/api/jobs")
def list_jobs_endpoint(limit: int = 20, offset: int = 0):
    """List recent jobs — used by the history panel."""
    return list_jobs(limit=limit, offset=offset)


@app.get("/api/health")
def health():
    return {
        "ok": True,
        "claude_planning": bool(os.environ.get("ANTHROPIC_API_KEY")),
        "db": os.path.exists(os.path.join(BASE, "output", "jobs.db")),
    }


class SuggestRequest(BaseModel):
    text: str


@app.post("/api/suggest-topics")
def suggest_topics(req: SuggestRequest):
    """Return 3 keyword-extracted focus topic suggestions."""
    import re
    from collections import Counter
    STOP = set("a an the and or but of to in on for with as at by from is are was were be it "
               "its this that these those can will would should not so than too very into about "
               "their there which what when where who how also more most such other each many "
               "any some you we they them he she".split())
    words = [w for w in re.findall(r"[A-Za-z][A-Za-z'\-]+", req.text.lower())
             if w not in STOP and len(w) > 4]
    top = [w.capitalize() for w, _ in Counter(words).most_common(12)]
    suggestions: list[str] = []
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
