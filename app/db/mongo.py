import os
from motor.motor_asyncio import AsyncIOMotorClient
from typing import List, Dict, Any, Optional

class MongoManager:
    def __init__(self):
        self.client: Optional[AsyncIOMotorClient] = None
        self.db = None

    def connect(self):
        uri = os.getenv("MONGO_URI")
        if not uri:
            # We don't raise here to allow the app to start even if DB is not configured yet
            # but we should log it.
            print("WARNING: MONGO_URI environment variable not set")
            return
        self.client = AsyncIOMotorClient(uri)
        self.db = self.client.home_assistant

    async def get_spatial_context(self, device_id: str) -> Dict[str, Any]:
        if self.db is None:
            return {"target": None, "neighbors": [], "zone": None}
            
        node = await self.db.spatial_nodes.find_one({"_id": device_id})
        if not node:
            return {"target": None, "neighbors": [], "zone": None}

        # Handle nodes without path safely
        path = node.get("path", "")
        if "," in path:
            zone_prefix = path.rsplit(",", 1)[0]
        else:
            zone_prefix = path

        neighbors = await self.db.spatial_nodes.find(
            {"path": {"$regex": f"^{zone_prefix}"}},
            {"_id": 1, "device_type": 1, "preferences_md": 1, "ha_entity_id": 1}
        ).to_list(20)

        return {
            "target": node,
            "neighbors": neighbors,
            "zone": zone_prefix
        }

    async def update_preferences(self, device_id: str, markdown: str):
        if self.db is None:
            return
        await self.db.spatial_nodes.update_one(
            {"_id": device_id},
            {"$set": {"preferences_md": markdown}},
            upsert=True
        )

mongo_manager = MongoManager()
mongo_manager.connect()
