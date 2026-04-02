import logging
from typing import Any

from app.collectors.base import BaseCollector, SAMPLE_DIR

logger = logging.getLogger(__name__)


class FashionphileCollector(BaseCollector):
    source = "fashionphile"

    async def collect(self) -> list[dict[str, Any]]:
        files = sorted(SAMPLE_DIR.glob("fashionphile_*.json"))
        results: list[dict[str, Any]] = []
        for f in files:
            try:
                raw = await self._read_json(f)
                results.append(self._normalise(raw))
            except Exception as exc:
                logger.error("Fashionphile: failed to parse %s: %s", f.name, exc)
        return results

    def _normalise(self, raw: dict) -> dict:
        meta = raw.get("metadata", {})
        return {
            "source": self.source,
            "external_id": raw.get("product_id", ""),
            "brand": raw.get("brand", ""),
            "model": raw.get("model", ""),
            "category": meta.get("garment_type", raw.get("function_id", "")),
            "condition": raw.get("condition"),
            "size": None,
            "color": None,
            "image_url": raw.get("image_url"),
            "product_url": raw.get("product_url"),
            "currency": raw.get("currency", "USD"),
            "current_price": float(raw.get("price", 0)),
            "is_sold": False,
        }
