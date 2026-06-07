from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List

from parsers.base_parser import ParsedRecord


@dataclass
class Chunk:
    text: str
    platform: str
    content_type: str
    platform_id: str | None
    created_at: str | None
    char_count: int
    chunk_index: int
    source_filename: str | None = None

    def payload(self) -> dict:
        return {
            "text": self.text,
            "platform": self.platform,
            "content_type": self.content_type,
            "platform_id": self.platform_id,
            "created_at": self.created_at,
            "char_count": self.char_count,
            "chunk_index": self.chunk_index,
            "source_filename": self.source_filename,
        }


class Chunker:
    SHORT_FORM_TYPES = {"post", "bio", "caption", "comment"}
    SHORT_FORM_LIMIT = 1600
    LONG_FORM_LIMIT = 1200

    def chunk_records(self, records: Iterable[ParsedRecord]) -> List[Chunk]:
        records = list(records)
        print(f"[chunker] chunking {len(records)} record(s)")
        chunks: List[Chunk] = []
        for record in records:
            chunks.extend(self._chunk_record(record))
        print(f"[chunker] produced {len(chunks)} chunk(s)")
        return chunks

    def _chunk_record(self, record: ParsedRecord) -> List[Chunk]:
        text = (record.text or "").strip()
        if not text:
            return []

        # Short-form content stays atomic so retrieval keeps the original meaning intact.
        if record.content_type in self.SHORT_FORM_TYPES or len(text) <= self.SHORT_FORM_LIMIT:
            print(f"[chunker] short-form record kept atomic platform={record.platform} type={record.content_type}")
            return [self._build_chunk(record, text, 0)]

        # Long-form content is split on paragraph boundaries, not arbitrary character counts.
        print(f"[chunker] long-form record split platform={record.platform} chars={len(text)}")
        paragraphs = [part.strip() for part in text.split("\n\n") if part.strip()]
        if not paragraphs:
            return [self._build_chunk(record, text, 0)]

        chunks: List[Chunk] = []
        buffer: list[str] = []
        buffer_length = 0
        index = 0
        for paragraph in paragraphs:
            paragraph_length = len(paragraph)
            if buffer and buffer_length + paragraph_length + 2 > self.LONG_FORM_LIMIT:
                chunks.append(self._build_chunk(record, "\n\n".join(buffer), index))
                index += 1
                buffer = [paragraph]
                buffer_length = paragraph_length
                continue
            buffer.append(paragraph)
            buffer_length += paragraph_length + (2 if len(buffer) > 1 else 0)

        if buffer:
            chunks.append(self._build_chunk(record, "\n\n".join(buffer), index))

        return chunks

    def _build_chunk(self, record: ParsedRecord, text: str, index: int) -> Chunk:
        return Chunk(
            text=text.strip(),
            platform=record.platform,
            content_type=record.content_type,
            platform_id=record.platform_id,
            created_at=record.created_at,
            char_count=len(text.strip()),
            chunk_index=index,
            source_filename=record.metadata.get("filename"),
        )
