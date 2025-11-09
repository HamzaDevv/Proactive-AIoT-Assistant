from __future__ import annotations
import json
import logging
import re  # <-- IMPORTED FOR SAFETY CHECKER
from typing import Any, Dict, List, Optional
from pydantic import ValidationError
from datetime import datetime, timedelta

# Import from shared schemas
from common.schemas import (
    ContextPacket,
    SuggestionSchema,
    ActionCommand,
    DeviceState,
    BiometricContext,
    LocationContext,
    ScheduleContext,
    EnvironmentContext,
)

# Import from our project modules
from config import GLOBAL_LLM, CHROMA_COLLECTION_NAME
from .memory import ChromaStore


# LangChain interfaces
from langchain_core.language_models import BaseLanguageModel
from langchain_core.prompts import PromptTemplate

# --- FIX: Import core parsers and remove LLMChain ---
from langchain_core.output_parsers import StrOutputParser, PydanticOutputParser
import asyncio  # For the demo

# ---------------------------
# Logging
# ---------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("sadaf.think")


# ---------------------------
# LangChain LLM Client Wrapper (Pass1 & Pass2)
# (Restored and UPDATED to LCEL)
# ---------------------------
class LangchainLLMClient:
    """
    A wrapper for the LangChain LLM to handle Pass 1 and Pass 2.
    *** UPDATED TO USE LCEL (LangChain Expression Language) ***
    """

    def __init__(self, llm: BaseLanguageModel):
        """
        Initialize the client with a pre-configured LangChain LLM instance
        and construct the LCEL chains.
        """
        if llm is None:
            raise ValueError(
                "A configured LangChain LLM (BaseLanguageModel) instance is required."
            )
        self.llm = llm

        # --- Pass 1 Chain (LCEL) ---
        self.pass1_prompt = PromptTemplate(
            template=(
                "You are Sadaf, a proactive assistant. Given the context, candidate actions, and relevant memories, write a concise summary (2-4 sentences) describing the situation and identify the most relevant candidate action."
                "\n\nContext:\n{context}\n\nCandidate Actions:\n{candidates}\n\nRelevant Memories:\n{memory}\n\nConcise Summary:"
            ),
            input_variables=["context", "candidates", "memory"],
        )
        # --- FIX: Replaced LLMChain with LCEL pipe ---
        self.pass1_chain = self.pass1_prompt | self.llm | StrOutputParser()

        # --- Pass 2 Chain (LCEL) ---
        self.pass2_parser = PydanticOutputParser(pydantic_object=SuggestionSchema)
        self.pass2_prompt = PromptTemplate(
            template=(
                "You are Sadaf. Based on the summary of the situation, produce a JSON object that matches the SuggestionSchema exactly. Your response MUST be only the JSON object."
                "\n\nSummary:\n{summary}\n\nFull Context (for reference):\n{context}\n\n"
                "JSON Output (must conform to schema):\n{format_instructions}\n"
            ),
            input_variables=["summary", "context"],
            partial_variables={
                "format_instructions": self.pass2_parser.get_format_instructions()
            },
        )
        # --- FIX: Replaced LLMChain with LCEL pipe ---
        self.pass2_chain = self.pass2_prompt | self.llm | self.pass2_parser

    async def pass1_reasoning(
        self, ctx: ContextPacket, candidates: List[Dict[str, Any]], memory_texts: str
    ) -> str:
        """Pass 1: Generate a human-readable summary and intent."""

        # --- FIX: Use .ainvoke() for LCEL chains ---
        raw = await self.pass1_chain.ainvoke(
            {
                "context": ctx.model_dump_json(exclude_unset=True),
                "candidates": json.dumps(candidates, default=str),
                "memory": memory_texts,
            }
        )
        return raw

    async def pass2_structured(
        self, ctx: ContextPacket, pass1_summary: str
    ) -> Dict[str, Any]:
        """Pass 2: Generate a structured JSON output based on Pass 1."""

        try:
            # --- FIX: Use .ainvoke() for LCEL chains ---
            # The parser now runs as part of the chain
            parsed: SuggestionSchema = await self.pass2_chain.ainvoke(
                {
                    "summary": pass1_summary,
                    "context": ctx.model_dump_json(exclude_unset=True),
                }
            )
            return parsed.model_dump()
        except Exception as e:
            logger.exception("Failed to parse LLM Pass 2 output: %s.", e)
            return {"should_suggest": False, "reason": "llm_parse_failed"}


# ---------------------------
# Simple deterministic DecisionGraph
# ---------------------------
class DecisionGraph:
    """Generates deterministic candidate actions based on rules."""

    @staticmethod
    def candidates_from_context(ctx: ContextPacket) -> List[Dict[str, Any]]:
        cands = []
        if ctx.environment:
            if ctx.environment.occupancy == "vacant":
                # propose turning off devices that are currently on
                on_devices = [
                    d.id for d in ctx.devices if d.on and "light" in d.id
                ]  # Be more specific
                if on_devices:
                    cands.append(
                        {
                            "action_type": "turn_off_room_lights",
                            "target_devices": on_devices,
                            "reason": "room appears empty and lights are on",
                        }
                    )

        if (
            ctx.biometric
            and ctx.biometric.activity_status == "post_workout"
            and ctx.location
            and ctx.location.place == "home"
        ):
            # propose preparatory action for bath
            water_devices = [
                d.id for d in ctx.devices if "geyser" in d.id or "water_heater" in d.id
            ]
            if water_devices:
                cands.append(
                    {
                        "action_type": "prepare_bath",
                        "target_devices": water_devices,
                        "reason": "user finished workout and is at home",
                    }
                )

        if ctx.biometric and ctx.biometric.stress_level == "high":
            relax_targets = [
                d.id for d in ctx.devices if "light" in d.id or "speaker" in d.id
            ]
            if relax_targets:
                cands.append(
                    {
                        "action_type": "relaxation_routine",
                        "target_devices": relax_targets,
                        "reason": "user shows high stress",
                    }
                )
        return cands


# ---------------------------
# Proactivity Budget Helper
# ---------------------------
class ProactivityBudget:
    """
    Tracks and limits proactive suggestions based on a minimum time threshold
    (cooldown period) between suggestions.
    """

    def __init__(self, cooldown_minutes: int = 10):
        """
        Initializes the budget with a minimum time between suggestions.

        Args:
            cooldown_minutes (int): The number of minutes that must pass
                                    before another suggestion is allowed.
        """
        self.cooldown_threshold = timedelta(minutes=cooldown_minutes)
        self.last_suggestion_time: Optional[datetime] = None
        logger.info(
            f"ProactivityBudget initialized with a {cooldown_minutes}-minute cooldown."
        )

    def allow(self) -> bool:
        """
        Checks if enough time has passed since the last suggestion was allowed.
        """
        now = datetime.utcnow()

        # If no suggestion has ever been allowed, allow this one.
        if self.last_suggestion_time is None:
            self.last_suggestion_time = now
            logger.info("Proactivity budget ALLOWED. (First suggestion)")
            return True

        # Calculate time elapsed since the last *allowed* suggestion
        time_elapsed = now - self.last_suggestion_time

        if time_elapsed >= self.cooldown_threshold:
            # Enough time has passed. Allow and update the timestamp.
            self.last_suggestion_time = now
            logger.info(
                f"Proactivity budget ALLOWED. (Time elapsed: {time_elapsed} >= {self.cooldown_threshold})"
            )
            return True
        else:
            # Not enough time has passed. Deny.
            time_remaining = self.cooldown_threshold - time_elapsed
            logger.warning(
                f"Proactivity budget DENIED. (Time elapsed: {time_elapsed} < {self.cooldown_threshold}). "
                f"Please wait {time_remaining.total_seconds():.1f} more seconds."
            )
            return False


# ---------------------------
# Safety checks & device capability validation
# (REPLACED WITH VERSION THAT READS devices.json FORMAT)
# ---------------------------
class SafetyChecker:
    """Performs safety and capability checks on a proposed action."""

    # These are devices we should NEVER toggle off, even if a rule suggests it.
    SAFE_DEVICE_BLACKLIST = {"router", "refrigerator", "security_camera"}

    @staticmethod
    def is_action_safe(action: ActionCommand, devices: List[DeviceState]) -> bool:
        dev_map = {d.id: d for d in devices}
        if action.device_id not in dev_map:
            logger.warning("SafetyCheck: Unknown device %s", action.device_id)
            return False

        # Check blacklist (e.g., "router", "refrigerator")
        for bad in SafetyChecker.SAFE_DEVICE_BLACKLIST:
            if bad in action.device_id:
                logger.warning(
                    "SafetyCheck: Action targets blacklisted device %s",
                    action.device_id,
                )
                return False

        dev = dev_map[action.device_id]

        # This is the 'capabilities' dict, structured like devices.json
        # This field is populated by ThinkOrchestrator._enrich_context_with_capabilities
        caps = dev.capabilities
        if not caps:
            logger.warning(
                "SafetyCheck: Device %s has no capabilities defined.", dev.id
            )
            # Fail safe: if no capabilities are defined, we can't check it.
            return False

        # 1. Check if the command (e.g., "set_brightness") is in the "functions" list
        available_functions = caps.get("functions", [])
        if action.command not in available_functions:
            logger.warning(
                "SafetyCheck: Device %s cannot perform command '%s'. Available: %s",
                action.device_id,
                action.command,
                available_functions,
            )
            return False

        # 2. Check all parameters for the action (e.g., {"brightness": 80})
        available_params = caps.get("parameters", {})
        for param_name, param_value in action.params.items():
            # Check if this parameter is defined for the device
            if param_name not in available_params:
                logger.debug(
                    "SafetyCheck: Param '%s' not in capability spec for %s. Skipping bounds check.",
                    param_name,
                    action.device_id,
                )
                continue

            # Get the spec for this parameter (e.g., [0, 100] or ["cool", "heat"])
            param_spec = available_params[param_name]

            # Case A: Spec is a list (either numeric range or string enum)
            if isinstance(param_spec, list):
                if not param_spec:
                    logger.debug(
                        "SafetyCheck: Param '%s' has empty spec list.", param_name
                    )
                    continue  # No range to check

                # Case A.1: Numeric range [min, max]
                if isinstance(param_spec[0], (int, float)):
                    if len(param_spec) == 2:
                        min_v, max_v = param_spec[0], param_spec[1]

                        # Ensure the value is numeric before comparing
                        if not isinstance(param_value, (int, float)):
                            logger.warning(
                                "SafetyCheck: Param '%s' value '%s' is not numeric for device %s.",
                                param_name,
                                param_value,
                                action.device_id,
                            )
                            return False

                        if not (min_v <= param_value <= max_v):
                            logger.warning(
                                "SafetyCheck: Param %s=%s outside range [%s, %s] for device %s",
                                param_name,
                                param_value,
                                min_v,
                                max_v,
                                action.device_id,
                            )
                            return False
                    else:
                        logger.warning(
                            "SafetyCheck: Numeric param spec '%s' has invalid format (not [min, max]).",
                            param_name,
                        )

                # Case A.2: String enum ["val1", "val2"]
                elif isinstance(param_spec[0], str):
                    if param_value not in param_spec:
                        logger.warning(
                            "SafetyCheck: Param %s=%s not in allowed list %s for device %s",
                            param_name,
                            param_value,
                            param_spec,
                            action.device_id,
                        )
                        return False

            # Case B: Spec is a string (e.g., "HH:MM")
            elif isinstance(param_spec, str):
                if param_spec == "HH:MM":
                    if not re.match(r"^\d{2}:\d{2}$", str(param_value)):
                        logger.warning(
                            "SafetyCheck: Param %s=%s does not match format '%s' for device %s",
                            param_name,
                            param_value,
                            param_spec,
                            action.device_id,
                        )
                        return False
                # Add other string format checks here if needed

            # Case C: Other spec types (e.g., nested dict) - not currently supported
            else:
                logger.debug(
                    "SafetyCheck: Param '%s' has unhandled spec format '%s' for %s. Skipping.",
                    param_name,
                    param_spec,
                    action.device_id,
                )

        # All checks passed
        return True


# ---------------------------
# Think Orchestrator
# ---------------------------
class ThinkOrchestrator:
    # --- FIX: Update __init__ signature to accept capabilities map ---
    def __init__(
        self,
        llm_client: LangchainLLMClient,
        memory: ChromaStore,
        device_capabilities: Dict[str, Dict[str, Any]],  # <-- ADDED
        cooldown_minutes: int = 10,
    ):
        self.llm_client = llm_client
        self.memory = memory
        self.device_capabilities = device_capabilities  # <-- ADDED: Stores the map
        self.proactivity_budget = ProactivityBudget(cooldown_minutes=cooldown_minutes)
        logger.info(
            "ThinkOrchestrator initialized with Capabilities, ChromaStore, LCEL Client, and Cooldown Budget."
        )

    async def _enrich_context_with_capabilities(
        self, ctx: ContextPacket
    ) -> ContextPacket:
        """
        Merges static device capabilities from the loaded JSON file into
        the dynamic DeviceState objects in the ContextPacket.
        """
        for dev_state in ctx.devices:
            if dev_state.id in self.device_capabilities:
                # Set the .capabilities field on the pydantic model
                dev_state.capabilities = self.device_capabilities[dev_state.id]
            else:
                logger.warning(
                    "Device %s from context has no capabilities defined in devices.json",
                    dev_state.id,
                )
                dev_state.capabilities = {}  # Ensure it's not None
        return ctx

    async def _get_memory_query(self, ctx: ContextPacket) -> str:
        """Builds a simple query string for memory retrieval."""
        mem_query_parts = []
        if ctx.biometric and ctx.biometric.activity_status:
            mem_query_parts.append(f"user activity {ctx.biometric.activity_status}")
        if ctx.biometric and ctx.biometric.stress_level:
            mem_query_parts.append(f"user stress {ctx.biometric.stress_level}")
        if ctx.environment and ctx.environment.occupancy:
            mem_query_parts.append(f"room {ctx.environment.occupancy}")
        if ctx.location and ctx.location.place:
            mem_query_parts.append(f"user at {ctx.location.place}")

        if not mem_query_parts:
            return "general user preferences"
        return ", ".join(mem_query_parts)

    async def process_context(self, ctx: ContextPacket) -> SuggestionSchema:
        logger.info("Processing context ts=%s", ctx.timestamp.isoformat())

        # --- FIX: Step 0: Enrich context with static capabilities ---
        ctx = await self._enrich_context_with_capabilities(ctx)

        # 1. deterministic candidates
        candidates = DecisionGraph.candidates_from_context(ctx)

        # 2. retrieve relevant memory (string)
        mem_query = await self._get_memory_query(ctx)
        memory_texts = self.memory.get_relevant_info(mem_query, n_results=3)

        # 3. Pass1 (reasoning summary)
        try:
            pass1_output = await self.llm_client.pass1_reasoning(
                ctx, candidates, memory_texts
            )
            logger.debug("Pass1 output: %s", pass1_output)
        except Exception as e:
            logger.exception("Pass1 LLM failure: %s", e)
            pass1_output = "LLM pass1 error"  # Fallback

        # 4. Pass2 (structured JSON)
        try:
            pass2_out = await self.llm_client.pass2_structured(ctx, pass1_output)
            suggestion = SuggestionSchema(**pass2_out)
        except ValidationError as e:
            logger.exception("Suggestion validation failed: %s", e)
            suggestion = SuggestionSchema(
                should_suggest=False, reason="validation_failed", confidence=0.0
            )
        except Exception as e:
            logger.exception("Pass2 parse/LLM failure: %s", e)
            suggestion = SuggestionSchema(
                should_suggest=False, reason="llm_error", confidence=0.0
            )

        # 5. Safety checks if contains action
        if suggestion.action:
            # The safety checker will now use the enriched capabilities
            if not SafetyChecker.is_action_safe(suggestion.action, ctx.devices):
                logger.warning(
                    "Safety check FAILED for action: %s",
                    suggestion.action.model_dump_json(),
                )
                suggestion.should_suggest = False
                suggestion.reason = "Action failed safety check."  # Overwrite reason

        # 6. Proactivity budget check
        if suggestion.should_suggest and not self.proactivity_budget.allow():
            logger.info("Proactivity budget exhausted; suppressing suggestion")
            suggestion.should_suggest = False
            suggestion.reason = "Proactivity budget exhausted."  # Overwrite reason

        return suggestion

    async def store_user_confirmation(
        self, suggestion: SuggestionSchema, ctx: ContextPacket, accepted: bool
    ):
        """Store accepted/rejected suggestions into memory."""
        if not self.memory:
            return

        activity = "unknown"
        if ctx.biometric:
            activity = ctx.biometric.activity_status or "unknown"

        if accepted:
            if suggestion.action:
                fact_text = f"User ACCEPTED this action: {suggestion.suggestion_text} (Action: {suggestion.action.command} {suggestion.action.device_id})"
                meta = {
                    "type": "accepted_action",
                    "accepted": True,
                    "action": suggestion.action.model_dump(),
                    "context_activity": activity,
                }
                self.memory.add_document(fact_text, meta)
        else:
            fact_text = f"User REJECTED this suggestion: {suggestion.suggestion_text}"
            meta = {
                "type": "rejected_action",
                "accepted": False,
                "reason": suggestion.reason,
                "context_activity": activity,
            }
            self.memory.add_document(fact_text, meta)


# ---------------------------
# Small demo runner / usage helper
# ---------------------------
async def demo_once():
    logger.info("--- Starting Demo ---")

    try:
        memory = ChromaStore(collection_name=CHROMA_COLLECTION_NAME)
        llm = GLOBAL_LLM  # configured in config.py
        if llm is None:
            logger.error(
                "GLOBAL_LLM is None. Check config.py and Ollama/Google connection."
            )
            return

        # --- FIX: Create a dummy capabilities map for the demo ---
        dummy_device_capabilities = {
            "smart_geyser_1": {
                "functions": ["on", "off", "set_temperature"],
                "parameters": {"temperature": [30, 75]},
            },
            "smart_light_1": {
                "functions": [
                    "on",
                    "off",
                    "set_brightness",
                    "set_color_temp",
                ],
                "parameters": {
                    "brightness": [0, 100],
                    "color_temperature": [2700, 6500],
                },
            },
            "smart_ac_1": {
                "functions": ["set_mode", "set_temperature", "eco_mode", "schedule"],
                "parameters": {
                    "mode": ["cool", "heat", "dry", "fan"],
                    "temperature": [16, 30],
                    "schedule_time": "HH:MM",
                },
            },
        }

        llm_client = LangchainLLMClient(llm=llm)
        orchestrator = ThinkOrchestrator(
            llm_client=llm_client,
            memory=memory,
            device_capabilities=dummy_device_capabilities,  # <-- PASS IT IN
            cooldown_minutes=0,
        )
        logger.info("Orchestrator initialized for demo.")

    except Exception as e:
        logger.exception(f"Failed to initialize orchestrator for demo: {e}")
        return

    # Example context
    ctx = ContextPacket(
        timestamp=datetime.utcnow(),
        biometric=BiometricContext(
            heart_rate=115, stress_level="high", activity_status="idle"
        ),
        location=LocationContext(place="office", travel_eta_min=30),
        schedule=ScheduleContext(next_meeting_time=None, free_now=True),
        environment=EnvironmentContext(
            room_temp=37.0, air_quality="moderate", occupancy="vacant"
        ),
        devices=[
            # --- FIX: capabilities field is now empty ---
            # The orchestrator will populate it using the map
            DeviceState(
                id="smart_geyser_1",
                name="Geyser",
                on=False,
                params={"temperature": 30},
                capabilities={},
            ),
            DeviceState(
                id="smart_light_1",
                name="Living Light",
                on=True,
                params={"brightness": 80},
                capabilities={},
            ),
            DeviceState(
                id="smart_ac_1",
                name="AC",
                on=False,
                params={},
                capabilities={},
            ),
        ],
    )

    logger.info("Processing example context...")
    suggestion = await orchestrator.process_context(ctx)
    print("\n--- FINAL SUGGESTION ---")
    print(suggestion.model_dump_json(indent=2))
    print("------------------------\n")

    # Demo storing feedback
    if suggestion.should_suggest:
        logger.info("Demo: Storing as ACCEPTED")
        await orchestrator.store_user_confirmation(suggestion, ctx, accepted=True)
    else:
        logger.info("Demo: Storing as REJECTED (or no suggestion)")
        await orchestrator.store_user_confirmation(suggestion, ctx, accepted=False)


if __name__ == "__main__":
    asyncio.run(demo_once())
