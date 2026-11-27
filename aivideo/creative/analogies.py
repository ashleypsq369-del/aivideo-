"""Analogy generation — Section 5.3 of the guide.

For each abstract concept (abstractness >= 3):
  1. DIVERGE:  5 analogies from 5 different domains + 2 visual metaphors
  2. MAP:      mapping table (source -> target, min 3 pairs) + "where it breaks"
  3. SCORE:    1-5 on accuracy, familiarity, visualisability, memorability, novelty
  4. CONVERGE: pick highest total with accuracy >= 4
  5. CRITIQUE: skeptical teacher pass — fix misleading parts
  6. HISTORY:  never reuse same domain in same video; track across workspace

Output: 02_creative.json
"""

import hashlib
import json
import os
from pathlib import Path
from typing import Optional

# ── cliché list ───────────────────────────────────────────────────────────────

def _load_cliches() -> list[str]:
    path = Path(__file__).parent / "cliches.txt"
    if not path.exists():
        return []
    return [ln.strip() for ln in path.read_text().splitlines()
            if ln.strip() and not ln.startswith("#")]


# ── history store ─────────────────────────────────────────────────────────────

_HISTORY_FILE = None


def _history_path(workspace: str) -> str:
    return os.path.join(workspace, ".analogy_history.json")


def _load_history(workspace: str) -> dict:
    p = _history_path(workspace)
    if os.path.exists(p):
        try:
            return json.loads(Path(p).read_text())
        except Exception:
            pass
    return {"domains_used": [], "videos": []}


def _save_history(workspace: str, history: dict) -> None:
    Path(_history_path(workspace)).write_text(json.dumps(history, indent=2))


def _recent_domains(workspace: str, n_videos: int = 3) -> list[str]:
    """Return analogy domains used in the last n_videos."""
    h = _load_history(workspace)
    recent = h.get("videos", [])[-n_videos:]
    domains = []
    for v in recent:
        domains.extend(v.get("domains", []))
    return list(set(domains))


def _record_domains(workspace: str, job_id: str, domains: list[str]) -> None:
    h = _load_history(workspace)
    h.setdefault("videos", []).append({"job_id": job_id, "domains": domains})
    # Keep only last 20 videos
    h["videos"] = h["videos"][-20:]
    _save_history(workspace, h)


# ── prompts ───────────────────────────────────────────────────────────────────

_DIVERGE_SYSTEM = """You are a creative educator who invents vivid teaching analogies.

For the concept and audience provided, propose:
- 5 analogies from 5 DIFFERENT everyday domains (e.g. kitchen, sport, farming,
  market, travel, weather, construction, nature, family, technology)
- 2 visual metaphors (not story analogies — things that can be DRAWN)

For each analogy/metaphor provide:
  - domain: one word (kitchen, sport, etc.)
  - analogy: one clear sentence
  - mapping: list of 3+ pairs {"source": "...", "target": "..."}
  - breaks_at: one sentence where the analogy fails or misleads
  - visual_idea: how to draw it in one sentence

Avoid these clichés: {cliches}
Avoid these recently used domains: {recent_domains}
Prefer domains familiar to this audience: {audience}

Return ONLY valid JSON — no markdown:
{{"analogies": [
  {{"domain":"...", "analogy":"...",
    "mapping":[{{"source":"...","target":"..."}}],
    "breaks_at":"...", "visual_idea":"..."}}
]}}"""

_SELECT_SYSTEM = """You are a strict, kind teacher evaluating teaching analogies.

Score each analogy 1-5 on:
  accuracy (does it teach the concept correctly?),
  familiarity (will the audience know the source domain?),
  visualisability (can it be drawn simply in a diagram?),
  memorability (is it surprising or sticky?),
  novelty (is it fresh, not a cliché?)

Reject any analogy where accuracy < 4 (it would teach something wrong).
Choose the one with the highest total score where accuracy >= 4.

Then state: the most likely way a learner would be misled by the chosen analogy,
and how the narration should prevent that.

Return ONLY valid JSON:
{{"chosen_index": 0,
  "scores": [{{"accuracy":4,"familiarity":4,"visualisability":3,"memorability":4,"novelty":3}}],
  "mislead_risk": "...",
  "narration_fix": "..."}}"""


# ── rules-based fallback ──────────────────────────────────────────────────────

_DOMAIN_TEMPLATES = {
    "kitchen": {
        "template": "Like a {kitchen_item} that {kitchen_action}, {concept} {concept_action}.",
        "domain": "kitchen",
    },
    "filter": {
        "template": "{concept} works like a filter — only certain things pass through.",
        "domain": "filter",
    },
    "garden": {
        "template": "Like growing a garden, {concept} needs the right conditions to thrive.",
        "domain": "garden",
    },
    "traffic": {
        "template": "Like traffic on a road, {concept} moves faster when there are fewer obstacles.",
        "domain": "traffic",
    },
    "defence": {
        "template": "Like a shield that blocks attacks, {concept} protects against harm.",
        "domain": "defence",
    },
}


def _rules_analogy(concept: dict, audience: str, used_domains: list[str]) -> dict:
    """Generate a simple rules-based analogy when LLM unavailable."""
    name   = concept.get("name", "this concept")
    defn   = concept.get("plain_definition", "")

    # Pick a domain not recently used
    for domain, tmpl in _DOMAIN_TEMPLATES.items():
        if domain not in used_domains:
            break
    else:
        domain = "filter"

    analogy_text = f"{name} is like a protective shield — it blocks harmful things from reaching you, just as {defn.lower()}"

    return {
        "concept_id":    concept.get("id", "c1"),
        "concept_name":  name,
        "domain":        domain,
        "analogy":       analogy_text,
        "mapping":       [
            {"source": "shield",    "target": name},
            {"source": "attacker",  "target": "the harmful factor"},
            {"source": "protected", "target": "the person or thing being helped"},
        ],
        "breaks_at":     "Unlike a physical shield, this cannot be seen or held — it works through behaviour or biology.",
        "visual_idea":   f"Draw a shield labelled '{name}' deflecting arrows labelled with the harmful factor.",
        "mislead_risk":  "Learners may think the protection is absolute.",
        "narration_fix": "Clarify that no protection is 100% — it significantly reduces risk but does not eliminate it.",
        "scores": {"accuracy": 4, "familiarity": 4, "visualisability": 4,
                   "memorability": 3, "novelty": 3},
        "_fallback": True,
    }


# ── LLM-based analogy ─────────────────────────────────────────────────────────

def _llm_analogy(concept: dict, audience: str, used_domains: list[str],
                 cliches: list[str]) -> dict:
    from aivideo.llm import call

    name = concept.get("name", "")
    defn = concept.get("plain_definition", "")

    # DIVERGE
    diverge_msg = [{
        "role": "user",
        "content": (
            f"Concept: {name}\n"
            f"Definition: {defn}\n"
            f"Audience: {audience}\n"
            f"Why it matters: {concept.get('why_it_matters','')}"
        )
    }]
    system_div = _DIVERGE_SYSTEM.format(
        cliches=", ".join(cliches[:20]),
        recent_domains=", ".join(used_domains[:6]) or "none",
        audience=audience,
    )
    div_result = call("analogy_diverge", system_div, diverge_msg,
                      max_tokens=2000)
    analogies = div_result.get("analogies", [])

    if not analogies:
        return _rules_analogy(concept, audience, used_domains)

    # Filter: at least 3 mappings, not in used_domains
    valid = [a for a in analogies
             if len(a.get("mapping", [])) >= 3
             and a.get("domain", "") not in used_domains]
    if not valid:
        valid = [a for a in analogies if len(a.get("mapping", [])) >= 3]
    if not valid:
        valid = analogies

    # SELECT + CRITIQUE
    select_msg = [{
        "role": "user",
        "content": (
            f"Concept: {name}\nAudience: {audience}\n\n"
            f"Analogies:\n{json.dumps(valid, indent=2)}"
        )
    }]
    sel_result = call("analogy_select", _SELECT_SYSTEM, select_msg,
                      max_tokens=800)

    chosen_idx  = sel_result.get("chosen_index", 0)
    scores_list = sel_result.get("scores", [{}])
    chosen      = valid[min(chosen_idx, len(valid) - 1)]
    scores      = scores_list[min(chosen_idx, len(scores_list) - 1)] if scores_list else {}

    return {
        "concept_id":    concept.get("id", ""),
        "concept_name":  name,
        "domain":        chosen.get("domain", ""),
        "analogy":       chosen.get("analogy", ""),
        "mapping":       chosen.get("mapping", []),
        "breaks_at":     chosen.get("breaks_at", ""),
        "visual_idea":   chosen.get("visual_idea", ""),
        "mislead_risk":  sel_result.get("mislead_risk", ""),
        "narration_fix": sel_result.get("narration_fix", ""),
        "scores":        scores,
    }


# ── public entry point ────────────────────────────────────────────────────────

def generate_analogies(analysis: dict, outdir: str,
                       workspace: Optional[str] = None,
                       job_id: Optional[str] = "job") -> dict:
    """Generate analogies for abstract concepts and write 02_creative.json.

    analysis:  output of analyze()
    outdir:    job directory
    workspace: root dir for cross-job history (defaults to parent of outdir)
    """
    workspace = workspace or os.path.dirname(outdir) or "."
    cliches   = _load_cliches()

    # Concepts qualifying for analogy generation (abstractness >= 3)
    concepts  = analysis.get("concepts", [])
    abstract  = [c for c in concepts if c.get("abstractness", 3) >= 3]
    if not abstract:
        abstract = concepts[:3]   # always do at least some

    audience      = analysis.get("audience", "general learners")
    used_domains  = _recent_domains(workspace)
    video_domains = []
    analogies_out = []

    for concept in abstract[:6]:   # max 6 to control cost
        # Domain uniqueness within this video
        try:
            if os.environ.get("MOCK_LLM", "0") == "1":
                result = _rules_analogy(concept, audience, used_domains + video_domains)
                result["_mock"] = True
            else:
                result = _llm_analogy(concept, audience,
                                      used_domains + video_domains, cliches)
        except Exception as e:
            print(f"[analogies] LLM failed for {concept.get('name','')} ({e}), using rules.")
            result = _rules_analogy(concept, audience, used_domains + video_domains)
            result["_fallback"] = True

        domain = result.get("domain", "")
        if domain and domain not in video_domains:
            video_domains.append(domain)

        analogies_out.append(result)

    _record_domains(workspace, job_id, video_domains)

    output = {
        "topic":     analysis.get("topic", ""),
        "audience":  audience,
        "analogies": analogies_out,
        "domains_used_this_video": video_domains,
    }

    os.makedirs(outdir, exist_ok=True)
    out_path = os.path.join(outdir, "02_creative.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"[analogies] {len(analogies_out)} analogies, "
          f"domains: {video_domains} → {out_path}")
    return output
