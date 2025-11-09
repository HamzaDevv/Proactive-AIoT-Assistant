# plugins/base_plugin.py
from abc import ABC, abstractmethod
from typing import Dict, Any


class BasePlugin(ABC):
    @abstractmethod
    async def sense(self) -> Dict[str, Any]:
        """
        Return a dictionary of sensed values.
        Must be async (so aggregator can run plugins concurrently).
        """
        ...
