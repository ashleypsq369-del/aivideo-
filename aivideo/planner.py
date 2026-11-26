"""Turn lesson text into a ScenePlan.

Two planners:
  * plan_with_rules  - offline, deterministic, no API key needed
  * plan_with_claude - structured JSON from Claude (needs ANTHROPIC_API_KEY)
"""
import json
import os
import re
from collections import Counter

from .models import Scene, ScenePlan

STOPWORDS = set("""a an the and or but if then of to in on for with as at by from is are was were be been it its this that
these those can may will would should could not no so than too very into over under about between their there which what
when where who how also more most such other each many any some your you we our they them he she his her""".split())

ICONS = {
    "book": ["learn", "lesson", "study", "education", "read"],
    "health": ["health", "disease", "malaria", "patient", "medical", "clinic", "care"],
    "money": ["money", "cost", "price", "budget", "finance", "income"],
    "science": ["science", "cell", "atom", "energy", "experiment", "research"],
    "code": ["code", "software", "program", "data", "computer", "algorithm"],
    "globe": ["world", "country", "global", "africa", "ghana", "city"],
    "people": ["people", "community", "team", "family", "children", "student"],
}


def _sentences(text):
    text = re.sub(r"\s+", " ", text.strip())
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if len(s.strip()) > 3]


def _keywords(text, n=3):
    words = [w for w in re.findall(r"[A-Za-z][A-Za-z\-']+", text.lower()) if w not in STOPWORDS and len(w) > 3]
    return [w for w, _ in Counter(words).most_common(n)]


def _icon_for(text):
    low = text.lower()
    for icon, keys in ICONS.items():
        if any(k in low for k in keys):
            return icon
    return "book"


def _short(sentence, limit=90):
    sentence = sentence.rstrip(".!?")
    if len(sentence) <= limit:
        return sentence
    cut = sentence[:limit].rsplit(" ", 1)[0]
    return cut + "..."


def plan_with_rules(text, topic=None, sentences_per_scene=3):
    sents = _sentences(text)
    if not sents:
        raise ValueError("No text to plan from.")
    kws = _keywords(text, 3)
    topic = topic or (" ".join(w.capitalize() for w in kws[:2]) or "Lesson")
    scenes = [Scene("title", topic, [], f"Welcome. In this lesson we will look at {topic}.", _icon_for(text))]

    chunks = [sents[i:i + sentences_per_scene] for i in range(0, len(sents), sentences_per_scene)]
    for chunk in chunks:
        joined = " ".join(chunk)
        title = " ".join(w.capitalize() for w in _keywords(joined, 2)) or topic
        scenes.append(Scene("bullets", title, [_short(s) for s in chunk], joined, _icon_for(joined)))

    # simple quiz from the first bullet scene
    first = scenes[1]
    scenes.append(Scene(
        "quiz", "Quick check", [],
        f"Quick check. Which of these is covered in the section on {first.title}?",
        "book", question=f"Which statement matches the section on {first.title}?",
        options=[first.bullets[0], "None of the above", "All of the above"], answer_index=0))
    scenes.append(Scene("summary", "Summary", [s.title for s in scenes[1:-1]][:4],
                        "To summarise, we covered " + ", ".join(s.title for s in scenes[1:-1][:4]) + ".", "book"))
    return ScenePlan(topic, scenes)


CLAUDE_SYSTEM = """You turn lesson text into a video scene plan. Return ONLY JSON, no markdown fences:
{"topic": str, "scenes": [{"kind": "title|bullets|quiz|summary", "title": str, "bullets": [str], "narration": str,
 "icon": "book|health|money|science|code|globe|people", "question": str, "options": [str], "answer_index": int}]}
Rules: max 4 bullets per scene, each under 90 characters; narration must not just repeat the bullets word for word;
use only facts from the lesson; start with a title scene, end with a summary; include one quiz scene."""


def plan_with_claude(text, topic=None, model=None):
    import anthropic
    client = anthropic.Anthropic()
    msg = client.messages.create(
        model=model or os.environ.get("AIVIDEO_MODEL", "claude-sonnet-4-5"),
        max_tokens=4000, system=CLAUDE_SYSTEM,
        messages=[{"role": "user", "content": f"Topic hint: {topic or 'none'}\n\nLesson:\n{text}"}])
    raw = "".join(b.text for b in msg.content if getattr(b, "text", None))
    raw = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.M).strip()
    return ScenePlan.from_dict(json.loads(raw))


def plan(text, topic=None, use_claude=False):
    if use_claude and os.environ.get("ANTHROPIC_API_KEY"):
        try:
            return plan_with_claude(text, topic)
        except Exception as e:  # fall back so the pipeline never dies on an API hiccup
            print(f"[planner] Claude planning failed ({e}); using rules.")
    return plan_with_rules(text, topic)
