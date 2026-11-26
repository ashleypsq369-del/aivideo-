"""Turn lesson text into a ScenePlan.

Formats: deep_dive | brief | critique | debate
Lengths: short | default | long
"""
import json
import os
import re
from collections import Counter

from .models import Scene, ScenePlan

STOPWORDS = set("""a an the and or but if then of to in on for with as at by from is are was were be been it its this
that these those can may will would should could not no so than too very into over under about between their there
which what when where who how also more most such other each many any some your you we our they them he she his
her""".split())

ICONS = {
    "book":    ["learn", "lesson", "study", "education", "read", "knowledge"],
    "health":  ["health", "disease", "malaria", "patient", "medical", "clinic", "care", "body"],
    "money":   ["money", "cost", "price", "budget", "finance", "income", "economy"],
    "science": ["science", "cell", "atom", "energy", "experiment", "research", "biology", "chemistry"],
    "code":    ["code", "software", "program", "data", "computer", "algorithm", "system"],
    "globe":   ["world", "country", "global", "africa", "ghana", "city", "region", "culture"],
    "people":  ["people", "community", "team", "family", "children", "student", "society"],
    "idea":    ["idea", "concept", "theory", "principle", "explain", "understand", "reason"],
    "warning": ["risk", "danger", "problem", "issue", "challenge", "threat", "cause"],
    "check":   ["solution", "answer", "result", "effect", "outcome", "prevent", "treat"],
}

LENGTH_SCENES  = {"short": 2, "default": 3, "long": 5}
LENGTH_BULLETS = {"short": 2, "default": 3, "long": 4}


def _sentences(text):
    text = re.sub(r"\s+", " ", text.strip())
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if len(s.strip()) > 3]


def _keywords(text, n=3):
    words = [w for w in re.findall(r"[A-Za-z][A-Za-z\-']+", text.lower())
             if w not in STOPWORDS and len(w) > 3]
    return [w for w, _ in Counter(words).most_common(n)]


def _icon_for(text):
    words = set(re.findall(r"[a-z]+", text.lower()))
    best, best_hits = "book", 0
    for icon, keys in ICONS.items():
        hits = sum(1 for k in keys if k in words)
        if hits > best_hits:
            best, best_hits = icon, hits
    return best


def _short_bullet(sentence, limit=90):
    sentence = sentence.rstrip(".!?")
    if len(sentence) <= limit:
        return sentence
    cut = sentence[:limit].rsplit(" ", 1)[0]
    return cut + "..."


def _takeaway(sentences):
    if not sentences:
        return ""
    scored = sorted(sentences, key=lambda s: len([w for w in s.lower().split()
                    if w not in STOPWORDS and len(w) > 3]), reverse=True)
    return scored[0].rstrip(".!?") + "."


def _make_flashcards(scenes):
    cards = []
    for s in scenes:
        if s.kind == "bullets" and s.bullets:
            q = "What is important about " + s.title + "?"
            a = s.bullets[0]
            cards.append({"front": q, "back": a})
            for b in s.bullets[1:]:
                words = b.split()
                if len(words) >= 5:
                    candidates = [(i, w) for i, w in enumerate(words)
                                  if w.lower() not in STOPWORDS and len(w) > 4]
                    if candidates:
                        idx, word = max(candidates, key=lambda x: len(x[1]))
                        blanked = words[:]
                        blanked[idx] = "______"
                        cards.append({"front": " ".join(blanked), "back": word})
    return cards


def _dialogue_snippet(title, narration, host_a="Alex", host_b="Jordan"):
    sents = _sentences(narration)
    if len(sents) < 2:
        return [{"host": "A", "name": host_a, "text": narration}]
    lines = []
    for i, s in enumerate(sents[:4]):
        host = "A" if i % 2 == 0 else "B"
        name = host_a if host == "A" else host_b
        if i == 1:
            s = "Right -- and what that really means is " + s[0].lower() + s[1:]
        elif i == 3:
            s = "So the key takeaway here is: " + s[0].lower() + s[1:]
        lines.append({"host": host, "name": name, "text": s})
    return lines


# -- Rules-based planners -------------------------------------------------------

def plan_deep_dive(text, topic, length="default"):
    sents = _sentences(text)
    if not sents:
        raise ValueError("No text to plan from.")
    kws   = _keywords(text, 3)
    topic = topic or (" ".join(w.capitalize() for w in kws[:2]) or "Lesson")
    spc   = LENGTH_SCENES.get(length, 3)
    bpc   = LENGTH_BULLETS.get(length, 3)

    scenes = [Scene(
        "title", topic, [],
        "Welcome. Today we explore " + topic + ". By the end you will understand the key ideas, "
        "why they matter, and how they connect.",
        _icon_for(text),
        takeaway="This lesson covers " + topic + ".",
        dialogue=_dialogue_snippet(topic,
            "Welcome. Today we explore " + topic + ". By the end you will understand the key ideas.")
    )]

    chunks = [sents[i:i + spc] for i in range(0, len(sents), spc)]
    for chunk in chunks:
        joined = " ".join(chunk)
        title  = " ".join(w.capitalize() for w in _keywords(joined, 2)) or topic
        bullets = [_short_bullet(s) for s in chunk[:bpc]]
        tk = _takeaway(chunk)
        scenes.append(Scene(
            "bullets", title, bullets, joined, _icon_for(joined),
            takeaway=tk,
            dialogue=_dialogue_snippet(title, joined)
        ))

    first   = scenes[1] if len(scenes) > 1 else scenes[0]
    correct = first.bullets[0] if first.bullets else first.title
    scenes.append(Scene(
        "quiz", "Knowledge Check", [],
        "Let us check your understanding of " + first.title + ".",
        "check",
        question="Which statement best describes " + first.title + "?",
        options=[correct, "None of the above", "It is unrelated to " + topic],
        answer_index=0,
        takeaway="Testing yourself improves retention by up to 50%."
    ))

    cards = _make_flashcards(scenes)
    if cards:
        scenes.append(Scene(
            "flashcard", "Flashcards", [],
            "Here are " + str(len(cards)) + " flashcards to reinforce what you have learned.",
            "book",
            flashcards=cards,
            takeaway="Active recall strengthens long-term memory."
        ))

    content_scenes  = [s for s in scenes if s.kind == "bullets"]
    summary_bullets = [s.takeaway or s.title for s in content_scenes[:5]]
    scenes.append(Scene(
        "summary", "Summary",
        summary_bullets,
        "To summarise: " + ". ".join(summary_bullets[:4]) + ".",
        "book",
        takeaway="You now understand the core ideas of " + topic + ".",
        dialogue=_dialogue_snippet("Summary",
            "To summarise: " + ". ".join(summary_bullets[:4]) + ".")
    ))
    return ScenePlan(topic, scenes, format="deep_dive", length=length)


def plan_brief(text, topic, length="short"):
    sents = _sentences(text)
    kws   = _keywords(text, 3)
    topic = topic or (" ".join(w.capitalize() for w in kws[:2]) or "Lesson")
    core_sents   = sents[1:4] if len(sents) > 3 else sents[1:]
    core_text    = " ".join(core_sents)
    takeaway_text = sents[-1] if len(sents) > 1 else sents[0]
    scenes = [
        Scene("title", topic, [], "Here is what you need to know about " + topic + " -- fast.",
              _icon_for(text), takeaway="Quick overview of " + topic + "."),
        Scene("bullets", "The Core Idea", [_short_bullet(s) for s in core_sents[:3]],
              core_text, _icon_for(core_text), takeaway=_takeaway(core_sents)),
        Scene("summary", "The One Thing to Remember", [_short_bullet(takeaway_text)],
              "If you remember one thing: " + takeaway_text,
              "check", takeaway=takeaway_text),
    ]
    return ScenePlan(topic, scenes, format="brief", length=length)


def plan_critique(text, topic, length="default"):
    sents = _sentences(text)
    kws   = _keywords(text, 3)
    topic = topic or (" ".join(w.capitalize() for w in kws[:2]) or "Lesson")
    strong = [s for s in sents if len(s.split()) >= 8][:3]
    gaps   = [s for s in sents if len(s.split()) < 8][:3]
    scenes = [
        Scene("title", "Critique: " + topic, [],
              "Let us examine this material on " + topic + " -- what it does well and where it could go deeper.",
              "idea", takeaway="A critical look at " + topic + "."),
        Scene("bullets", "Strengths",
              [_short_bullet(s) for s in strong] or ["Clear and direct language.", "Covers the core topic."],
              "This material handles these points well: " + " ".join(strong[:2]),
              "check", takeaway="Good content builds on these foundations."),
        Scene("bullets", "Gaps and Questions",
              [_short_bullet(s) for s in gaps] or ["Could include more examples.", "Data sources not cited."],
              "However, a critical reader would ask: " + " ".join(gaps[:2]),
              "warning", takeaway="Every strong argument should anticipate counter-questions."),
        Scene("bullets", "Suggestions",
              ["Add concrete examples or data.", "Define key terms explicitly.",
               "Show cause-and-effect relationships.", "Link to real-world outcomes."],
              "To strengthen this material, consider adding evidence, examples, and explicit reasoning chains.",
              "idea", takeaway="Better explanations show the why, not just the what."),
        Scene("summary", "Verdict",
              ["Coverage of " + topic + ": solid foundation.",
               "Depth: could go further with evidence.",
               "Clarity: well-structured, needs examples."],
              "Overall: a useful introduction to " + topic + " that would benefit from deeper evidence.",
              "book", takeaway="Good start on " + topic + "; deepen with evidence and examples."),
    ]
    return ScenePlan(topic, scenes, format="critique", length=length)


def plan_debate(text, topic, length="default"):
    sents = _sentences(text)
    kws   = _keywords(text, 3)
    topic = topic or (" ".join(w.capitalize() for w in kws[:2]) or "Lesson")
    pro = [s for s in sents if any(w in s.lower() for w in
           ["prevent", "treat", "help", "reduce", "safe", "good", "benefit", "improve"])]
    con = [s for s in sents if any(w in s.lower() for w in
           ["risk", "danger", "spread", "affect", "cause", "problem", "issue", "challenge"])]
    if not pro: pro = sents[:len(sents)//2]
    if not con: con  = sents[len(sents)//2:]
    scenes = [
        Scene("title", "Debate: " + topic, [],
              "Two perspectives on " + topic + ". Both sides make important points.",
              "idea", takeaway="Debate reveals the full complexity of " + topic + "."),
        Scene("bullets", "The Case For",
              [_short_bullet(s) for s in pro[:4]],
              "On one side: " + " ".join(pro[:3]),
              "check", takeaway=_takeaway(pro) if pro else "Solutions exist.",
              dialogue=[{"host": "A", "name": "Alex",
                         "text": "The evidence strongly supports action here. " + (pro[0] if pro else "")}]),
        Scene("bullets", "The Case Against",
              [_short_bullet(s) for s in con[:4]],
              "On the other side: " + " ".join(con[:3]),
              "warning", takeaway=_takeaway(con) if con else "Challenges remain.",
              dialogue=[{"host": "B", "name": "Jordan",
                         "text": "But we cannot ignore the harder reality. " + (con[0] if con else "")}]),
        Scene("summary", "Synthesis",
              ["Both perspectives contain truth.",
               "Solutions require understanding the full problem.",
               "The real question: what does " + topic + " demand of us?"],
              "The truth about " + topic + " lives in the tension between these views.",
              "book", takeaway="Nuanced understanding beats one-sided conclusions.",
              dialogue=[
                  {"host": "A", "name": "Alex",  "text": "So we agree -- it is not either-or, it is both-and."},
                  {"host": "B", "name": "Jordan", "text": "Exactly. The full picture is always more useful."}
              ]),
    ]
    return ScenePlan(topic, scenes, format="debate", length=length)


FORMAT_PLANNERS = {
    "deep_dive": plan_deep_dive,
    "brief":     plan_brief,
    "critique":  plan_critique,
    "debate":    plan_debate,
}

# -- Claude planner -------------------------------------------------------------

CLAUDE_SYSTEM = """You are an expert instructional designer and science communicator.
Turn lesson text into a smart, creative video scene plan. Be specific, insightful, and genuinely helpful.
Return ONLY valid JSON -- no markdown fences, no extra text:
{
  "topic": "str", "format": "deep_dive|brief|critique|debate",
  "length": "short|default|long", "language": "en", "focus": "str",
  "scenes": [{
    "kind": "title|bullets|quiz|summary|flashcard",
    "title": "str", "bullets": ["str"], "narration": "str",
    "icon": "book|health|money|science|code|globe|people|idea|warning|check",
    "question": "str", "options": ["str"], "answer_index": 0,
    "dialogue": [{"host": "A", "name": "str", "text": "str"}],
    "flashcards": [{"front": "str", "back": "str"}],
    "takeaway": "str"
  }]
}
Rules: narration explains WHY; bullets are specific facts; every scene has a takeaway."""


def plan_with_claude(text, topic=None, fmt="deep_dive", length="default", focus="", model=None):
    import anthropic
    client  = anthropic.Anthropic()
    user_msg = (
        f"Format: {fmt}\nLength: {length}\nTopic hint: {topic or 'derive from text'}\n"
        f"Focus: {focus or 'cover the most important ideas'}\n\nLesson text:\n{text}"
    )
    msg = client.messages.create(
        model=model or os.environ.get("AIVIDEO_MODEL", "claude-sonnet-4-5"),
        max_tokens=6000, system=CLAUDE_SYSTEM,
        messages=[{"role": "user", "content": user_msg}]
    )
    raw = "".join(b.text for b in msg.content if getattr(b, "text", None))
    raw = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.M).strip()
    return ScenePlan.from_dict(json.loads(raw))


# -- Public entry point ---------------------------------------------------------

def plan(text, topic=None, use_claude=False, fmt="deep_dive", length="default", focus=""):
    if use_claude and os.environ.get("ANTHROPIC_API_KEY"):
        try:
            return plan_with_claude(text, topic, fmt, length, focus)
        except Exception as e:
            print(f"[planner] Claude failed ({e}); falling back to rules.")
    planner_fn = FORMAT_PLANNERS.get(fmt, plan_deep_dive)
    return planner_fn(text, topic, length)

# Backwards-compat alias used by tests
def plan_with_rules(text, topic=None, length="default"):
    return plan_deep_dive(text, topic, length)
