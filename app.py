"""Studio backend. Run:  uvicorn app:app --reload   then open http://localhost:8000"""
import os
import threading
import uuid

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from aivideo.pipeline import build_video

BASE = os.path.dirname(os.path.abspath(__file__))
JOBS_DIR = os.path.join(BASE, "output", "jobs")
os.makedirs(JOBS_DIR, exist_ok=True)

app = FastAPI(title="aivideo Studio")
JOBS = {}


class JobRequest(BaseModel):
    text: str
    topic: str | None = None
    engine: str = "mock"
    voice: str | None = None
    use_claude: bool = False


def _run(job_id, req):
    job = JOBS[job_id]
    try:
        result = build_video(req.text, os.path.join(JOBS_DIR, job_id), req.topic, req.engine, req.voice,
                             req.use_claude, progress=lambda m: job.update(status=m))
        job.update(state="done", status="Done", plan=result["plan"], timeline=result["timeline"],
                   total_seconds=result["total_seconds"], video_url=f"/files/{job_id}/lesson.mp4")
    except Exception as e:
        job.update(state="error", status=f"Failed: {e}")


@app.post("/api/jobs")
def create_job(req: JobRequest):
    if len(req.text.strip()) < 20:
        raise HTTPException(400, "Paste at least a couple of sentences of lesson text.")
    if len(req.text) > 20000:
        raise HTTPException(400, "Lesson text is limited to 20,000 characters.")
    job_id = uuid.uuid4().hex[:10]
    JOBS[job_id] = {"id": job_id, "state": "running", "status": "Starting"}
    threading.Thread(target=_run, args=(job_id, req), daemon=True).start()
    return JOBS[job_id]


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    if job_id not in JOBS:
        raise HTTPException(404, "Unknown job")
    return JOBS[job_id]


@app.get("/api/health")
def health():
    return {"ok": True, "claude_planning": bool(os.environ.get("ANTHROPIC_API_KEY"))}


app.mount("/files", StaticFiles(directory=JOBS_DIR), name="files")


@app.get("/")
def index():
    return FileResponse(os.path.join(BASE, "static", "index.html"))
