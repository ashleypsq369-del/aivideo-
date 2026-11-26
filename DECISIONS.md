# Architecture Decisions

Decisions made during implementation, with reasoning. Append new entries chronologically.

---

## 2026-11-26 — M0 Hygiene

**D001 — SQLite for job persistence (upgrade path to Postgres)**
*Decision:* Use SQLite via SQLAlchemy as the job store, replacing the in-memory dict.
*Reason:* Server restarts were losing all jobs. SQLite requires zero extra infrastructure on a developer machine. SQLAlchemy means swapping to Postgres later is a one-line config change.
*Trade-off:* SQLite has limited concurrent write performance; acceptable for a single-machine Studio. Switch to Postgres before multi-user deployment.

**D002 — Port 8080 as default**
*Decision:* Default server port changed from 8000 to 8080.
*Reason:* Port 8000 is occupied by another service (Aura Care API) on the developer machine.

**D003 — Kokoro as production TTS, never mock in production**
*Decision:* `AIVIDEO_TTS_ENGINE=kokoro` is the production default. The mock/test-tone engine is restricted to `engine="mock"` in test code only.
*Reason:* The mock produces unrecognisable robot clicks. Kokoro-82M (Apache 2.0) produces warm, natural speech suitable for educational video.
*Fallback chain:* Kokoro → eSpeak → abort with clear error. eSpeak is GPL so cannot be shipped in proprietary builds; always try Kokoro first.

**D004 — Slide layout: 55% text left, 45% diagram right, no overlap**
*Decision:* Bullet scenes render text in the left 1040px and diagrams in the right 860px (x=1022). Text bullets are constrained to max 920px wide.
*Reason:* The previous layout clipped text and let the diagram overlap bullet cards. The guide requires "nothing clipped or overlapping".

**D005 — Visual types capped at 14 (from the guide's decision table)**
*Decision:* `visual_chooser.py` maps content shape to exactly one of 14 visual types from the guide. The slides and animator only implement these types.
*Reason:* Unlimited visual types create inconsistency. A fixed vocabulary with trusted renderers is more reliable.

**D006 — One file per commit, push after each**
*Decision:* Follow the guide strictly: create or change one file, run its test/smoke check, commit, push.
*Reason:* Keeps the history bisectable and prevents silent batching of unrelated failures.

---

## To be recorded as implemented

- D007 — LLM wrapper design (M1)
- D008 — Analogy generation strategy (M2)
- D009 — Storyboard validation approach (M3)
- D010 — Caption alignment method (M4)
