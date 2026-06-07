from __future__ import annotations

import csv
import io
from typing import List

from .base_parser import BaseParser, ParsedRecord


class LinkedInParser(BaseParser):
    platform = "linkedin"

    TEXT_FIELDS = (
        "text",
        "content",
        "body",
        "summary",
        "message",
        "article",
        "comment",
        "post",
    )

    CONTENT_TYPE_HINTS = {
        "article": "article",
        "summary": "bio",
        "headline": "bio",
        "title": "post",
    }

    def parse(self, file_obj, filename: str) -> List[ParsedRecord]:
        # LinkedIn exports are parsed as CSV row-by-row so large files do not need to load fully into memory.
        print(f"[linkedin] parsing file={filename!r}")
        raw = file_obj.read()
        if isinstance(raw, bytes):
            text = raw.decode("utf-8-sig", errors="ignore")
        else:
            text = str(raw)
        reader = csv.DictReader(io.StringIO(text, newline=""))
        records: List[ParsedRecord] = []

        for row in reader:
            normalized = {str(key).strip().lower(): value for key, value in row.items() if key}
            text = self._pick_text(normalized)
            if not text:
                continue

            platform_id = self._pick_first(normalized, ("update id", "update_id", "id", "urn", "activity urn"))
            created_at = self._iso_or_none(
                self._pick_first(normalized, ("date", "created at", "created_at", "timestamp", "time"))
            )
            content_type = self._infer_content_type(normalized)

            records.append(
                ParsedRecord(
                    text=text,
                    platform=self.platform,
                    content_type=content_type,
                    platform_id=platform_id,
                    created_at=created_at,
                    metadata={"filename": filename},
                ).normalized()
            )

        print(f"[linkedin] extracted {len(records)} record(s)")
        return records

    def _pick_text(self, row: dict) -> str:
        for field in self.TEXT_FIELDS:
            value = row.get(field)
            if value:
                return str(value).strip()
        parts = [str(value).strip() for value in row.values() if value and str(value).strip()]
        return " ".join(parts[:3]).strip()

    def _pick_first(self, row: dict, field_names: tuple[str, ...]):
        for field_name in field_names:
            if row.get(field_name):
                return str(row[field_name]).strip()
        return None

    def _infer_content_type(self, row: dict) -> str:
        for key, value in row.items():
            if value and key in self.CONTENT_TYPE_HINTS:
                return self.CONTENT_TYPE_HINTS[key]
        return "post"
