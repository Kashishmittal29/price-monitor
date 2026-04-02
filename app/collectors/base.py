"""
Collector base class.
Each marketplace collector reads from its local JSON files (simulating a live
scrape) and normalises data into a common dict structure consumed by the
ingest service.

Assumption: In production these would call live APIs/scrapers; for this
assignment the sample JSON files act as the source of truth.  Adding a new
source means subclassing BaseCollector and implementing `collect()`.
"""

import asyncio
import json
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

SAMPLE_DIR = Path(__file__).resolve().parent.parent.parent / "sample_data"


class BaseCollector(ABC):
    source: str = ""

    @abstractmethod
    async def collect(self) -> list[dict[str, Any]]:
        """Return a list of normalised product dicts."""
        ...

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=4))
    async def _read_json(self, path: Path) -> dict:
        """Async JSON read with retry — mirrors what a real HTTP fetch would do."""
        loop = asyncio.get_event_loop()
        raw = await loop.run_in_executor(None, path.read_text, "utf-8")
        return json.loads(raw)
