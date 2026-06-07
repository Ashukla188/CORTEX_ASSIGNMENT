from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, List

from pipeline.embedder import Embedder
from vector_store.qdrant_client import QdrantStore, SearchHit


@dataclass
class Answer:
    answer: str
    sources: List[Dict[str, Any]]


class RagChat:
    def __init__(self, embedder: Embedder, store: QdrantStore):
        self.embedder = embedder
        self.store = store
        self._client = None
        self._init_client()

    def _init_client(self) -> None:
        # Keep chat local to avoid OpenAI session/rate limits during testing.
        self._client = None
        return

        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        if not api_key:
            return
        try:
            from openai import AsyncOpenAI
        except Exception:
            return
        self._client = AsyncOpenAI(api_key=api_key)

    async def answer(self, question: str, top_k: int = 5) -> Answer:
        # Retrieval happens first so the LLM only sees grounded source snippets.
        print(f"[rag] answering question={question!r} top_k={top_k}")
        question_vector = (await self.embedder.embed_texts([question]))[0]
        search_limit = max(top_k * 4, top_k)
        hits = self.store.search(question_vector, limit=search_limit)
        print(f"[rag] retrieved {len(hits)} hit(s)")
        sources = [self._hit_to_source(hit) for hit in hits]

        filtered_sources = self._select_coherent_sources(sources)[:top_k]

        if self._client is None:
            # Without OpenAI access, return a deterministic local summary for testing the full flow.
            print("[rag] using fallback answer mode")
            return Answer(answer=self._fallback_answer(question, filtered_sources), sources=filtered_sources)

        prompt = self._build_prompt(question, filtered_sources)
        print("[rag] sending prompt to OpenAI chat completion")
        response = await self._client.chat.completions.create(
            model=os.getenv("OPENAI_CHAT_MODEL", "gpt-4o").strip(),
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You answer questions about a person using only the provided source snippets. "
                        "Cite the platform and content type for every claim."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
        )
        content = response.choices[0].message.content or ""
        print("[rag] chat completion received")
        return Answer(answer=content.strip(), sources=filtered_sources)

    def _build_prompt(self, question: str, sources: List[Dict[str, Any]]) -> str:
        snippets = []
        for index, source in enumerate(sources, start=1):
            snippets.append(
                f"[{index}] platform={source['platform']} type={source['content_type']} "
                f"date={source.get('created_at') or 'unknown'} text={source['text']}"
            )
        return f"Question: {question}\n\nSources:\n" + "\n".join(snippets)

    def _fallback_answer(self, question: str, sources: List[Dict[str, Any]]) -> str:
        if not sources:
            return f"No relevant content found for: {question}"
        
        lines = [f"Based on their own words, here is what this person thinks about '{question}':\n"]
        
        for i, source in enumerate(sources[:5], 1):
            text = source['text']
            platform = source['platform']
            content_type = source['content_type']
            date = source.get('created_at', 'unknown date')
            score = source.get('score', 0)
            lines.append(f"{i}. \"{text}\"")
            lines.append(f"   — {platform} {content_type}, {date} (relevance: {score:.2f})\n")
        
        lines.append("Note: answers are grounded in retrieved source content only.")
        return "\n".join(lines)

    def _select_coherent_sources(self, sources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if len(sources) <= 1:
            return sources

        buckets: Dict[str, List[Dict[str, Any]]] = {}
        for source in sources:
            bucket_key = source.get("source_filename") or source.get("platform") or "unknown"
            buckets.setdefault(str(bucket_key), []).append(source)

        def bucket_score(items: List[Dict[str, Any]]) -> float:
            return sum(float(item.get("score") or 0.0) for item in items)

        selected_bucket = max(buckets.values(), key=bucket_score)
        selected_bucket.sort(key=lambda item: float(item.get("score") or 0.0), reverse=True)
        return selected_bucket
    
    def _hit_to_source(self, hit: SearchHit) -> Dict[str, Any]:
        payload = dict(hit.payload or {})
        payload["score"] = hit.score
        payload["id"] = hit.id
        return payload
