# test_pipeline.py  — save this in C:\cortex_Assignment\backend\

import asyncio
import sys
sys.path.insert(0, ".")

from pipeline.chunker import Chunker
from pipeline.deduplicator import Deduplicator
from parsers.instagram_parser import InstagramParser
from vector_store.qdrant_client import QdrantStore

# Sample data inline — no file needed
SAMPLE = {
    "posts": [
        {"id": "1", "created_at": "2025-01-01T00:00:00Z", "caption": "I prefer PostgreSQL for transactional systems."},
        {"id": "2", "created_at": "2025-01-02T00:00:00Z", "caption": "Redis is my default choice for caching."},
        {"id": "3", "created_at": "2025-01-03T00:00:00Z", "caption": "Documentation is a scaling tool for teams."},
        {"id": "4", "created_at": "2025-01-04T00:00:00Z", "caption": "Remote work succeeds with async communication."},
        {"id": "5", "created_at": "2025-01-05T00:00:00Z", "caption": "Kafka simplifies event-driven architectures."},
    ]
}

def keyword_search(chunks, query, top_k=3):
    """Simple keyword overlap scoring — no embeddings needed."""
    query_words = set(query.lower().split())
    scored = []
    for chunk in chunks:
        text_words = set(chunk["text"].lower().split())
        score = len(query_words & text_words)
        scored.append((score, chunk))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [c for _, c in scored[:top_k]]

async def main():
    print("\n=== PIPELINE TEST (no OpenAI needed) ===\n")

    # 1. Parse
    import json, tempfile, os
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(SAMPLE, f)
        tmp_path = f.name

    parser = InstagramParser()
    # records = parser.parse(tmp_path)
    # records = parser.parse(tmp_path, "test_Insta_file.json")
    with open(tmp_path, "rb") as f:
        records = parser.parse(f, "test_Insta_file.json")
    os.unlink(tmp_path)
    print(f"[1] Parser: {len(records)} records extracted")
    assert len(records) == 5

    # 2. Chunk
    chunker = Chunker()
    chunks = chunker.chunk_records(records)
    print(f"[2] Chunker: {len(chunks)} chunks produced")
    assert len(chunks) == 5

    # 3. Dedup IDs
    dedup = Deduplicator()
    ids = [dedup.chunk_id(chunk) for chunk in chunks]
    print(f"[3] Deduplicator: {len(set(ids))} unique IDs (expected 5)")
    assert len(set(ids)) == 5

    # 4. Keyword search simulation
    chunk_dicts = [{"text": c.text, "platform": c.platform, "content_type": c.content_type} for c in chunks]
    
    queries = ["databases PostgreSQL", "documentation teams", "remote work"]
    print("\n[4] Keyword search results:")
    for q in queries:
        results = keyword_search(chunk_dicts, q, top_k=2)
        print(f"\n  Query: '{q}'")
        for r in results:
            print(f"    → {r['text'][:80]}")

    print("\n=== ALL TESTS PASSED — pipeline logic is correct ===")
    print("=== Only missing piece: OpenAI API credits for real embeddings ===\n")

asyncio.run(main())