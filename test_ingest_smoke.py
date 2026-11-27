"""Smoke test for ingest module."""
import os
from aivideo.ingest import ingest_sources
from aivideo.ingest.chunker import verify_quote

result = ingest_sources(["samples/lesson.txt"], "output/test_ingest")
print(f"Chunks: {result['chunk_count']}, Words: {result['total_words']}")
for c in result["chunks"]:
    print(f"  {c['id']} ({c['word_count']} words): {c['text'][:60]}...")

chunks     = result["chunks"]
first      = chunks[0]
ok  = verify_quote(first["text"][:30], first["id"], chunks)
bad = verify_quote("invented fact not in source", first["id"], chunks)
print(f"verify_quote (True):  {ok}")
print(f"verify_quote (False): {bad}")
assert ok  is True,  "Expected True"
assert bad is False, "Expected False"
print("All ingest checks passed.")
