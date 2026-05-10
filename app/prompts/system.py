import json

class PromptBuilder:
    def build(self, spatial_ctx: dict, ha_states: dict) -> str:
        target = spatial_ctx.get("target")
        neighbors = spatial_ctx.get("neighbors", [])

        if not target:
            context_block = "## Target Device\n(no context device found)\n"
        else:
            context_block = f"""
## Target Device
- ID: {target.get('_id', 'unknown')}
- Type: {target.get('device_type', 'unknown')}
- Path: {target.get('path', 'unknown')}

{target.get('preferences_md', '(no preferences set)')}
"""

        if neighbors:
            context_block += "\n## Neighbor Devices in Zone\n"
            # Filter out the target itself if it's in neighbors
            target_id = target.get('_id') if target else None
            filtered_neighbors = [n for n in neighbors if n.get('_id') != target_id]
            
            for n in filtered_neighbors[:5]:  # Cap at 5 neighbors to control token count
                eid = n.get("ha_entity_id")
                state = ha_states.get(eid, "unknown")
                context_block += f"""
### {n.get('_id')} ({n.get('device_type')}) — current state: {state}
{n.get('preferences_md', '(no preferences)')}
"""

        return f"""You are a smart home AI assistant. All users are identified by tokens (USER_1, USER_2).
All rooms and devices use tokens (ROOM_A, DEVICE_B). Never reveal or guess real names.
Always respond using the same token identifiers present in the user's message.

{context_block}

## Current Device States
{json.dumps(ha_states, indent=2)}

## Available Tools
Use these MCP tools to control devices. Always confirm what you're doing.
Proactively suggest related device changes based on neighbor context and preferences.
"""

prompt_builder = PromptBuilder()
