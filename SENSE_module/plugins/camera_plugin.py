# plugins/camera_plugin.py
from typing import Dict, Any
import random
import asyncio

from .base_plugin import BasePlugin


class CameraPlugin(BasePlugin):
    async def sense(self) -> Dict[str, Any]:
        # Simulate latency and return mock values
        await asyncio.sleep(0.05)
        emotion = random.choice(["neutral", "happy", "focused", "tired"])
        focus = round(random.uniform(0.4, 0.95), 2)

        return {
            "camera": {
                "emotion": emotion,
                "focus": focus,
                "confidence": round(random.uniform(0.6, 0.98), 2),
            }
        }
