from dataclasses import dataclass, field, asdict


@dataclass
class Scene:
    kind: str                      # "title" | "bullets" | "quiz" | "summary"
    title: str
    bullets: list = field(default_factory=list)
    narration: str = ""
    icon: str = "book"
    # quiz-only
    question: str = ""
    options: list = field(default_factory=list)
    answer_index: int = 0

    def to_dict(self):
        return asdict(self)


@dataclass
class ScenePlan:
    topic: str
    scenes: list

    def to_dict(self):
        return {"topic": self.topic, "scenes": [s.to_dict() for s in self.scenes]}

    @staticmethod
    def from_dict(d):
        return ScenePlan(d["topic"], [Scene(**s) for s in d["scenes"]])
