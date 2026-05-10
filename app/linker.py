from app.models import CommandRequest, CommandResponse
from app.db.mongo import mongo_manager
from app.ha.client import ha_client
from app.prompts.system import prompt_builder
from app.agents.orchestrator import orchestrator
import logging

logger = logging.getLogger(__name__)

class Linker:
    async def process(self, req: CommandRequest) -> CommandResponse:
        try:
            # 1. Fetch spatial context from MongoDB
            spatial_ctx = await mongo_manager.get_spatial_context(req.context_device_id)

            # 2. Fetch current HA device states in parallel
            entity_ids = []
            if spatial_ctx["target"] and spatial_ctx["target"].get("ha_entity_id"):
                entity_ids.append(spatial_ctx["target"]["ha_entity_id"])
            
            for n in spatial_ctx["neighbors"]:
                if n.get("ha_entity_id"):
                    entity_ids.append(n["ha_entity_id"])
            
            entity_ids = list(set(entity_ids))
            ha_states = await ha_client.get_zone_states(entity_ids)

            # 3. Build system prompt with injected context
            system_prompt = prompt_builder.build(
                spatial_ctx=spatial_ctx,
                ha_states=ha_states
            )

            # 4. Run LangGraph orchestration
            result = await orchestrator.run(
                payload=req.payload,
                system_prompt=system_prompt,
                spatial_ctx=spatial_ctx,
                ha_states=ha_states
            )

            return CommandResponse(
                message=result.get("response", "I've processed your command."),
                actions_taken=result.get("tool_calls", [])
            )
        except Exception as e:
            logger.error(f"Error in Linker process: {e}")
            return CommandResponse(
                message=f"Error processing command: {str(e)}",
                actions_taken=[]
            )

linker = Linker()
