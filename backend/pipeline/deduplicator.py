from __future__ import annotations

import hashlib
import uuid

from .chunker import Chunk


class Deduplicator:
    def chunk_id(self, chunk: Chunk) -> str:
        # Build a stable raw identifier from the platform record when available.
        if chunk.platform_id:
            raw = f"{chunk.platform}:{chunk.platform_id}"
        else:
            raw = hashlib.md5(chunk.text.encode("utf-8")).hexdigest()

        # Qdrant accepts UUIDs, so convert the deterministic raw value into UUID form.
        return str(uuid.UUID(hashlib.md5(raw.encode("utf-8")).hexdigest()))
