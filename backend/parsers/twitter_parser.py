from __future__ import annotations

import json
from typing import Any, Dict, List

from .base_parser import BaseParser, ParsedRecord


class TwitterParser(BaseParser):
    platform = "twitter"

    def parse(self, file_obj, filename: str) -> List[ParsedRecord]:
        # Twitter exports may arrive in several JSON shapes, so we normalize them before extraction.
        print(f"[twitter] parsing file={filename!r}")
        raw = file_obj.read()
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8", errors="ignore")
        data = json.loads(raw or "{}")
        tweets = self._extract_tweets(data)
        records: List[ParsedRecord] = []

        for tweet in tweets:
            text = self._text_from_tweet(tweet)
            if not text:
                continue
            platform_id = self._first(tweet, ("id_str", "id", "tweet_id"))
            created_at = self._iso_or_none(self._first(tweet, ("created_at", "date", "timestamp")))
            records.append(
                ParsedRecord(
                    text=text,
                    platform=self.platform,
                    content_type="post",
                    platform_id=platform_id,
                    created_at=created_at,
                    metadata={"filename": filename},
                ).normalized()
            )

        print(f"[twitter] extracted {len(records)} record(s)")
        return records

    def _extract_tweets(self, data: Any) -> List[Dict[str, Any]]:
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
        if isinstance(data, dict):
            if isinstance(data.get("tweets"), list):
                return [item for item in data["tweets"] if isinstance(item, dict)]
            if isinstance(data.get("data"), list):
                return [item for item in data["data"] if isinstance(item, dict)]
            global_objects = data.get("globalObjects") or {}
            if isinstance(global_objects, dict) and isinstance(global_objects.get("tweets"), dict):
                return list(global_objects["tweets"].values())
            return [data]
        return []

    def _text_from_tweet(self, tweet: Dict[str, Any]) -> str:
        if tweet.get("full_text"):
            return str(tweet["full_text"]).strip()
        if tweet.get("text"):
            return str(tweet["text"]).strip()
        legacy = tweet.get("content") or tweet.get("body")
        return str(legacy).strip() if legacy else ""

    def _first(self, row: Dict[str, Any], fields: tuple[str, ...]):
        for field in fields:
            value = row.get(field)
            if value not in (None, ""):
                return str(value).strip()
        return None
