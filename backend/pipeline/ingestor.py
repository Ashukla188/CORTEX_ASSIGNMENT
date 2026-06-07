from __future__ import annotations

from dataclasses import asdict
from typing import Any, Dict, List, Optional

from parsers import InstagramParser, LinkedInParser, TwitterParser
from parsers.base_parser import ParsedRecord

from .chunker import Chunk, Chunker
from .deduplicator import Deduplicator
from .embedder import Embedder
from vector_store.qdrant_client import QdrantStore


class Ingestor:
    def __init__(self, embedder: Embedder, store: QdrantStore):
        self.embedder = embedder
        self.store = store
        self.chunker = Chunker()
        self.deduplicator = Deduplicator()
        self.parsers = {
            "linkedin": LinkedInParser(),
            "twitter": TwitterParser(),
            "instagram": InstagramParser(),
        }

    async def ingest_file(self, upload_file, source_type: Optional[str] = None) -> Dict[str, Any]:
        # Parser selection is based on file name or explicit source_type so manual testing is flexible.
        parser = self._resolve_parser(upload_file.filename or "", source_type)
        self._validate_file_extension(upload_file.filename or "", parser.platform)
        print(f"[ingestor] using parser={parser.__class__.__name__} for file={upload_file.filename!r}")
        records = parser.parse(upload_file.file, upload_file.filename or "upload")
        print(f"[ingestor] parser returned {len(records)} record(s)")
        chunks = self.chunker.chunk_records(records)
        if not chunks:
            print("[ingestor] no chunks produced")
            return {"records": 0, "chunks": 0, "inserted": 0}

        # Embeddings are generated only after chunking so the vector store receives normalized units of meaning.
        embeddings = await self.embedder.embed_texts([chunk.text for chunk in chunks])
        print(f"[ingestor] received {len(embeddings)} embedding(s)")
        points = []
        for chunk, embedding in zip(chunks, embeddings):
            point_id = self.deduplicator.chunk_id(chunk)
            points.append(
                {
                    "id": point_id,
                    "vector": embedding,
                    "payload": {
                        **chunk.payload(),
                        "point_id": point_id,
                    },
                }
            )

        self.store.upsert(points)
        print(f"[ingestor] upsert complete points={len(points)}")
        return {"records": len(records), "chunks": len(chunks), "inserted": len(points)}

    def _resolve_parser(self, filename: str, source_type: Optional[str]):
        normalized = (source_type or "").strip().lower()
        if normalized in self.parsers:
            return self.parsers[normalized]

        lowered = filename.lower()
        if "linkedin" in lowered or lowered.endswith(".csv"):
            return self.parsers["linkedin"]
        if "twitter" in lowered or lowered.endswith(".json"):
            return self.parsers["twitter"]
        if "instagram" in lowered or lowered.endswith(".html"):
            return self.parsers["instagram"]
        return self.parsers["linkedin"]

    @staticmethod
    def _validate_file_extension(filename: str, platform: str) -> None:
        lowered = filename.lower()
        if platform == "linkedin" and not lowered.endswith(".csv"):
            raise ValueError("LinkedIn uploads must be CSV files.")
