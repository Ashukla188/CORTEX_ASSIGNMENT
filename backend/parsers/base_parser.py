from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional


@dataclass
class ParsedRecord:
    text: str
    platform: str
    content_type: str
    platform_id: Optional[str] = None
    created_at: Optional[str] = None
    char_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def normalized(self) -> "ParsedRecord":
        self.text = (self.text or "").strip()
        self.char_count = len(self.text)
        if not self.created_at:
            self.created_at = None
        return self

    def as_payload(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "platform": self.platform,
            "content_type": self.content_type,
            "platform_id": self.platform_id,
            "created_at": self.created_at,
            "char_count": self.char_count,
        }


class BaseParser:
    platform: str = "unknown"

    def parse(self, file_obj, filename: str) -> List[ParsedRecord]:
        raise NotImplementedError

    @staticmethod
    def _iso_or_none(value: Any) -> Optional[str]:
        if value in (None, "", "null"):
            return None
        if isinstance(value, datetime):
            dt = value
        else:
            text = str(value).strip()
            try:
                dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
            except ValueError:
                return text
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat()

