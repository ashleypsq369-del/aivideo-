import argparse
import sys

from .pipeline import build_video


def main():
    p = argparse.ArgumentParser(description="Turn lesson text into a narrated video.")
    p.add_argument("input", help="path to a .txt lesson, or - for stdin")
    p.add_argument("-o", "--out", default="output")
    p.add_argument("--topic")
    p.add_argument("--engine", default="mock", choices=["mock", "espeak", "kokoro"])
    p.add_argument("--voice")
    p.add_argument("--claude", action="store_true", help="plan scenes with Claude (needs ANTHROPIC_API_KEY)")
    a = p.parse_args()
    text = sys.stdin.read() if a.input == "-" else open(a.input, encoding="utf-8").read()
    r = build_video(text, a.out, a.topic, a.engine, a.voice, a.claude, progress=print)
    print(f"\nVideo: {r['video']}  ({r['total_seconds']}s, {len(r['timeline'])} scenes)")


if __name__ == "__main__":
    main()
