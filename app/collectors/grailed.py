import logging
from pathlib import Path
from typing import Any

from app.collectors.base import BaseCollector, SAMPLE_DIR

logger = logging.getLogger(__name__)


class GrailedCollector(BaseCollector):
    source = "grailed"

    async def collect(self) -> list[dict[str, Any]]:
        files = sorted(SAMPLE_DIR.glob("grailed_*.json"))
        results: list[dict[str, Any]] = []
        for f in files:
            try:
                raw = await self._read_json(f)
                results.append(self._normalise(raw))
            except Exception as exc:
                logger.error("Grailed: failed to parse %s: %s", f.name, exc)
        return results

    def _normalise(self, raw: dict) -> dict:
        meta = raw.get("metadata", {})
        return {
            "source": self.source,
            "external_id": raw.get("product_id", ""),
            "brand": raw.get("brand", ""),
            "model": raw.get("model", ""),
            "category": raw.get("function_id", ""),
            "condition": None,                      # Grailed doesn't include condition
            "size": raw.get("size"),
            "color": meta.get("color"),
            "image_url": raw.get("image_url"),
            "product_url": raw.get("product_url"),
            "currency": "USD",
            "current_price": float(raw.get("price", 0)),
            "is_sold": bool(meta.get("is_sold", False)),
        }
