from __future__ import annotations

import math
import os
from pathlib import Path
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(ROOT_DIR / ".env", override=False)


@dataclass
class SearchHit:
    id: str
    score: float
    payload: Dict[str, Any]


class QdrantStore:
    def __init__(self, collection_name: str = "cortex_person", vector_size: int = 1536):
        self.collection_name = collection_name
        self.vector_size = vector_size
        self._client = None
        self._memory: Dict[str, Dict[str, Any]] = {}
        self._memory_vectors: Dict[str, List[float]] = {}
        self._init_client()

    def _init_client(self) -> None:
        try:
            from qdrant_client import QdrantClient
            from qdrant_client.http import models
        except Exception:
            # If Qdrant is not installed, the store automatically uses in-memory mode.
            print("[qdrant] client import failed, using in-memory store")
            return

        url = os.getenv("QDRANT_URL", "http://localhost:6333")
        api_key = os.getenv("QDRANT_API_KEY", "").strip() or None
        try:
            client = QdrantClient(url=url, api_key=api_key)
            client.get_collections()
        except Exception:
            # Connection failure should not stop local testing; health will still expose the fallback.
            print(f"[qdrant] connection failed for url={url!r}, using in-memory store")
            return
        self._client = client
        self._models = models
        print(f"[qdrant] connected to {url!r} auth={'yes' if api_key else 'no'}")

    def ensure_collection(self) -> None:
        if self._client is None:
            return

        # Collection creation is idempotent so the app can start cleanly on repeat runs.
        collections = self._client.get_collections().collections
        names = {collection.name for collection in collections}
        if self.collection_name in names:
            print(f"[qdrant] collection exists: {self.collection_name}")
            return

        print(f"[qdrant] creating collection: {self.collection_name}")
        self._client.create_collection(
            collection_name=self.collection_name,
            vectors_config=self._models.VectorParams(size=self.vector_size, distance=self._models.Distance.COSINE),
        )

    def upsert(self, points: List[Dict[str, Any]]) -> None:
        if points:
            self.vector_size = len(points[0]["vector"])
        if self._client is None:
            print(f"[qdrant] storing {len(points)} point(s) in memory")
            for point in points:
                self._memory[str(point["id"])] = dict(point["payload"])
                self._memory_vectors[str(point["id"])] = list(point["vector"])
            return

        self.ensure_collection()
        print(f"[qdrant] upserting {len(points)} point(s) into {self.collection_name}")
        self._client.upsert(
            collection_name=self.collection_name,
            points=[
                self._models.PointStruct(id=point["id"], vector=point["vector"], payload=point["payload"])
                for point in points
            ],
        )

    def clear(self) -> None:
        if self._client is None:
            print("[qdrant] clearing in-memory store")
            self._memory.clear()
            self._memory_vectors.clear()
            return

        print(f"[qdrant] clearing collection={self.collection_name}")
        try:
            self._client.delete_collection(collection_name=self.collection_name)
        except Exception:
            # If the collection does not exist yet, there is nothing to clear.
            self._memory.clear()
            self._memory_vectors.clear()

    def search(self, vector: List[float], limit: int = 5) -> List[SearchHit]:
        if self._client is None:
            print(f"[qdrant] searching in-memory store limit={limit}")
            scored = []
            for point_id, payload in self._memory.items():
                stored = self._memory_vectors.get(point_id)
                if not stored:
                    continue
                scored.append(SearchHit(id=point_id, score=self._cosine(vector, stored), payload=payload))
            scored.sort(key=lambda hit: hit.score, reverse=True)
            return scored[:limit]

        self.ensure_collection()
        print(f"[qdrant] searching collection={self.collection_name} limit={limit}")
        results = self._client.query_points(
            collection_name=self.collection_name,
            query=vector,
            limit=limit,
            with_payload=True,
        ).points
        return [
            SearchHit(id=str(result.id), score=float(result.score), payload=dict(result.payload or {}))
            for result in results
        ]

    def health(self) -> bool:
        if self._client is None:
            print("[qdrant] health check against in-memory store")
            return True
        try:
            self._client.get_collections()
            print("[qdrant] health check ok")
            return True
        except Exception:
            print("[qdrant] health check failed")
            return False

    @staticmethod
    def _cosine(left: List[float], right: List[float]) -> float:
        numerator = sum(a * b for a, b in zip(left, right))
        left_norm = math.sqrt(sum(a * a for a in left)) or 1.0
        right_norm = math.sqrt(sum(b * b for b in right)) or 1.0
        return numerator / (left_norm * right_norm)
