# Third-party Licenses

This file records the license of every third-party dependency used by aivideo.
Update this file whenever a new model, font, icon set, audio track or library is added.

---

## Python libraries

| Package | License | Notes |
|---|---|---|
| Pillow | HPND (MIT-compatible) | Image rendering |
| FastAPI | MIT | Web framework |
| Uvicorn | BSD-3-Clause | ASGI server |
| Pydantic | MIT | Data validation |
| anthropic | MIT | Anthropic API client |
| moviepy 2.x | MIT | Video composition |
| numpy | BSD-3-Clause | Array operations |
| opencv-python-headless | Apache 2.0 | Frame processing |
| matplotlib | PSF (BSD-compatible) | Charts |
| faster-whisper | MIT | Word-aligned transcription |
| trafilatura | Apache 2.0 | Web content extraction |
| pdfplumber | MIT | PDF text extraction |
| python-docx | MIT | DOCX extraction |
| SQLAlchemy | MIT | Database ORM |
| python-dotenv | BSD-3-Clause | .env loading |

---

## TTS models

| Model | License | Commercial use | Notes |
|---|---|---|---|
| Kokoro-82M | Apache 2.0 | Yes | Default voice engine. Voices: af_heart, af_sky, am_michael. pip install kokoro soundfile |
| eSpeak NG | GPL-3.0 | Yes (open source only) | Fallback TTS. Not for proprietary distribution. |

---

## Fonts

| Font | License | Source |
|---|---|---|
| Arial | Proprietary (bundled with Windows) | C:/Windows/Fonts — do not redistribute |
| DejaVu Sans | Bitstream Vera (free, permissive) | /usr/share/fonts/truetype/dejavu |

> **Note:** The Arial font is used only when running on Windows and is not redistributed.
> For cross-platform/server deployment, DejaVu Sans is the primary font.

---

## Icons / graphics

No external icon sets are currently used. All icons are drawn programmatically with Pillow.

---

## Music / audio

No music tracks are currently included. Any future music must be licensed under CC0, CC-BY, or a commercial royalty-free license, and recorded here before use.

---

## Remotion

Remotion is licensed under the Remotion License. Free for companies with fewer than 3 employees or for open-source projects. For commercial use with 3+ employees, a license is required. See https://remotion.dev/license before enabling the Remotion renderer.

---

## FFmpeg

FFmpeg is licensed under LGPL-2.1 or GPL-2.0 depending on build options. The winget `Gyan.FFmpeg` build (used here) is a full GPL build. Ensure your use case is compatible with GPL-2.0+. See https://ffmpeg.org/legal.html

---

*Last updated: 2026-11-26*
