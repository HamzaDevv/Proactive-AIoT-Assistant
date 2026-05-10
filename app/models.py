from pydantic import BaseModel
from typing import List, Optional, Dict, Any

class CommandRequest(BaseModel):
    payload: str          # Tokenized text
    user_token: str       # e.g. "USER_1"
    context_device_id: str  # e.g. "lamp_living_reading"

class CommandResponse(BaseModel):
    message: str
    actions_taken: List[Dict[str, Any]] = []

class PreferenceUpdate(BaseModel):
    markdown: str

class SpatialNode(BaseModel):
    id: str
    path: str
    device_type: str
    matter_id: Optional[str] = None
    ha_entity_id: Optional[str] = None
    neighbors: List[str] = []
    preferences_md: Optional[str] = None
