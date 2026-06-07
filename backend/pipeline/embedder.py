from __future__ import annotations

import asyncio
import hashlib
import math
import os
import random
from typing import List

from dotenv import load_dotenv

load_dotenv(override=True)


class Embedder:
    def __init__(self, model: str = "text-embedding-3-small", batch_size: int = 100):
        self.model = model
        self.batch_size = batch_size
        self.dimension = 1536
        self._client = None
        self._local_model = None
        self._mode = "fallback"
        self._enable_local_embeddings = os.getenv("ENABLE_LOCAL_EMBEDDINGS", "").strip().lower() in {"1", "true", "yes", "on"}
        self._init_clients()

    def _init_clients(self) -> None:
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        if api_key:
            try:
                from openai import AsyncOpenAI

                self._client = AsyncOpenAI(api_key=api_key)
                self._mode = "openai"
                self.dimension = 1536  # Native OpenAI size
                print("[embedder] OpenAI client initialized")
            except Exception as exc:
                print(f"[embedder] OpenAI client unavailable: {exc}")

        if self._enable_local_embeddings:
            try:
                from sentence_transformers import SentenceTransformer

                print("[embedder] loading local sentence-transformers model (first run downloads ~90MB)...")
                self._local_model = SentenceTransformer("all-MiniLM-L6-v2")
                if self._mode != "openai":
                    self._mode = "local"
                    self.dimension = 384  # Native Sentence-Transformers size
                print("[embedder] local model ready (all-MiniLM-L6-v2, 384 dims)")
            except Exception as exc:
                print(f"[embedder] sentence-transformers unavailable: {exc}")
        else:
            print("[embedder] local embeddings disabled; using OpenAI or fallback only")

        if self._client is None and self._local_model is None:
            print("[embedder] no OpenAI or local model available, using fallback embeddings")
            print("[embedder] WARNING: fallback embeddings have no semantic meaning - search results will be random")

    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []

        if self._mode == "openai" and self._client is not None:
            try:
                return await self._embed_with_openai(texts)
            except Exception as exc:
                print(f"[embedder] OpenAI embedding failed, switching to local model: {exc}")
                if self._local_model is not None:
                    self._mode = "local"
                    self.dimension = 384  # Native Sentence-Transformers size
                else:
                    self._mode = "fallback"

        if self._mode == "local" and self._local_model is not None:
            print(f"[embedder] embedding {len(texts)} text(s) with local model")
            loop = asyncio.get_running_loop()
            embeddings = await loop.run_in_executor(None, self._embed_local, texts)
            return embeddings

        if self._mode == "local" and self._local_model is None and self._enable_local_embeddings:
            try:
                from sentence_transformers import SentenceTransformer

                print("[embedder] lazily loading local sentence-transformers model")
                self._local_model = SentenceTransformer("all-MiniLM-L6-v2")
                loop = asyncio.get_running_loop()
                embeddings = await loop.run_in_executor(None, self._embed_local, texts)
                return embeddings
            except Exception as exc:
                print(f"[embedder] lazy local model load failed: {exc}")

        print(f"[embedder] generating {len(texts)} fallback embedding(s)")
        return [self._fallback_embedding(text) for text in texts]

    async def _embed_with_openai(self, texts: List[str]) -> List[List[float]]:
        print(f"[embedder] embedding {len(texts)} text(s) in batches of {self.batch_size} with OpenAI")
        batches = [texts[i : i + self.batch_size] for i in range(0, len(texts), self.batch_size)]
        semaphore = asyncio.Semaphore(5)

        async def _guarded(batch):
            async with semaphore:
                return await self._embed_batch_openai(batch)

        results = await asyncio.gather(*(_guarded(batch) for batch in batches))
        flattened: List[List[float]] = []
        for batch in results:
            flattened.extend(batch)
        return flattened

    async def _embed_batch_openai(self, batch: List[str]) -> List[List[float]]:
        max_retries = 4
        for attempt in range(max_retries):
            try:
                print(f"[embedder] sending batch of {len(batch)} text(s) to OpenAI")
                response = await self._client.embeddings.create(model=self.model, input=batch)
                ordered = sorted(response.data, key=lambda item: item.index)
                return [list(item.embedding) for item in ordered]
            except Exception as exc:
                is_last = attempt == max_retries - 1
                wait = 2 ** attempt  # 1s, 2s, 4s, 8s
                if is_last:
                    print(f"[embedder] batch failed after {max_retries} attempts: {exc}")
                    raise
                print(f"[embedder] batch attempt {attempt + 1} failed ({exc}), retrying in {wait}s")
                await asyncio.sleep(wait)
    def _embed_local(self, texts: List[str]) -> List[List[float]]:
        """Run sentence-transformers synchronously (called via run_in_executor)."""
        vectors = self._local_model.encode(texts, show_progress_bar=False, normalize_embeddings=True)
        return [v.tolist() for v in vectors]

    def _fallback_embedding(self, text: str) -> List[float]:
        print(f"[embedder] fallback vector generated for text_len={len(text)}")
        seed = int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:16], 16)
        rng = random.Random(seed)
        vector = [rng.uniform(-1.0, 1.0) for _ in range(self.dimension)]
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]
