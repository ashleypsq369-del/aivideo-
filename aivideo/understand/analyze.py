"""Understand stage — produces 01_analysis.json from source chunks.

Output schema (Analysis):
  audience       — who, prior knowledge, reading level
  goal           — what the learner can do after watching
  tone           — formal | conversational | technical | inspirational
  concepts[]     — each with id, name, plain_definition, why_it_matters,
                   prerequisites[], difficulty 1-5, abstractness 1-5, source_refs[]
  misconceptions[] — likely wrong beliefs, one per concept
  facts[]        — atomic claims, each with source_ref + short exact quote
  numbers[]      — statistics with units and source_ref
  outline        — ordered concept ids forming hook → build → apply → recap arc

Grounding rules (enforced in code, not just prompt):
  - Every fact's source_ref must exist in chunks
  - Every fact's quote must be a substring of that chunk (whitespace-normalised)
  - Any failing ref is dropped and logged, never silently included

MOCK_LLM=1 → returns a minimal fixture so tests never call the network.
"""

import json
import os
from typing import Optional

# ── Pydantic schema ───────────────────────────────────────────────────────────

try:
    from pydantic import BaseModel, Field

    class SourceRef(BaseModel):
        chunk_id: str
        quote: str

    class Concept(BaseModel):
        id: str
        name: str
        plain_definition: str
        why_it_matters: str
        prerequisites: list[str] = []
        difficulty: int = Field(default=3, ge=1, le=5)
        abstractness: int = Field(default=3, ge=1, le=5)
        source_refs: list[SourceRef] = []

    class Misconception(BaseModel):
        concept_id: str
        belief: str
        correction: str

    class Fact(BaseModel):
        id: str
        text: str
        source_ref: str   # chunk_id
        quote: str        # exact substring of that chunk

    class Number(BaseModel):
        id: str
        value: str        # e.g. "40" or "40%"
        unit: str         # e.g. "percent of children affected"
        context: str      # one sentence of context
        source_ref: str

    class Analysis(BaseModel):
        topic: str
        audience: str
        goal: str
        tone: str = "conversational"
        concepts: list[Concept] = []
        misconceptions: list[Misconception] = []
        facts: list[Fact] = []
        numbers: list[Number] = []
        outline: list[str] = []   # ordered concept ids

    PYDANTIC_OK = True

except ImportError:
    PYDANTIC_OK = False
    Analysis = None


# ── prompts ───────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are an expert instructional designer and educational content analyst.

Read the numbered source chunks provided. Use ONLY information found in those chunks.
If something is not in the text, do not include it.

Produce a structured analysis via the output tool with:
- audience: who is this for, what do they already know, what reading level
- goal: one sentence — what the learner can DO or UNDERSTAND after watching
- tone: conversational | formal | technical | inspirational
- concepts: each key idea with a plain English definition, why it matters,
  prerequisites, difficulty (1=easy, 5=hard), abstractness (1=concrete, 5=abstract),
  and source_refs with exact short quotes
- misconceptions: for each concept, the most common wrong belief and the correction
- facts: every atomic factual claim, each with the chunk_id and an exact quote
  (the quote MUST appear verbatim in that chunk)
- numbers: every statistic or quantity, with units and source chunk
- outline: ordered list of concept ids forming a teaching arc:
  hook (most surprising/relevant) → build (core ideas) → apply (real world) → recap

Rules:
- Every fact needs a source_ref. If you cannot find a source, omit the fact.
- Quotes must be exact substrings of the chunk text (normalise whitespace but no other changes).
- Maximum 8 concepts. Maximum 20 facts. Maximum 6 numbers.
- misconceptions must address real learner confusions, not invented ones.
"""


# ── grounding verifier ────────────────────────────────────────────────────────

def _verify_grounding(analysis_dict: dict, chunks: list[dict]) -> dict:
    """Drop any facts/numbers whose source_ref or quote cannot be verified.
    Returns cleaned analysis_dict and a list of violations."""
    from aivideo.ingest.chunker import verify_quote

    violations = []

    # Verify facts
    clean_facts = []
    for f in analysis_dict.get("facts", []):
        ref   = f.get("source_ref", "")
        quote = f.get("quote", "")
        if not ref or not quote:
            violations.append(f"fact {f.get('id','?')}: missing source_ref or quote")
            continue
        if verify_quote(quote, ref, chunks):
            clean_facts.append(f)
        else:
            violations.append(
                f"fact {f.get('id','?')}: quote not found in chunk {ref!r}: {quote[:60]!r}"
            )
    analysis_dict["facts"] = clean_facts

    # Verify numbers
    clean_nums = []
    for n in analysis_dict.get("numbers", []):
        ref   = n.get("source_ref", "")
        # Numbers don't require exact quote match — just chunk existence
        if ref and any(c["id"] == ref for c in chunks):
            clean_nums.append(n)
        else:
            violations.append(
                f"number {n.get('id','?')}: chunk_id {ref!r} not found"
            )
    analysis_dict["numbers"] = clean_nums

    # Verify concept source_refs
    for concept in analysis_dict.get("concepts", []):
        clean_refs = []
        for sr in concept.get("source_refs", []):
            ref   = sr.get("chunk_id", "")
            quote = sr.get("quote", "")
            if verify_quote(quote, ref, chunks):
                clean_refs.append(sr)
            else:
                violations.append(
                    f"concept {concept.get('id','?')} ref: quote not in {ref!r}"
                )
        concept["source_refs"] = clean_refs

    if violations:
        print(f"[analyze] grounding check: dropped {len(violations)} unverified refs:")
        for v in violations:
            print(f"  - {v}")

    return analysis_dict, violations


# ── mock fixture ─────────────────────────────────────────────────────────────

def _mock_analysis(chunks: list[dict], topic: str) -> dict:
    """Minimal analysis fixture for MOCK_LLM=1 mode."""
    return {
        "topic":    topic or "Lesson",
        "audience": "General learners with no prior knowledge",
        "goal":     "Understand the key concepts and their real-world importance",
        "tone":     "conversational",
        "concepts": [
            {
                "id":               "c1",
                "name":             topic or "Main Concept",
                "plain_definition": "The core idea from the source material.",
                "why_it_matters":   "It affects people's lives directly.",
                "prerequisites":    [],
                "difficulty":       2,
                "abstractness":     2,
                "source_refs":      [],
            }
        ],
        "misconceptions": [
            {
                "concept_id": "c1",
                "belief":     "It is rare and not worth worrying about.",
                "correction": "It is actually very common and preventable.",
            }
        ],
        "facts":    [],
        "numbers":  [],
        "outline":  ["c1"],
    }


# ── rules-based fallback ──────────────────────────────────────────────────────

def _rules_analysis(chunks: list[dict], topic: str) -> dict:
    """Fast rules-based analysis when LLM is unavailable."""
    import re
    from collections import Counter

    all_text = " ".join(c["text"] for c in chunks)
    words    = re.findall(r"[A-Za-z][A-Za-z'\-]+", all_text.lower())
    STOP     = set("a an the and or but of to in on for with as at by from is are was were be "
                   "it its this that these those can will would should not so than too very "
                   "into about their there which what when where who how also more most such "
                   "other each many any some you we they them he she".split())
    kw = [w for w, _ in Counter(w for w in words if w not in STOP and len(w) > 4).most_common(6)]

    facts = []
    for i, chunk in enumerate(chunks[:5]):
        sents = re.split(r"(?<=[.!?])\s+", chunk["text"].strip())
        for j, sent in enumerate(sents[:3]):
            if len(sent.split()) >= 6:
                facts.append({
                    "id":         f"f{i}_{j}",
                    "text":       sent.rstrip(".!?") + ".",
                    "source_ref": chunk["id"],
                    "quote":      sent[:80],
                })

    concepts = []
    for i, word in enumerate(kw[:4]):
        concepts.append({
            "id":               f"c{i+1}",
            "name":             word.capitalize(),
            "plain_definition": f"A key idea from the source: {word}.",
            "why_it_matters":   "Understanding this helps learners apply the knowledge.",
            "prerequisites":    [],
            "difficulty":       2,
            "abstractness":     2,
            "source_refs":      [],
        })

    return {
        "topic":         topic or "Lesson",
        "audience":      "General learners",
        "goal":          f"Understand {topic or 'the key concepts'} and why they matter.",
        "tone":          "conversational",
        "concepts":      concepts,
        "misconceptions": [
            {"concept_id": f"c{i+1}",
             "belief":     f"This is too complicated to understand.",
             "correction": f"With clear explanations, {c['name']} is accessible to everyone."}
            for i, c in enumerate(concepts[:2])
        ],
        "facts":   facts[:12],
        "numbers": [],
        "outline": [c["id"] for c in concepts],
    }


# ── public entry point ────────────────────────────────────────────────────────

def analyze(chunks_data: dict, outdir: str,
            topic: Optional[str] = None) -> dict:
    """Produce 01_analysis.json from ingest output.

    chunks_data: return value of ingest_sources() or load_chunks()
    outdir:      job directory (writes outdir/01_analysis.json)
    topic:       optional topic hint

    Returns analysis dict.
    """
    chunks  = chunks_data.get("chunks", [])
    topic   = topic or chunks_data.get("topic", "")

    # Build chunk context for the LLM (numbered for citation)
    chunk_context = "\n\n".join(
        f"[{c['id']}] (source: {c['source']}, page {c['page']})\n{c['text']}"
        for c in chunks
    )
    user_msg = (
        f"Topic hint: {topic or 'derive from text'}\n\n"
        f"Source chunks:\n\n{chunk_context}"
    )

    # MOCK mode
    if os.environ.get("MOCK_LLM", "0") == "1":
        result = _mock_analysis(chunks, topic)
        result["_mock"] = True
    else:
        # Try LLM
        try:
            from aivideo.llm import call
            schema = Analysis if PYDANTIC_OK else None
            result = call(
                stage="analysis",
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_msg}],
                schema=schema,
                temperature=0.2,
                max_tokens=6000,
            )
        except Exception as e:
            print(f"[analyze] LLM failed ({e}), using rules-based fallback.")
            result = _rules_analysis(chunks, topic)
            result["_fallback"] = True

    # Grounding verification — drop any unverified facts
    result, violations = _verify_grounding(result, chunks)
    result["_violations"] = violations
    result["_chunk_count"] = len(chunks)

    # Write output
    os.makedirs(outdir, exist_ok=True)
    out_path = os.path.join(outdir, "01_analysis.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    n_concepts = len(result.get("concepts", []))
    n_facts    = len(result.get("facts", []))
    n_viol     = len(violations)
    print(f"[analyze] {n_concepts} concepts, {n_facts} facts, "
          f"{n_viol} grounding violations dropped → {out_path}")
    return result
