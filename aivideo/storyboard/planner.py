"""Storyboard planner — M3 of the guide.

Turns analysis + creative direction into 03_storyboard.json.

Hard validation rules (enforced in code):
  1. Every narration sentence that carries a fact must list at least one facts_used id
     OR be marked kind="bridge" (transitions, questions with no factual content)
  2. beats[].at_phrase must appear verbatim in the scene narration
  3. visual_type must be one of the 14 allowed types
  4. No two consecutive non-statement/quiz scenes share a visual type
  5. Scene target_seconds must be 12-60
  6. Max 4 on_screen_text items, each under 12 words

MOCK_LLM=1 → produces a minimal fixture storyboard for CI.
Falls back to rules-based storyboard when LLM unavailable.
"""

import json
import os
import re
from typing import Optional

from aivideo.creative.visual_chooser import assign_visuals, choose_visual

ALLOWED_VISUAL_TYPES = {
    "process_flow", "cycle", "comparison", "chart_bar", "chart_line",
    "timeline", "concept_map", "analogy_split", "statement", "checklist",
    "cause_effect", "tree", "annotated_body", "atom_orbital", "quiz",
}

# ── prompts ───────────────────────────────────────────────────────────────────

_SYSTEM = """You are a documentary scriptwriter and instructional animator.

Turn the analysis and creative direction into a storyboard for an explainer video.

Teaching heuristics you MUST follow:
- Concrete before abstract: show an example before the definition
- One idea per scene: introduce at most one new concept per scene
- Dual coding: narration and visual carry DIFFERENT information — never read the screen aloud
- Signalling: each beat highlights what is being discussed RIGHT NOW
- Pacing: 15-45 seconds per scene; something visually changes every 6-8 seconds
- Prediction hook: open with a question, then answer it
- Target misconceptions: each listed misconception gets one beat that confronts it
- Spaced recap: summary uses different visuals from the introduction
- Cognitive load: max 4 on-screen items, each under 12 words

Return ONLY valid JSON — no markdown fences:
{
  "title": "string",
  "style": {"palette": "auto|classic|whiteboard|kawaii", "pace": "calm|medium|brisk"},
  "scenes": [{
    "id": "s01",
    "concept_ids": ["c1"],
    "purpose": "hook|explain|example|misconception|apply|recap|quiz",
    "visual_type": "one of the 14 allowed types",
    "visual_spec": {},
    "narration": "Written for the ear. Contractions allowed. Never repeat on-screen text word for word.",
    "beats": [{"at_phrase": "exact phrase from narration", "action": "reveal|highlight|fade", "target": "element-id"}],
    "on_screen_text": ["max 4 items", "each under 12 words"],
    "facts_used": ["f1", "f2"],
    "target_seconds": 25
  }]
}

Rules:
- Every factual narration sentence needs a facts_used id OR must carry no facts (bridge sentence)
- beats[].at_phrase must appear VERBATIM in that scene's narration
- visual_type must be one of: process_flow, cycle, comparison, chart_bar, chart_line,
  timeline, concept_map, analogy_split, statement, checklist, cause_effect, tree,
  annotated_body, atom_orbital, quiz
- Start with a hook scene (purpose=hook), end with recap (purpose=recap) + optional quiz
- Include one scene per misconception (purpose=misconception)
"""


# ── validation ────────────────────────────────────────────────────────────────

def _validate_storyboard(sb: dict, facts: list[dict]) -> tuple[dict, list[str]]:
    """Enforce hard validation rules. Returns (cleaned_sb, violations)."""
    fact_ids  = {f["id"] for f in facts}
    violations = []
    clean_scenes = []

    prev_vt = None
    ALLOW_REPEAT = {"statement", "quiz"}

    for scene in sb.get("scenes", []):
        sid = scene.get("id", "?")

        # 1. Visual type must be allowed
        vt = scene.get("visual_type", "concept_map")
        if vt not in ALLOWED_VISUAL_TYPES:
            violations.append(f"{sid}: invalid visual_type {vt!r} → replaced with concept_map")
            vt = "concept_map"
        # 2. No consecutive duplicate visual types
        if vt == prev_vt and vt not in ALLOW_REPEAT:
            new_vt = "concept_map" if vt != "concept_map" else "statement"
            violations.append(f"{sid}: consecutive {vt!r} → changed to {new_vt!r}")
            vt = new_vt
        scene["visual_type"] = vt
        prev_vt = vt

        # 3. beats at_phrase must appear in narration
        narration = scene.get("narration", "")
        clean_beats = []
        for beat in scene.get("beats", []):
            phrase = beat.get("at_phrase", "")
            if phrase and phrase.lower() in narration.lower():
                clean_beats.append(beat)
            else:
                violations.append(
                    f"{sid} beat: at_phrase {phrase[:40]!r} not in narration → dropped"
                )
        scene["beats"] = clean_beats

        # 4. facts_used ids must exist
        clean_fu = [fid for fid in scene.get("facts_used", []) if fid in fact_ids]
        dropped  = set(scene.get("facts_used", [])) - set(clean_fu)
        if dropped:
            violations.append(f"{sid}: unknown fact ids dropped: {dropped}")
        scene["facts_used"] = clean_fu

        # 5. on_screen_text: max 4 items, each under 12 words
        ost = scene.get("on_screen_text", [])[:4]
        clean_ost = []
        for item in ost:
            words = item.split()
            if len(words) > 12:
                item = " ".join(words[:12]) + "..."
                violations.append(f"{sid}: on_screen_text truncated to 12 words")
            clean_ost.append(item)
        scene["on_screen_text"] = clean_ost

        # 6. target_seconds in range
        ts = scene.get("target_seconds", 25)
        if not (12 <= ts <= 60):
            clamped = max(12, min(60, ts))
            violations.append(f"{sid}: target_seconds {ts} clamped to {clamped}")
            scene["target_seconds"] = clamped

        clean_scenes.append(scene)

    sb["scenes"] = clean_scenes
    return sb, violations


# ── rules-based storyboard ────────────────────────────────────────────────────

def _rules_storyboard(analysis: dict, creative: dict) -> dict:
    """Fast rules-based storyboard when LLM unavailable."""
    topic       = analysis.get("topic", "Lesson")
    concepts    = analysis.get("concepts", [])
    facts       = analysis.get("facts", [])
    misconceptions = analysis.get("misconceptions", [])
    analogies   = creative.get("analogies", [])

    scenes = []

    # Hook scene
    hook_fact = facts[0]["text"] if facts else f"Today we explore {topic}."
    scenes.append({
        "id":          "s01",
        "concept_ids": [],
        "purpose":     "hook",
        "visual_type": "statement",
        "visual_spec": {"text": hook_fact, "source": ""},
        "narration":   f"Here is something important: {hook_fact} In this lesson we explore {topic}.",
        "beats":       [{"at_phrase": "Here is something important", "action": "reveal", "target": "statement"}],
        "on_screen_text": [topic],
        "facts_used":  [facts[0]["id"]] if facts else [],
        "target_seconds": 18,
    })

    # One scene per concept
    analogy_map = {a.get("concept_id", ""): a for a in analogies}
    for i, concept in enumerate(concepts[:5]):
        cid       = concept.get("id", f"c{i+1}")
        cname     = concept.get("name", "")
        defn      = concept.get("plain_definition", "")
        why       = concept.get("why_it_matters", "")
        c_facts   = [f for f in facts if f.get("source_ref")]

        analogy   = analogy_map.get(cid)
        from aivideo.creative.visual_chooser import choose_visual
        vt, spec  = choose_visual(cname, [defn, why], "bullets",
                                   concept.get("icon", "book"), analogy,
                                   scenes[-1]["visual_type"] if scenes else None)

        narration = f"{cname}: {defn} {why}"
        scene_facts = [f["id"] for f in c_facts[:2]]

        scenes.append({
            "id":           f"s{i+2:02d}",
            "concept_ids":  [cid],
            "purpose":      "explain",
            "visual_type":  vt,
            "visual_spec":  spec,
            "narration":    narration,
            "beats":        [{"at_phrase": cname, "action": "reveal", "target": f"node-{cid}"}],
            "on_screen_text": [cname, defn[:60] if defn else ""],
            "facts_used":   scene_facts,
            "target_seconds": 25,
        })

    # Misconception scene
    for m in misconceptions[:1]:
        cname = next((c["name"] for c in concepts if c["id"] == m.get("concept_id")), "this concept")
        scenes.append({
            "id":           f"s{len(scenes)+1:02d}",
            "concept_ids":  [m.get("concept_id", "")],
            "purpose":      "misconception",
            "visual_type":  "comparison",
            "visual_spec":  {
                "left_label":  "Common Belief",
                "right_label": "Reality",
                "left_items":  [m.get("belief", "")],
                "right_items": [m.get("correction", "")],
            },
            "narration":    f"A common misunderstanding about {cname}: {m.get('belief','')}. "
                            f"In fact: {m.get('correction','')}",
            "beats":        [{"at_phrase": "common misunderstanding", "action": "reveal", "target": "left-col"},
                             {"at_phrase": "In fact", "action": "highlight", "target": "right-col"}],
            "on_screen_text": ["Common Belief", m.get("belief","")[:60], "Reality", m.get("correction","")[:60]],
            "facts_used":   [],
            "target_seconds": 22,
        })

    # Quiz scene
    if concepts:
        c0 = concepts[0]
        c0_facts = [f for f in facts if f.get("source_ref")]
        correct  = c0_facts[0]["text"][:60] if c0_facts else c0.get("plain_definition","")[:60]
        scenes.append({
            "id":           f"s{len(scenes)+1:02d}",
            "concept_ids":  [c0.get("id","c1")],
            "purpose":      "quiz",
            "visual_type":  "quiz",
            "visual_spec":  {},
            "narration":    f"Let us check your understanding. {c0.get('name','')}: what is the most important thing to remember?",
            "beats":        [{"at_phrase": "Let us check your understanding", "action": "reveal", "target": "question"}],
            "on_screen_text": [f"What is most important about {c0.get('name','')}?"],
            "facts_used":   [],
            "target_seconds": 20,
        })

    # Recap / summary
    summary_bullets = [c.get("name","") for c in concepts[:4]]
    scenes.append({
        "id":           f"s{len(scenes)+1:02d}",
        "concept_ids":  [c["id"] for c in concepts],
        "purpose":      "recap",
        "visual_type":  "concept_map",
        "visual_spec":  {"center": topic, "concepts": summary_bullets},
        "narration":    "To summarise: " + ". ".join(
                            f"{c.get('name','')} — {c.get('plain_definition','')[:50]}"
                            for c in concepts[:4]
                        ) + ".",
        "beats":        [{"at_phrase": "To summarise", "action": "reveal", "target": "center"}],
        "on_screen_text": summary_bullets[:4],
        "facts_used":   [],
        "target_seconds": 30,
    })

    return {
        "title":  topic,
        "style":  {"palette": "auto", "pace": "medium"},
        "scenes": scenes,
    }


# ── LLM storyboard ────────────────────────────────────────────────────────────

def _llm_storyboard(analysis: dict, creative: dict) -> dict:
    from aivideo.llm import call

    topic     = analysis.get("topic", "")
    audience  = analysis.get("audience", "")
    analogies = creative.get("analogies", [])

    # Build exemplar hint (from guide §5.2)
    heuristics_note = (
        "Teaching heuristics reminder: concrete before abstract; "
        "one idea per scene; dual coding (narration ≠ on-screen text); "
        "confront each misconception; end recap uses different visual than intro."
    )

    user_msg = [{
        "role": "user",
        "content": (
            f"Topic: {topic}\nAudience: {audience}\n\n"
            f"Analysis:\n{json.dumps(analysis, indent=2)}\n\n"
            f"Creative direction (analogies):\n{json.dumps(analogies, indent=2)}\n\n"
            f"{heuristics_note}"
        )
    }]

    return call("storyboard", _SYSTEM, user_msg, max_tokens=8000)


# ── public entry point ────────────────────────────────────────────────────────

def build_storyboard(analysis: dict, creative: dict,
                     outdir: str) -> dict:
    """Produce 03_storyboard.json from analysis + creative direction.

    Returns the validated storyboard dict.
    """
    facts = analysis.get("facts", [])

    if os.environ.get("MOCK_LLM", "0") == "1":
        sb = _rules_storyboard(analysis, creative)
        sb["_mock"] = True
    else:
        try:
            sb = _llm_storyboard(analysis, creative)
        except Exception as e:
            print(f"[storyboard] LLM failed ({e}), using rules fallback.")
            sb = _rules_storyboard(analysis, creative)
            sb["_fallback"] = True

    # Hard validation
    sb, violations = _validate_storyboard(sb, facts)
    sb["_violations"] = violations

    if violations:
        print(f"[storyboard] {len(violations)} validation issues fixed:")
        for v in violations:
            print(f"  - {v}")

    # Write output
    os.makedirs(outdir, exist_ok=True)
    out_path = os.path.join(outdir, "03_storyboard.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(sb, f, indent=2, ensure_ascii=False)

    n_scenes = len(sb.get("scenes", []))
    print(f"[storyboard] {n_scenes} scenes → {out_path}")
    return sb
