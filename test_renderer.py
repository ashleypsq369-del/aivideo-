"""Test renderer.py — render one frame per scene type and verify output."""
import os, sys
os.environ["MOCK_LLM"] = "1"

from aivideo.slides import THEMES
from aivideo.renderer import (
    TitleRenderer, BulletsRenderer, QuizRenderer,
    SummaryRenderer, FlashcardRenderer
)
from aivideo.models import Scene

T = THEMES["auto"]

def make_scene(kind, title, bullets=None, narration="", icon="book",
               question="", options=None, answer_index=0,
               flashcards=None, takeaway=""):
    return Scene(
        kind=kind, title=title,
        bullets=bullets or [],
        narration=narration or f"This scene covers {title}.",
        icon=icon,
        question=question,
        options=options or [],
        answer_index=answer_index,
        flashcards=flashcards or [],
        takeaway=takeaway or f"Remember: {title} matters.",
    )

scenes = [
    make_scene("title", "The Human Immune System",
               narration="Your immune system is your body's defence network against disease.",
               icon="health", takeaway="The immune system protects you from pathogens."),
    make_scene("bullets", "How Immunity Works",
               bullets=["Innate immunity acts immediately",
                        "Adaptive immunity learns over 7-14 days",
                        "Memory cells last for decades",
                        "Vaccines train the adaptive immune system"],
               icon="health", takeaway="Two branches work together to defend you."),
    make_scene("bullets", "Key Statistics",
               bullets=["Vaccines eliminated smallpox in 1980",
                        "1 in 100 people have autoimmune disease",
                        "7-9 hours sleep boosts immune function 40 percent",
                        "Chronic stress reduces immune response"],
               icon="money", takeaway="Lifestyle choices significantly affect immunity."),
    make_scene("quiz", "Knowledge Check",
               question="Which branch of the immune system remembers past infections?",
               options=["Adaptive immune system", "Innate immune system", "The skin"],
               answer_index=0, takeaway="Memory cells make vaccines possible."),
    make_scene("summary", "Summary",
               bullets=["Two branches: innate (fast) and adaptive (precise)",
                        "Memory cells enable rapid response on re-exposure",
                        "Vaccines exploit immune memory safely",
                        "Lifestyle strongly affects immune strength"],
               icon="check", takeaway="Your immune system is remarkably intelligent."),
]

os.makedirs("output/test_renderer_frames", exist_ok=True)
all_ok = True

print("Testing all renderer types...")
for scene in scenes:
    RendClass = {
        "title":     TitleRenderer,
        "bullets":   BulletsRenderer,
        "quiz":      QuizRenderer,
        "summary":   SummaryRenderer,
        "flashcard": FlashcardRenderer,
    }.get(scene.kind, BulletsRenderer)

    r = RendClass(scene, T, duration=8.0)

    # Test 3 frames per scene: start, mid, end
    for t_val, label in [(0.1, "start"), (3.5, "mid"), (7.0, "end")]:
        frame = r.render(t_val)
        h, w, ch = frame.shape
        assert h == 1080 and w == 1920 and ch == 3, f"{scene.kind} frame shape wrong: {frame.shape}"
        assert frame.dtype.name == "uint8", f"{scene.kind} frame dtype wrong: {frame.dtype}"

        # Save frame as PNG
        from PIL import Image
        img = Image.fromarray(frame)
        out = f"output/test_renderer_frames/{scene.kind}_{label}.png"
        img.save(out)
        size_kb = os.path.getsize(out) // 1024
        print(f"  OK  {scene.kind:12} t={t_val:4.1f}s  {w}x{h}  {size_kb} KB  -> {out}")

print(f"\nAll renderer tests passed. Frames saved to output/test_renderer_frames/")
print("Open those PNGs to visually inspect the layout.")
