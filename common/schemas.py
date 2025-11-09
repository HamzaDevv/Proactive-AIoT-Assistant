from __future__ import annotations
from typing import Any, Dict, List, Optional, Literal
from pydantic import BaseModel, Field
from datetime import datetime

# --- Context Schemas (for SENSE and THINK module) ---


class BiometricContext(BaseModel):
    heart_rate: Optional[float] = None
    activity_status: Optional[Literal["idle", "walking", "post_workout"]] = None
    stress_level: Optional[Literal["low", "high"]] = None
    calories_today: Optional[float] = None
    confidence: Optional[float] = Field(default=1.0, ge=0.0, le=1.0)


class LocationContext(BaseModel):
    place: Optional[str] = None
    travel_eta_min: Optional[int] = None
    confidence: Optional[float] = Field(default=1.0, ge=0.0, le=1.0)


class ScheduleContext(BaseModel):
    next_meeting_time: Optional[datetime] = None
    free_now: Optional[bool] = None


class EnvironmentContext(BaseModel):
    room_temp: Optional[float] = None
    air_quality: Optional[Literal["good", "moderate", "poor"]] = None
    occupancy: Optional[Literal["occupied", "vacant"]] = None
    occupancy_confidence: Optional[float] = Field(default=1.0, ge=0.0, le=1.0)


class DeviceState(BaseModel):
    id: str
    name: Optional[str] = None
    on: bool
    params: Dict[str, Any] = Field(default_factory=dict)

    # *** CRITICAL FIX ***
    # Added capabilities field, which SafetyChecker depends on.
    # Defaulting to an empty dict makes checks easier.
    capabilities: Optional[Dict[str, Any]] = Field(default_factory=dict)


class ContextPacket(BaseModel):
    timestamp: datetime
    biometric: Optional[BiometricContext] = None
    location: Optional[LocationContext] = None
    schedule: Optional[ScheduleContext] = None
    environment: Optional[EnvironmentContext] = None
    devices: List[DeviceState] = Field(default_factory=list)
    raw: Dict[str, Any] = Field(default_factory=dict)


# --- Action Schemas (for THINK and ACTION module) ---


class ActionCommand(BaseModel):
    device_id: str
    command: str
    params: Dict[str, Any] = Field(default_factory=dict)


class SuggestionSchema(BaseModel):
    should_suggest: bool
    suggestion_text: Optional[str] = None
    reason: Optional[str] = None
    action: Optional[ActionCommand] = None
    confidence: Optional[float] = Field(default=0.5, ge=0.0, le=1.0)


class suggestion_list(BaseModel):
    List_of_sugg: List[SuggestionSchema]
