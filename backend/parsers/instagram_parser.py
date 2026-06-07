from __future__ import annotations

import html
import json
import re
from typing import Any, Dict, List

from .base_parser import BaseParser, ParsedRecord


class InstagramParser(BaseParser):
    platform = "instagram"

    def parse(self, file_obj, filename: str) -> List[ParsedRecord]:
        # Instagram exports can be JSON or HTML, so the parser accepts both formats.
        print(f"[instagram] parsing file={filename!r}")
        raw = file_obj.read()
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8", errors="ignore")
        data = self._load_payload(raw)
        records: List[ParsedRecord] = []

        for item in self._extract_items(data):
            text = self._extract_text(item)
            if not text:
                continue
            content_type = self._content_type(item)
            platform_id = self._first(item, ("id", "media_id", "pk", "shortcode"))
            created_at = self._iso_or_none(self._first(item, ("created_at", "taken_at", "timestamp", "date")))
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

        print(f"[instagram] extracted {len(records)} record(s)")
        return records

    def _load_payload(self, raw: str) -> Any:
        stripped = raw.strip()
        if not stripped:
            return {}
        if stripped.startswith("<"):
            return {"html": stripped}
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            return {"raw": stripped}

    def _extract_items(self, data: Any) -> List[Dict[str, Any]]:
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
        if isinstance(data, dict):
            if "html" in data:
                return self._items_from_html(data["html"])
            for key in ("media", "items", "posts", "photos", "comments"):
                value = data.get(key)
                if isinstance(value, list):
                    return [item for item in value if isinstance(item, dict)]
            return [data]
        return []

    def _items_from_html(self, html_text: str) -> List[Dict[str, Any]]:
        matches = re.findall(r'<script[^>]+type="application/ld\+json"[^>]*>(.*?)</script>', html_text, re.S)
        items: List[Dict[str, Any]] = []
        for match in matches:
            try:
                loaded = json.loads(html.unescape(match))
            except json.JSONDecodeError:
                continue
            if isinstance(loaded, dict):
                items.append(loaded)
            elif isinstance(loaded, list):
                items.extend([item for item in loaded if isinstance(item, dict)])
        if not items:
            text = re.sub(r"<[^>]+>", " ", html_text)
            text = re.sub(r"\s+", " ", html.unescape(text)).strip()
            if text:
                items.append({"caption": text})
        return items

    def _extract_text(self, item: Dict[str, Any]) -> str:
        for field in ("caption", "text", "title", "body", "comment"):
            value = item.get(field)
            if value:
                return str(value).strip()
        nested = item.get("edge_media_to_caption")
        if isinstance(nested, dict):
            edges = nested.get("edges")
            if isinstance(edges, list) and edges:
                node = edges[0].get("node") if isinstance(edges[0], dict) else None
                if isinstance(node, dict) and node.get("text"):
                    return str(node["text"]).strip()
        return ""

    def _content_type(self, item: Dict[str, Any]) -> str:
        if item.get("caption"):
            return "caption"
        if item.get("comment"):
            return "comment"
        return "post"

    def _first(self, row: Dict[str, Any], fields: tuple[str, ...]):
        for field in fields:
            value = row.get(field)
            if value not in (None, ""):
                return str(value).strip()
        return None
