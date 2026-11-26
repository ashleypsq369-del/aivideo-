from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class Scene:
    kind: str          # "title" | "bullets" | "quiz" | "summary" | "flashcard" | "dialogue"
    title: str
    bullets: list = field(default_factory=list)
    narration: str = ""
    icon: str = "book"
    # quiz-only
    question: str = ""
    options: list = field(default_factory=list)
    answer_index: int = 0
    # dialogue-only (two-host audio)
    dialogue: list = field(default_factory=list)   # [{"host": "A"|"B", "text": str}, ...]
    # flashcard-only
    flashcards: list = field(default_factory=list) # [{"front": str, "back": str}, ...]
    # extra metadata
    takeaway: str = ""   # one-sentence key insight per scene

    def to_dict(self):
        return asdict(self)


@dataclass
class ScenePlan:
    topic: str
    scenes: list
    format: str = "deep_dive"   # deep_dive | brief | critique | debate
    length: str = "default"     # short | default | long
    language: str = "en"
    focus: str = ""             # user focus prompt

    def to_dict(self):
        return {
            "topic": self.topic,
            "format": self.format,
            "length": self.length,
            "language": self.language,
            "focus": self.focus,
            "scenes": [s.to_dict() for s in self.scenes],
        }

    @staticmethod
    def from_dict(d):
        return ScenePlan(
            topic=d["topic"],
            scenes=[Scene(**s) for s in d["scenes"]],
            format=d.get("format", "deep_dive"),
            length=d.get("length", "default"),
            language=d.get("language", "en"),
            focus=d.get("focus", ""),
        )
