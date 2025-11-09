# sense_aggregator.py
from typing import Dict, Any, List
from datetime import datetime
import asyncio

from .plugins.fit_plugin import FitPlugin
from .plugins.camera_plugin import CameraPlugin
from .plugins.location_plugin import LocationPlugin


class SenseAggregator:
    def __init__(self):
        self.plugins = [FitPlugin(), CameraPlugin(), LocationPlugin()]

    async def collect(self) -> Dict[str, Any]:
        # Run all plugins concurrently
        results = await asyncio.gather(*[p.sense() for p in self.plugins])

        packet: Dict[str, Any] = {"timestamp": datetime.now().isoformat()}
        for r in results:
            # Each plugin returns a namespaced dict (e.g., {"fit": {...}})
            packet.update(r)
        return packet
