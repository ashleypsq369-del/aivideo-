"""Check which optional animation dependencies are available."""

DEPS = [
    ("numpy",      "NumPy array operations"),
    ("moviepy",    "MoviePy animated video"),
    ("cv2",        "OpenCV frame processing"),
    ("matplotlib", "Matplotlib charts"),
]

def check():
    print("\naivideo dependency check")
    print("=" * 40)
    all_ok = True
    for mod, desc in DEPS:
        try:
            __import__(mod)
            print(f"  OK  {mod:<18} {desc}")
        except ImportError:
            print(f"  X   {mod:<18} {desc}  -- pip install {mod}")
            all_ok = False
    print()
    if all_ok:
        print("All animation dependencies available. Quality: cinematic")
    else:
        print("Some deps missing -- draft/static quality only.")
    print()

if __name__ == "__main__":
    check()
