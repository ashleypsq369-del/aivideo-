"""Visual type chooser — Section 5.4 of the guide.

Maps content shape to one of 14 visual types, each with a trusted renderer
in assets.py. The decision table is code, not a coin toss.

Rule: no two consecutive scenes may share a visual type unless the type is
      'statement' or 'quiz'.
"""

from typing import Optional


# ── decision table ────────────────────────────────────────────────────────────
# (content_keywords, scene_kind_hint) -> visual_type
# Evaluated top-to-bottom; first match wins.

_RULES: list[tuple[list[str], str, str]] = [
    # keywords in title/bullets,  scene kind,   visual_type
    (["step", "process", "how to", "procedure", "workflow", "stage", "phase", "method", "first", "then", "finally", "next"],
     "any",        "process_flow"),
    (["cycle", "loop", "lifecycle", "circular", "repeat", "rotation", "revolv"],
     "any",        "cycle"),
    (["versus", "vs ", "compare", "difference", "contrast", "unlike", "similar", "both", "whereas"],
     "any",        "comparison"),
    (["year", "century", "history", "timeline", "evolution", "development", "age of", "era", "period", "since"],
     "any",        "timeline"),
    (["cause", "effect", "leads to", "because", "therefore", "result", "consequence", "due to"],
     "any",        "cause_effect"),
    (["tree", "hierarchy", "classify", "category", "type of", "kind of", "subcategor"],
     "any",        "tree"),
    (["percent", "%", "million", "billion", "thousand", "rate", "statistic", "data", "figure", "number", "measure"],
     "any",        "chart_bar"),
    (["trend", "over time", "increase", "decrease", "grow", "decline", "rise", "fall", "change"],
     "any",        "chart_line"),
    (["atom", "electron", "proton", "nucleus", "molecule", "element", "periodic", "orbital"],
     "any",        "atom_orbital"),
    (["body", "organ", "brain", "heart", "lung", "blood", "cell", "anatomy", "tissue", "nerve"],
     "any",        "annotated_body"),
    (["check", "prevent", "protect", "must", "should", "recommend", "action", "step to", "ensure"],
     "any",        "checklist"),
    (["analogy", "like a", "similar to", "imagine", "think of", "just as"],
     "any",        "analogy_split"),
    (["key fact", "important", "remember", "critical", "essential", "definition", "means"],
     "any",        "statement"),
    (["connect", "relate", "link", "network", "relationship", "between", "concept", "idea", "map"],
     "any",        "concept_map"),
]

# Icon-based routing (fallback when keywords don't match)
_ICON_MAP: dict[str, str] = {
    "health":  "annotated_body",
    "science": "atom_orbital",
    "money":   "chart_bar",
    "code":    "process_flow",
    "globe":   "concept_map",
    "people":  "concept_map",
    "idea":    "concept_map",
    "warning": "cause_effect",
    "check":   "checklist",
    "book":    "timeline",
}

# Scene kind overrides
_KIND_MAP: dict[str, str] = {
    "title":     "statement",
    "quiz":      "quiz",
    "flashcard": "checklist",
    "summary":   "concept_map",
}


def choose_visual(scene_title: str,
                  scene_bullets: list[str],
                  scene_kind: str = "bullets",
                  scene_icon: str = "book",
                  analogy: Optional[dict] = None,
                  prev_visual_type: Optional[str] = None) -> tuple[str, dict]:
    """Choose the best visual type and return (visual_type, spec_hint).

    spec_hint is a partial spec dict passed to assets.make_visual().
    The caller (storyboard / pipeline) fills in the actual data values.

    consecutive_check: if chosen type == prev_visual_type and type is not
    'statement' or 'quiz', rotate to concept_map as a safe fallback.
    """
    # Kind overrides first
    if scene_kind in _KIND_MAP:
        vt = _KIND_MAP[scene_kind]
        return vt, {"_chosen_by": "kind_map"}

    combined = (scene_title + " " + " ".join(scene_bullets)).lower()

    # If we have an analogy, prefer analogy_split for abstract scenes
    if analogy and not analogy.get("_fallback"):
        vt = "analogy_split"
        spec = {
            "familiar_label": analogy.get("domain", "Familiar idea").title(),
            "familiar_items": [m["source"] for m in analogy.get("mapping", [])[:5]],
            "target_label":   analogy.get("concept_name", scene_title)[:20],
            "target_items":   [m["target"] for m in analogy.get("mapping", [])[:5]],
            "_chosen_by":     "analogy",
        }
        return _dedupe(vt, prev_visual_type), spec

    # Keyword rules
    for keywords, kind_hint, vt in _RULES:
        if kind_hint != "any" and scene_kind != kind_hint:
            continue
        if any(kw in combined for kw in keywords):
            return _dedupe(vt, prev_visual_type), {"_chosen_by": "keyword", "_matched": keywords[0]}

    # Icon fallback
    if scene_icon in _ICON_MAP:
        vt = _ICON_MAP[scene_icon]
        return _dedupe(vt, prev_visual_type), {"_chosen_by": "icon"}

    # Ultimate fallback
    return "concept_map", {"_chosen_by": "default"}


def _dedupe(vt: str, prev: Optional[str]) -> str:
    """Avoid two consecutive scenes with the same visual type."""
    ALLOW_REPEAT = {"statement", "quiz"}
    if vt == prev and vt not in ALLOW_REPEAT:
        return "concept_map"
    return vt


def assign_visuals(scenes: list[dict], analogies: list[dict]) -> list[dict]:
    """Assign a visual_type and spec_hint to every scene dict.

    scenes:    list of scene dicts (from storyboard or planner)
    analogies: list of analogy dicts from creative/analogies.py

    Returns scenes with 'visual_type' and 'visual_spec_hint' added.
    """
    # Build concept_id -> analogy lookup
    analogy_map: dict[str, dict] = {}
    for a in analogies:
        cid = a.get("concept_id", "")
        if cid:
            analogy_map[cid] = a

    prev_vt = None
    result  = []
    for scene in scenes:
        kind    = scene.get("kind",    "bullets")
        title   = scene.get("title",   "")
        bullets = scene.get("bullets", [])
        icon    = scene.get("icon",    "book")

        # Find the best matching analogy for this scene
        analogy = None
        for cid in scene.get("concept_ids", []):
            if cid in analogy_map:
                analogy = analogy_map[cid]
                break

        vt, spec = choose_visual(title, bullets, kind, icon, analogy, prev_vt)

        scene = dict(scene)   # don't mutate caller's dict
        scene["visual_type"]      = vt
        scene["visual_spec_hint"] = spec
        result.append(scene)
        prev_vt = vt

    return result
