"""Ingest sources and produce stable chunks.

Each chunk has:
  id       — stable string like "s1_p3_c2" (source_index, page/heading, chunk)
  source   — original filename or URL
  text     — 300-500 word excerpt
  page     — page number or heading (for citations)
  meta     — {"source_type": "txt"|"pdf"|"docx"|"url", "char_start": int}

Output: 00_sources/chunks.json
Limits: 20 MB per file, 50,000 words total — rejected with a clear message.
"""

import hashlib
import json
import os
import re
import textwrap
from pathlib import Path
from typing import Optional

MAX_FILE_BYTES  = 20 * 1024 * 1024   # 20 MB
MAX_TOTAL_WORDS = 50_000
CHUNK_WORDS_MIN = 280
CHUNK_WORDS_MAX = 520


# ── text splitter ─────────────────────────────────────────────────────────────

def _split_into_chunks(text: str, source_idx: int, source_name: str,
                       source_type: str) -> list[dict]:
    """Split text into ~300-500 word chunks with stable ids."""
    # Normalise whitespace but preserve paragraph breaks
    text = re.sub(r"\r\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Split by paragraph breaks first, then by sentence if paragraph is too long
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

    chunks  = []
    buf     = []
    buf_wc  = 0
    page    = 1
    chunk_i = 0

    def flush(page_no):
        nonlocal chunk_i
        if not buf:
            return
        body = " ".join(buf)
        cid  = f"s{source_idx}_p{page_no}_c{chunk_i}"
        chunks.append({
            "id":          cid,
            "source":      source_name,
            "source_type": source_type,
            "page":        page_no,
            "char_start":  text.find(buf[0]) if buf else 0,
            "text":        body,
            "word_count":  len(body.split()),
            "hash":        hashlib.md5(body.encode()).hexdigest()[:8],
        })
        chunk_i += 1
        buf.clear()

    for para in paragraphs:
        words = para.split()
        if len(words) == 0:
            continue

        # Very long paragraph — split at sentence boundaries
        if len(words) > CHUNK_WORDS_MAX:
            sentences = re.split(r"(?<=[.!?])\s+", para)
            for sent in sentences:
                sw = len(sent.split())
                if buf_wc + sw > CHUNK_WORDS_MAX:
                    flush(page)
                    buf_wc = 0
                buf.append(sent)
                buf_wc += sw
                if buf_wc >= CHUNK_WORDS_MIN:
                    flush(page)
                    buf_wc = 0
        else:
            if buf_wc + len(words) > CHUNK_WORDS_MAX:
                flush(page)
                buf_wc = 0
            buf.append(para)
            buf_wc += len(words)
            if buf_wc >= CHUNK_WORDS_MIN:
                flush(page)
                buf_wc = 0

        # Crude page counter: a line that is all digits / "Page N"
        if re.match(r"^(page\s*)?\d+$", para.strip(), re.I):
            page += 1

    flush(page)   # trailing content
    return chunks


# ── format-specific extractors ────────────────────────────────────────────────

def _ingest_txt(path: str, source_idx: int) -> list[dict]:
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    return _split_into_chunks(text, source_idx, Path(path).name, "txt")


def _ingest_pdf(path: str, source_idx: int) -> list[dict]:
    try:
        import pdfplumber
    except ImportError:
        raise RuntimeError(
            "pdfplumber not installed. Run: pip install pdfplumber"
        )
    chunks = []
    with pdfplumber.open(path) as pdf:
        for page_no, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            if text.strip():
                for c in _split_into_chunks(text, source_idx,
                                             Path(path).name, "pdf"):
                    c["page"] = page_no
                    chunks.append(c)
    return chunks


def _ingest_docx(path: str, source_idx: int) -> list[dict]:
    try:
        from docx import Document
    except ImportError:
        raise RuntimeError(
            "python-docx not installed. Run: pip install python-docx"
        )
    doc   = Document(path)
    paras = []
    page  = 1
    for para in doc.paragraphs:
        t = para.text.strip()
        if not t:
            continue
        # Use heading level as a page proxy for citation
        if para.style.name.startswith("Heading"):
            page += 1
        paras.append(t)
    text = "\n\n".join(paras)
    return _split_into_chunks(text, source_idx, Path(path).name, "docx")


def _ingest_url(url: str, source_idx: int) -> list[dict]:
    try:
        import trafilatura
    except ImportError:
        raise RuntimeError(
            "trafilatura not installed. Run: pip install trafilatura"
        )
    downloaded = trafilatura.fetch_url(url)
    if not downloaded:
        raise RuntimeError(f"Could not fetch URL: {url}")
    text = trafilatura.extract(downloaded, include_comments=False,
                                include_tables=True) or ""
    if not text.strip():
        raise RuntimeError(f"No extractable text at URL: {url}")
    return _split_into_chunks(text, source_idx, url, "url")


def _ingest_text_string(text: str, source_idx: int, name: str = "input") -> list[dict]:
    """Ingest a raw text string directly (used by existing pipeline)."""
    return _split_into_chunks(text, source_idx, name, "txt")


# ── public API ────────────────────────────────────────────────────────────────

def ingest_sources(sources: list, outdir: str) -> dict:
    """Ingest a list of sources.

    sources: list of file paths (str/Path) or URLs (str starting with http)
             OR a list of raw text strings (for backwards compat)

    Returns: {"chunks": [...], "total_words": int, "sources": [...]}
    Writes:  outdir/00_sources/chunks.json
    """
    os.makedirs(os.path.join(outdir, "00_sources"), exist_ok=True)
    all_chunks  = []
    total_words = 0
    source_list = []

    for idx, src in enumerate(sources):
        src_str = str(src)

        # Size check for files
        if not src_str.startswith("http"):
            p = Path(src_str)
            if p.exists() and p.stat().st_size > MAX_FILE_BYTES:
                raise ValueError(
                    f"Source '{p.name}' is {p.stat().st_size/1e6:.1f} MB — "
                    f"limit is {MAX_FILE_BYTES/1e6:.0f} MB."
                )

        try:
            if src_str.startswith("http://") or src_str.startswith("https://"):
                chunks = _ingest_url(src_str, idx)
                source_list.append({"index": idx, "type": "url", "source": src_str})
            elif Path(src_str).suffix.lower() == ".pdf":
                chunks = _ingest_pdf(src_str, idx)
                source_list.append({"index": idx, "type": "pdf", "source": src_str})
            elif Path(src_str).suffix.lower() in (".docx", ".doc"):
                chunks = _ingest_docx(src_str, idx)
                source_list.append({"index": idx, "type": "docx", "source": src_str})
            else:
                # .txt / .md / plain text
                if Path(src_str).exists():
                    chunks = _ingest_txt(src_str, idx)
                    source_list.append({"index": idx, "type": "txt", "source": src_str})
                else:
                    # Treat as raw text string
                    chunks = _ingest_text_string(src_str, idx, f"text_{idx}")
                    source_list.append({"index": idx, "type": "text", "source": f"text_{idx}"})
        except Exception as e:
            raise RuntimeError(f"Failed to ingest source {idx} ({src_str[:60]}): {e}") from e

        words_in_source = sum(c["word_count"] for c in chunks)
        total_words    += words_in_source
        all_chunks.extend(chunks)

        if total_words > MAX_TOTAL_WORDS:
            raise ValueError(
                f"Total word count {total_words:,} exceeds the "
                f"{MAX_TOTAL_WORDS:,}-word limit. Use shorter or fewer sources."
            )

    result = {
        "chunks":      all_chunks,
        "total_words": total_words,
        "sources":     source_list,
        "chunk_count": len(all_chunks),
    }

    out_path = os.path.join(outdir, "00_sources", "chunks.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"[ingest] {len(all_chunks)} chunks, {total_words:,} words → {out_path}")
    return result


def load_chunks(outdir: str) -> dict:
    """Load previously written chunks.json."""
    path = os.path.join(outdir, "00_sources", "chunks.json")
    if not os.path.exists(path):
        raise FileNotFoundError(f"chunks.json not found at {path}")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def verify_quote(quote: str, chunk_id: str, chunks: list[dict]) -> bool:
    """Check that quote is a substring of the chunk with chunk_id.
    Normalises whitespace before comparison.
    """
    for c in chunks:
        if c["id"] == chunk_id:
            norm_chunk = " ".join(c["text"].split())
            norm_quote = " ".join(quote.split())
            return norm_quote in norm_chunk
    return False
