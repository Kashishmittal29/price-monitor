import logging
from typing import Any

from app.collectors.base import BaseCollector, SAMPLE_DIR

logger = logging.getLogger(__name__)


class FirstDibsCollector(BaseCollector):
    source = "1stdibs"

    async def collect(self) -> list[dict[str, Any]]:
        files = sorted(SAMPLE_DIR.glob("1stdibs_*.json"))
        results: list[dict[str, Any]] = []
        for f in files:
            try:
                raw = await self._read_json(f)
                results.append(self._normalise(raw))
            except Exception as exc:
                logger.error("1stdibs: failed to parse %s: %s", f.name, exc)
        return results

    def _normalise(self, raw: dict) -> dict:
        meta = raw.get("metadata", {})
        return {
            "source": self.source,
            "external_id": raw.get("product_id", raw.get("session_id", "")),
            "brand": raw.get("brand", meta.get("brand", "")),
            "model": raw.get("model", ""),
            "category": "belts",           # inferred from sample filenames
            "condition": meta.get("condition_display") or meta.get("condition"),
            "size": raw.get("size"),
            "color": None,
            "image_url": raw.get("image_url"),
            "product_url": raw.get("product_url"),
            "currency": "USD",
            "current_price": float(raw.get("price", 0)),
            "is_sold": meta.get("availability", "In Stock") != "In Stock",
        }
