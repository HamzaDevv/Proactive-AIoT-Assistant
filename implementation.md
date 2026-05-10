# Cloud-Native Home Assistant — Full Implementation Plan
> Cloud-Native · Mobile-First · Zero-Cost · Privacy-Preserving · Spatial Tree RAG

---

## Table of Contents
1. [Architecture Overview](#1-architecture-overview)
2. [Phase 1 — Foundation & Infrastructure](#2-phase-1--foundation--infrastructure-weeks-12)
3. [Phase 2 — Mobile Edge & PII Pipeline](#3-phase-2--mobile-edge--pii-pipeline-weeks-35)
4. [Phase 3 — Cloud Brain (Linker + LangGraph + Gemini)](#4-phase-3--cloud-brain-linker--langgraph--gemini-weeks-69)
5. [Phase 4 — Actuation Layer (HA + Matter)](#5-phase-4--actuation-layer-ha--matter-weeks-1012)
6. [Phase 5 — Testing, Polish & Hardening](#6-phase-5--testing-polish--hardening-weeks-1316)
7. [Free-Tier Limits Reference](#7-free-tier-limits-reference)
8. [Overall Timeline](#8-overall-timeline)

---

## 1. Architecture Overview

### The "Always Free" Stack

| Layer | Technology | Tier | Role |
|---|---|---|---|
| **Mobile Edge** | iOS / Android app | N/A | ASR, PII scrubbing, TTS, preference editor |
| **Logic Layer** | Render (FastAPI) | Free | Linker logic, LangGraph orchestrator, MCP client |
| **Storage** | MongoDB Atlas M0 | Free (512 MB) | Spatial tree, Markdown preferences, masked PII map |
| **Reasoning** | Gemini 2.5 Flash | Free tier | Primary LLM, tool calling, multimodal |
| **Actuation** | Home Assistant | Local | MCP server, Matter 1.5 controller |
| **Tunnel** | Cloudflare Tunnel | Free | Encrypted Render → HA bridge |

### Data Flow (End-to-End)

```
[User speaks]
      ↓
[Mobile: ASR (on-device)]
      ↓
[Mobile: Regex + registry tokenization — PII never leaves phone]
      ↓  POST tokenized payload
[Render FastAPI: Linker]
      ↓                        ↓
[MongoDB: spatial context]   [HA tunnel: current device states]
      ↓
[LangGraph: intent → sub-agent → tool calls]
      ↓
[Gemini 2.5 Flash: reasoning + MCP tool call generation]
      ↓
[Render: execute tool calls via Cloudflare Tunnel → HA → Matter 1.5]
      ↓
[Render: return tokenized response to mobile]
      ↓
[Mobile: re-hydrate tokens → real names → TTS playback]
```

### Project File Structure (Render FastAPI)

```
app/
  main.py              # FastAPI entrypoint, routes
  linker.py            # Intent → Context → Execution bridge
  models.py            # Pydantic schemas
  agents/
    orchestrator.py    # LangGraph state graph
    comfort.py         # Comfort sub-agent (lights, temp, blinds)
    security.py        # Security sub-agent (locks, cameras)
    query.py           # Pure information queries
  db/
    mongo.py           # Atlas client + spatial tree queries
  ha/
    client.py          # HA tunnel HTTP client + HMAC signing
  prompts/
    system.py          # System prompt builder (context injection)
Dockerfile
render.yaml
requirements.txt
tests/
  test_pii.py
  test_linker.py
  test_agents.py
  test_executor.py
```

---

## 2. Phase 1 — Foundation & Infrastructure (Weeks 1–2)

**Goal:** Stand up every service and configure the data schema before any application code is written.

---

### 2.1 MongoDB Atlas M0 — Spatial Schema

#### Setup
- Create a free Atlas M0 cluster (512 MB, shared, always on)
- Create database: `home_assistant`
- Create three collections: `spatial_nodes`, `preferences`, `pii_map`

#### `spatial_nodes` Document Schema

```json
{
  "_id": "lamp_living_reading",
  "path": "floor_1,living_room,reading_zone",
  "device_type": "lamp",
  "matter_id": "node-0x1A2B",
  "ha_entity_id": "light.living_room_reading_lamp",
  "neighbors": ["blind_living_reading", "therm_living"],
  "preferences_md": "# Reading Lamp\n- Color: warm white\n- Max brightness: 60%"
}
```

#### `pii_map` Document Schema (per user, stored encrypted)

```json
{
  "_id": "USER_1",
  "tokens": {
    "USER_1": "REDACTED",
    "ROOM_A": "REDACTED"
  },
  "note": "Raw PII is never stored here — this maps token → token category only"
}
```

#### Indexes to Create

```javascript
// Prefix query for neighbor fetching
db.spatial_nodes.createIndex({ "path": 1 })

// Compound for device type filtering within a zone
db.spatial_nodes.createIndex({ "path": 1, "device_type": 1 })

// For HA entity ID reverse lookup
db.spatial_nodes.createIndex({ "ha_entity_id": 1 })
```

#### Key Query — Fetch Zone Neighbors

```python
async def get_spatial_context(device_id: str) -> dict:
    node = await db.spatial_nodes.find_one({"_id": device_id})
    zone_prefix = node["path"].rsplit(",", 1)[0]  # parent zone path

    neighbors = await db.spatial_nodes.find(
        {"path": {"$regex": f"^{zone_prefix}"}},
        {"_id": 1, "device_type": 1, "preferences_md": 1, "ha_entity_id": 1}
    ).to_list(20)

    return {
        "target": node,
        "neighbors": neighbors,
        "zone": zone_prefix
    }
```

---

### 2.2 Render.com — FastAPI Service

#### Setup Steps
1. Create GitHub repo, connect to Render (free tier: 750 hrs/month)
2. Add `Dockerfile`:

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

3. `requirements.txt`:

```
fastapi
uvicorn
langgraph
langchain-google-genai
pymongo[srv]
motor
python-dotenv
python-jose[cryptography]
httpx
pydantic
python-json-logger
tenacity
```

4. Set environment variables in Render dashboard:

| Key | Value |
|---|---|
| `MONGO_URI` | Atlas connection string |
| `GEMINI_API_KEY` | Google AI Studio key |
| `HA_TUNNEL_URL` | `https://ha.yourdomain.com` |
| `TUNNEL_HMAC_SECRET` | 256-bit random secret |
| `JWT_SECRET` | App JWT signing secret |

5. `render.yaml`:

```yaml
services:
  - type: web
    name: home-assistant-brain
    env: docker
    healthCheckPath: /health
    envVars:
      - fromGroup: home-assistant-secrets
```

---

### 2.3 Gemini 2.5 Flash API

- Create Google AI Studio project → generate API key → store in Render env
- **Free tier limits:** 15 RPM, 1M tokens/min, 1,500 req/day

#### Rate Limit Handling

```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=2, max=8))
async def call_gemini(prompt: str, tools: list) -> dict:
    # Gemini API call here
    pass
```

#### Token Budget Rules
- System prompt: max 3,000 tokens
- Spatial context injection: max 1,500 tokens (truncate oldest neighbor prefs first)
- Max output tokens: 300 (command responses are short)
- Cache MongoDB context fetches: 30-second TTL in-memory LRU

---

### 2.4 Secure Tunnel — Cloudflare Tunnel

#### Setup (Recommended: Cloudflare)

```bash
# On the Home Assistant host machine
curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -o cloudflared
chmod +x cloudflared
./cloudflared login
./cloudflared tunnel create ha-tunnel
./cloudflared tunnel route dns ha-tunnel ha.yourdomain.com
```

`~/.cloudflared/config.yml`:

```yaml
tunnel: ha-tunnel
credentials-file: /root/.cloudflared/ha-tunnel.json
ingress:
  - hostname: ha.yourdomain.com
    service: http://localhost:8123
  - service: http_status:404
```

```bash
./cloudflared tunnel run ha-tunnel
```

#### Alternative: Tailscale Subnet Router
```bash
# Install Tailscale on HA host
curl -fsSL https://tailscale.com/install.sh | sh
tailscale up --advertise-routes=192.168.1.0/24 --accept-routes
# Add Render as a Tailscale node via service account key
```

#### HMAC Signature Verification (Render → HA)

```python
# Render: sign every request
import hmac, hashlib, json

def sign_request(body: dict, secret: str) -> str:
    payload = json.dumps(body, sort_keys=True).encode()
    return hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()

headers = {"X-HA-Signature": sign_request(body, TUNNEL_HMAC_SECRET)}

# HA middleware: verify before executing
def verify_signature(body: bytes, signature: str, secret: str) -> bool:
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)
```

---

## 3. Phase 2 — Mobile Edge & PII Pipeline (Weeks 3–5)

**Goal:** Build the privacy boundary. PII must never leave the device in any readable form.

---

### 3.1 Local PII Token Registry

#### iOS (Swift)

```swift
import CryptoKit
import Security

class PIIRegistry {
    private var registry: [String: String] = [:]  // "Ameer" → "USER_1"
    private let key: SymmetricKey

    init() {
        // Load or generate key in SecureEnclave
        self.key = SymmetricKey(size: .bits256)
        self.registry = loadFromKeychain()
    }

    func addEntity(_ real: String, category: TokenCategory) -> String {
        let token = generateToken(category: category)
        registry[real.lowercased()] = token
        persistToKeychain()
        return token
    }

    func tokenize(_ text: String) -> String {
        var result = text
        // Sort by length descending to avoid partial matches
        let sorted = registry.keys.sorted { $0.count > $1.count }
        for key in sorted {
            result = result.replacingOccurrences(
                of: key,
                with: registry[key]!,
                options: .caseInsensitive
            )
        }
        return result
    }

    func rehydrate(_ text: String) -> String {
        var result = text
        for (real, token) in registry {
            result = result.replacingOccurrences(of: token, with: real)
        }
        return result
    }
}

enum TokenCategory: String {
    case user = "USER"
    case room = "ROOM"
    case device = "DEVICE"
    case address = "ADDR"
    case date = "DATE"
}
```

#### Android (Kotlin)

```kotlin
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey

class PIIRegistry(context: Context) {
    private val masterKey = MasterKey.Builder(context)
        .setKeyScheme(MasterKey.KeyScheme.AES256_GCM).build()

    private val prefs = EncryptedSharedPreferences.create(
        context, "pii_registry", masterKey,
        EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
        EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
    )

    fun tokenize(text: String): String {
        var result = text
        val entries = prefs.all.entries.sortedByDescending { it.key.length }
        for ((real, token) in entries) {
            result = result.replace(real, token.toString(), ignoreCase = true)
        }
        return result
    }
}
```

---

### 3.2 Voice ASR + Regex Scrubbing Pipeline

#### iOS ASR (On-Device)

```swift
import Speech

class VoicePipeline {
    let recognizer = SFSpeechRecognizer(locale: Locale(identifier: "en-US"))!
    let registry: PIIRegistry

    func startListening(completion: @escaping (String) -> Void) {
        let request = SFSpeechAudioBufferRecognitionRequest()
        request.requiresOnDeviceRecognition = true  // CRITICAL: no Apple servers
        request.shouldReportPartialResults = false

        recognizer.recognitionTask(with: request) { result, error in
            if let transcript = result?.bestTranscription.formattedString {
                let tokenized = self.scrub(transcript)
                completion(tokenized)
            }
        }
    }

    func scrub(_ text: String) -> String {
        var result = registry.tokenize(text)  // Stage 1: registry
        result = applyRegex(result)            // Stage 2: regex sweep
        return result
    }
}
```

#### Regex Patterns (Swift)

```swift
let patterns: [(NSRegularExpression, String)] = [
    // Phone numbers
    (try! NSRegularExpression(pattern: #"(\+?\d[\d\s\-().]{7,}\d)"#), "PHONE_REDACTED"),
    // Email addresses
    (try! NSRegularExpression(pattern: #"[\w._%+\-]+@[\w.\-]+\.[a-zA-Z]{2,}"#), "EMAIL_REDACTED"),
    // Street addresses
    (try! NSRegularExpression(pattern: #"\d{1,5}\s+\w+(\s+\w+){1,4}\s+(St|Ave|Rd|Blvd|Ln|Dr|Street|Avenue)"#, options: .caseInsensitive), "ADDR_REDACTED"),
    // IP addresses
    (try! NSRegularExpression(pattern: #"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b"#), "IP_REDACTED"),
]

func applyRegex(_ text: String) -> String {
    var result = text
    for (regex, replacement) in patterns {
        result = regex.stringByReplacingMatches(
            in: result, range: NSRange(result.startIndex..., in: result),
            withTemplate: replacement
        )
    }
    return result
}
```

---

### 3.3 API Client — Mobile → Render

```swift
struct CommandRequest: Codable {
    let payload: String          // Tokenized text
    let userToken: String        // e.g. "USER_1"
    let contextDeviceId: String  // e.g. "lamp_living_reading"
}

class RenderClient {
    let baseURL = "https://your-app.onrender.com"

    func sendCommand(_ payload: String, deviceId: String) async throws -> String {
        let body = CommandRequest(
            payload: payload,
            userToken: currentUserToken,
            contextDeviceId: deviceId
        )
        var request = URLRequest(url: URL(string: "\(baseURL)/command")!)
        request.method = .post
        request.setValue("Bearer \(jwt)", forHTTPHeaderField: "Authorization")
        request.httpBody = try JSONEncoder().encode(body)

        let (data, _) = try await URLSession.shared.data(for: request)
        let response = try JSONDecoder().decode(CommandResponse.self, from: data)
        return registry.rehydrate(response.message)  // Re-hydrate before TTS
    }

    // Keep-alive: ping every 10 minutes to prevent Render free tier from sleeping
    func startKeepAlive() {
        Timer.scheduledTimer(withTimeInterval: 600, repeats: true) { _ in
            Task { try? await URLSession.shared.data(from: URL(string: "\(self.baseURL)/health")!) }
        }
    }
}
```

---

### 3.4 TTS Playback

```swift
import AVFoundation

class TTSPlayer {
    let synthesizer = AVSpeechSynthesizer()
    let registry: PIIRegistry

    func speak(_ tokenizedText: String) {
        let real = registry.rehydrate(tokenizedText)
        let utterance = AVSpeechUtterance(string: real)
        utterance.voice = AVSpeechSynthesisVoice(language: "en-US")
        utterance.rate = 0.52
        utterance.pitchMultiplier = 1.0
        synthesizer.speak(utterance)
    }
}
```

---

### 3.5 Markdown Preference Editor

#### UI Screens
1. **Room tree browser** — shows floor → room → device hierarchy fetched from `GET /spatial/tree`
2. **Device detail** — shows current preference Markdown, last-modified timestamp
3. **Editor view** — monospaced editor with live preview pane; on save: `PATCH /preferences/{device_id}`
4. **Template picker** — 10 built-in templates (Movie Night, Reading, Sleep, Work, Morning, Party, Away, Guest, Study, Cooking)

#### Example Preference Markdown

```markdown
# Reading Lamp — Living Room

## Contexts
- **reading**: warm white (2700K), 40% brightness
- **movie**: off
- **ambient**: warm white, 20%
- **morning**: cool white (5000K), 80%, gradual 5min rise

## Rules
- Never exceed 70% brightness after 21:00
- Sync with blind_living_reading when context = reading
- If USER_1 says "dim", reduce by 20% from current

## Notes
Paired Matter device: node-0x1A2B
```

---

## 4. Phase 3 — Cloud Brain: Linker + LangGraph + Gemini (Weeks 6–9)

**Goal:** Build the full cloud reasoning pipeline — from tokenized payload to tool-call dispatch.

---

### 4.1 FastAPI Endpoints

```python
from fastapi import FastAPI, Depends, HTTPException
from app.models import CommandRequest, CommandResponse, PreferenceUpdate

app = FastAPI()

@app.post("/command", response_model=CommandResponse)
async def handle_command(req: CommandRequest, user=Depends(verify_jwt)):
    return await linker.process(req)

@app.get("/state/{device_id}")
async def get_state(device_id: str, user=Depends(verify_jwt)):
    return await ha_client.get_state(device_id)

@app.patch("/preferences/{device_id}")
async def update_preference(device_id: str, body: PreferenceUpdate, user=Depends(verify_jwt)):
    await db.spatial_nodes.update_one(
        {"_id": device_id},
        {"$set": {"preferences_md": body.markdown}}
    )
    return {"status": "updated"}

@app.get("/spatial/tree")
async def get_tree(user=Depends(verify_jwt)):
    nodes = await db.spatial_nodes.find({}, {"_id":1,"path":1,"device_type":1}).to_list(500)
    return build_tree(nodes)

@app.post("/spatial/node")
async def add_node(node: SpatialNode, user=Depends(verify_jwt)):
    await db.spatial_nodes.insert_one(node.dict())

@app.get("/health")
async def health():
    return {"status": "ok"}
```

---

### 4.2 The Linker (linker.py)

```python
class Linker:
    async def process(self, req: CommandRequest) -> CommandResponse:
        # 1. Fetch spatial context from MongoDB
        spatial_ctx = await mongo.get_spatial_context(req.context_device_id)

        # 2. Fetch current HA device states in parallel
        ha_states = await ha_client.get_zone_states(spatial_ctx["zone"])

        # 3. Build system prompt with injected context
        system_prompt = prompt_builder.build(
            spatial_ctx=spatial_ctx,
            ha_states=ha_states
        )

        # 4. Run LangGraph orchestration
        result = await orchestrator.run(
            payload=req.payload,
            system_prompt=system_prompt,
            user_token=req.user_token
        )

        # 5. Execute tool calls via HA tunnel
        execution_results = await executor.run(result.tool_calls)

        # 6. Return tokenized response
        return CommandResponse(
            message=result.response,
            actions_taken=execution_results
        )
```

---

### 4.3 LangGraph Multi-Agent Orchestrator

```python
from langgraph.graph import StateGraph, END
from typing import TypedDict

class AgentState(TypedDict):
    payload: str
    system_prompt: str
    intent: str
    spatial_ctx: dict
    ha_states: dict
    agent_plan: list
    tool_calls: list
    response: str

def build_graph():
    graph = StateGraph(AgentState)

    graph.add_node("intent_classifier", classify_intent)
    graph.add_node("comfort_agent", run_comfort_agent)
    graph.add_node("security_agent", run_security_agent)
    graph.add_node("query_agent", run_query_agent)
    graph.add_node("command_executor", execute_commands)
    graph.add_node("response_formatter", format_response)

    graph.set_entry_point("intent_classifier")

    graph.add_conditional_edges("intent_classifier", route_by_intent, {
        "comfort": "comfort_agent",
        "security": "security_agent",
        "query": "query_agent",
        "unknown": "response_formatter"
    })

    for agent in ["comfort_agent", "security_agent", "query_agent"]:
        graph.add_edge(agent, "command_executor")

    graph.add_edge("command_executor", "response_formatter")
    graph.add_edge("response_formatter", END)

    return graph.compile()

async def classify_intent(state: AgentState) -> AgentState:
    # Quick Gemini call (low token cost) to classify intent
    intent = await gemini.classify(state["payload"])
    return {**state, "intent": intent}

def route_by_intent(state: AgentState) -> str:
    return state["intent"]
```

---

### 4.4 Gemini System Prompt Engineering

```python
class PromptBuilder:
    def build(self, spatial_ctx: dict, ha_states: dict) -> str:
        target = spatial_ctx["target"]
        neighbors = spatial_ctx["neighbors"]

        context_block = f"""
## Target Device
- ID: {target['_id']}
- Type: {target['device_type']}
- Path: {target['path']}

{target.get('preferences_md', '(no preferences set)')}

## Neighbor Devices in Zone
"""
        for n in neighbors[:5]:  # Cap at 5 neighbors to control token count
            state = ha_states.get(n["ha_entity_id"], "unknown")
            context_block += f"""
### {n['_id']} ({n['device_type']}) — current state: {state}
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
```

---

### 4.5 MCP Tool Definitions (Passed to Gemini)

```python
MCP_TOOLS = [
    {
        "name": "set_device_state",
        "description": "Turn a device on/off and set its attributes (brightness, temperature, position).",
        "parameters": {
            "type": "object",
            "properties": {
                "device_id": {"type": "string", "description": "Spatial node _id"},
                "state": {"type": "string", "enum": ["on", "off"]},
                "brightness": {"type": "integer", "minimum": 0, "maximum": 100},
                "color_temp": {"type": "string", "enum": ["warm", "neutral", "cool"]},
                "position": {"type": "integer", "minimum": 0, "maximum": 100, "description": "For blinds: 0=closed, 100=open"}
            },
            "required": ["device_id", "state"]
        }
    },
    {
        "name": "get_device_state",
        "description": "Get the current state and attributes of a device.",
        "parameters": {
            "type": "object",
            "properties": {
                "device_id": {"type": "string"}
            },
            "required": ["device_id"]
        }
    },
    {
        "name": "set_scene",
        "description": "Activate a named Home Assistant scene for a room.",
        "parameters": {
            "type": "object",
            "properties": {
                "scene_id": {"type": "string", "description": "HA scene entity ID"}
            },
            "required": ["scene_id"]
        }
    },
    {
        "name": "schedule_command",
        "description": "Schedule a device command to execute after a delay.",
        "parameters": {
            "type": "object",
            "properties": {
                "device_id": {"type": "string"},
                "state": {"type": "string"},
                "delay_minutes": {"type": "integer"}
            },
            "required": ["device_id", "state", "delay_minutes"]
        }
    }
]
```

---

### 4.6 Agentic Intuition — Expected Behaviors

| User says | Expected LLM behavior |
|---|---|
| "reading mode" | Dim lamp to 40% warm white, close blinds to 30%, set thermostat to 21°C |
| "good morning" | Raise blinds gradually over 10 min, lamp to 80% cool white |
| "movie" | Dim all zone lights to 5%, close blinds fully, skip thermostat unless pref says so |
| "sleep" | Turn off all lights in zone, lock doors if security pref enabled, set thermostat to 18°C |
| "I'm leaving" | Trigger away scene: all lights off, lock front door, set thermostat to eco mode |

---

## 5. Phase 4 — Actuation Layer: HA + Matter (Weeks 10–12)

**Goal:** Home Assistant becomes the trusted local executor — receiving verified commands, controlling Matter 1.5 devices, and returning state confirmation.

---

### 5.1 HA MCP Server Add-on

Create a custom HA add-on (`mcp_server.py`) that listens on port 9000:

```python
from aiohttp import web
import hmac, hashlib, json
import aiohttp

HA_BASE = "http://localhost:8123"
HA_TOKEN = os.environ["HA_LONG_LIVED_TOKEN"]
HMAC_SECRET = os.environ["TUNNEL_HMAC_SECRET"]

async def handle_mcp(request):
    body = await request.read()

    # Verify HMAC signature from Render
    sig = request.headers.get("X-HA-Signature", "")
    expected = hmac.new(HMAC_SECRET.encode(), body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, sig):
        raise web.HTTPForbidden()

    call = json.loads(body)
    tool_name = call["tool"]
    params = call["params"]

    if tool_name == "set_device_state":
        result = await set_device_state(params)
    elif tool_name == "get_device_state":
        result = await get_device_state(params)
    elif tool_name == "set_scene":
        result = await set_scene(params)

    return web.json_response(result)

async def set_device_state(params: dict) -> dict:
    node = await mongo_lookup(params["device_id"])  # Get ha_entity_id
    entity_id = node["ha_entity_id"]
    domain = entity_id.split(".")[0]

    service_data = {"entity_id": entity_id}
    if "brightness" in params:
        service_data["brightness_pct"] = params["brightness"]
    if "color_temp" in params:
        service_data["kelvin"] = {"warm": 2700, "neutral": 3500, "cool": 5000}[params["color_temp"]]
    if "position" in params:
        service_data["position"] = params["position"]

    service = "turn_on" if params["state"] == "on" else "turn_off"
    if domain == "cover":
        service = "set_cover_position"

    async with aiohttp.ClientSession() as session:
        await session.post(
            f"{HA_BASE}/api/services/{domain}/{service}",
            json=service_data,
            headers={"Authorization": f"Bearer {HA_TOKEN}"}
        )

    # Verify state changed
    await asyncio.sleep(1.5)
    return await get_device_state({"device_id": params["device_id"]})

app = web.Application()
app.router.add_post("/mcp", handle_mcp)
web.run_app(app, port=9000)
```

---

### 5.2 Matter 1.5 Device Types & Clusters

| Device Type | Matter Cluster IDs | HA Entity Domain |
|---|---|---|
| Light (on/off + dim) | 0x0006 (On/Off), 0x0008 (Level Control) | `light` |
| Light (color temp) | 0x0300 (Color Control) | `light` |
| Thermostat | 0x0201 (Thermostat) | `climate` |
| Window covering / blind | 0x0102 (Window Covering) | `cover` |
| Door lock | 0x0101 (Door Lock) | `lock` |
| Contact sensor | 0x0045 (Boolean State) | `binary_sensor` |
| Motion sensor | 0x0406 (Occupancy Sensing) | `binary_sensor` |

#### Device Onboarding Sync Script

```python
# Run once after adding new Matter devices in HA
async def sync_devices_to_mongodb():
    async with aiohttp.ClientSession() as session:
        resp = await session.get(
            f"{HA_BASE}/api/states",
            headers={"Authorization": f"Bearer {HA_TOKEN}"}
        )
        states = await resp.json()

    for entity in states:
        if entity["entity_id"].split(".")[0] in ["light", "climate", "cover", "lock"]:
            await db.spatial_nodes.update_one(
                {"ha_entity_id": entity["entity_id"]},
                {"$setOnInsert": {
                    "_id": entity["entity_id"].replace(".", "_"),
                    "ha_entity_id": entity["entity_id"],
                    "device_type": entity["entity_id"].split(".")[0],
                    "path": "floor_1,unassigned",  # User assigns in mobile app
                    "preferences_md": ""
                }},
                upsert=True
            )
    print(f"Synced {len(states)} entities to MongoDB")
```

---

### 5.3 Command Executor & Confirmation Loop (Render side)

```python
class CommandExecutor:
    async def run(self, tool_calls: list) -> list:
        results = []
        for call in tool_calls:
            result = await self.execute_with_retry(call)
            results.append(result)
        return results

    async def execute_with_retry(self, call: dict, max_attempts=2) -> dict:
        for attempt in range(max_attempts):
            response = await ha_client.call_mcp_tool(
                tool=call["name"],
                params=call["parameters"]
            )
            if response.get("state") == call["parameters"].get("state"):
                return {"success": True, "device": call["parameters"]["device_id"]}
            await asyncio.sleep(1.5)

        return {"success": False, "device": call["parameters"]["device_id"], "error": "State did not change"}
```

---

## 6. Phase 5 — Testing, Polish & Hardening (Weeks 13–16)

---

### 6.1 Latency Budget

| Stage | Target |
|---|---|
| ASR (on-device) | ~400 ms |
| PII scrubbing | ~20 ms |
| Network → Render | ~100 ms |
| MongoDB spatial query | ~80 ms |
| HA state fetch (parallel) | ~150 ms |
| Gemini API call | ~900 ms |
| MCP tool execution | ~200 ms |
| Network → mobile | ~100 ms |
| TTS (on-device) | ~300 ms |
| **Total** | **~2,250 ms** |

#### Optimization Techniques
- Pre-fetch HA device states on app open with 30-second TTL — skip at command time
- MongoDB projection: only fetch `_id`, `device_type`, `preferences_md`, `ha_entity_id` — no full docs
- Gemini: `maxOutputTokens: 300` for command responses
- Pipeline TTS start immediately on first sentence (streaming)
- In-memory LRU cache for spatial context (TTL: 60s, max 50 entries)

---

### 6.2 Test Suite

```python
# tests/test_pii.py
def test_name_scrubbing():
    registry = PIIRegistry({"ameer": "USER_1", "master bedroom": "ROOM_A"})
    result = registry.tokenize("Ameer is in the Master Bedroom")
    assert "Ameer" not in result
    assert "Master Bedroom" not in result
    assert "USER_1" in result
    assert "ROOM_A" in result

def test_partial_match_safety():
    registry = PIIRegistry({"am": "USER_X", "ameer": "USER_1"})
    # "ameer" should match before "am" (longest-first ordering)
    result = registry.tokenize("Ameer is here")
    assert result == "USER_1 is here"

def test_email_regex():
    result = scrub("Send it to john@example.com please")
    assert "john@example.com" not in result

# tests/test_linker.py
@pytest.mark.asyncio
async def test_reading_intent_produces_correct_tools(mock_mongo, mock_gemini):
    req = CommandRequest(
        payload="USER_1 wants reading mode in ROOM_A",
        user_token="USER_1",
        context_device_id="lamp_living_reading"
    )
    result = await linker.process(req)
    tool_names = [tc["name"] for tc in result.tool_calls]
    assert "set_device_state" in tool_names

# tests/test_agents.py
@pytest.mark.asyncio
async def test_comfort_agent_routing():
    state = AgentState(payload="dim the lights", intent="comfort", ...)
    result = await comfort_agent(state)
    assert len(result["agent_plan"]) > 0

# tests/test_executor.py
@pytest.mark.asyncio
async def test_executor_retries_on_failure(mock_ha_client):
    mock_ha_client.set_to_fail_once()
    result = await executor.execute_with_retry({"name": "set_device_state", ...})
    assert mock_ha_client.call_count == 2
```

#### Intent Test Matrix (minimum 30 phrases)

```python
INTENT_MATRIX = [
    ("reading mode please", "comfort", ["set_device_state"]),
    ("turn off everything in ROOM_A", "comfort", ["set_device_state"]),
    ("what's the temperature right now", "query", ["get_device_state"]),
    ("lock the front door", "security", ["set_device_state"]),
    ("good morning", "comfort", ["set_device_state"]),
    ("movie time", "comfort", ["set_device_state", "set_scene"]),
    ("I'm going to bed", "comfort", ["set_device_state"]),
    ("set a timer for 30 minutes then dim", "comfort", ["schedule_command"]),
    # ... 22 more phrases
]

@pytest.mark.asyncio
@pytest.mark.parametrize("phrase,expected_intent,expected_tools", INTENT_MATRIX)
async def test_intent_matrix(phrase, expected_intent, expected_tools, mock_gemini):
    result = await linker.process(CommandRequest(payload=phrase, ...))
    assert result.intent == expected_intent
```

---

### 6.3 Error Handling & Graceful Degradation

| Failure | Response |
|---|---|
| Gemini 429 (rate limit) | Exponential backoff (2s→4s→8s), then return friendly "temporarily overloaded" message |
| Gemini quota exhausted | Fall back to simple rule-based command parser for basic on/off commands |
| Tunnel down | Return "Can't reach your home — check the local bridge is running" |
| Render cold start | Mobile keep-alive ping every 10 minutes prevents sleep |
| MongoDB unavailable | Serve in-memory cached spatial context (LRU, 5-min TTL) |
| ASR failure | Auto-show text input fallback on mobile |
| HA entity not found | Return "Device not found — please resync your devices" |
| PII leak guard | Before returning response to mobile, scan for any registry keys → redact + log alert |

#### PII Leak Guard (Render)

```python
def pii_leak_guard(response: str, registry_keys: list) -> str:
    for key in registry_keys:
        if key.lower() in response.lower():
            logger.error(f"PII LEAK DETECTED: '{key}' found in LLM response")
            response = response.replace(key, "[REDACTED]")
    return response
```

---

### 6.4 Monitoring (Free Tier)

| Tool | Purpose | Limit |
|---|---|---|
| Render logs (built-in) | Structured JSON logs, searchable in dashboard | 7-day retention |
| Betterstack Logtail | Extended log history, alerts | 1 GB/month free |
| MongoDB Atlas Metrics | Query performance, storage, index usage | Built-in, always free |
| Sentry (free tier) | Mobile crash reporting (iOS + Android) | 5,000 errors/month |
| Custom `/metrics` endpoint | Gemini call count, avg latency, error rate | Self-hosted |

#### Custom Metrics Endpoint

```python
@app.get("/metrics")
async def metrics(admin=Depends(verify_admin)):
    return {
        "gemini_calls_today": await get_counter("gemini_calls"),
        "avg_latency_ms": await get_avg_latency(last_n=100),
        "error_rate_1h": await get_error_rate(window_minutes=60),
        "mongo_context_cache_hit_rate": context_cache.hit_rate(),
        "ha_tunnel_status": await ha_client.ping()
    }
```

---

## 7. Free-Tier Limits Reference

| Service | Limit | Impact |
|---|---|---|
| **Render** | 750 hrs/month, sleeps after 15 min idle | Use keep-alive pings from mobile app |
| **MongoDB Atlas M0** | 512 MB storage, 100 connections | ~500,000 devices/preferences before hitting limit |
| **Gemini 2.5 Flash** | 1,500 req/day, 15 RPM, 1M tokens/min | ~1,500 voice commands/day — sufficient for household |
| **Cloudflare Tunnel** | Unlimited bandwidth | No practical limit |
| **Tailscale** | 3 users, 100 devices | Sufficient for household |
| **Betterstack** | 1 GB logs/month | ~10M log lines/month |
| **Sentry** | 5,000 errors/month | Sufficient for personal app |

---

## 8. Overall Timeline

| Phase | Focus | Duration |
|---|---|---|
| **Phase 1** | Infrastructure: MongoDB schema, Render setup, Gemini account, Cloudflare tunnel | Weeks 1–2 |
| **Phase 2** | Mobile: PII registry, ASR pipeline, TTS, Markdown preference editor | Weeks 3–5 |
| **Phase 3** | Cloud brain: Linker, LangGraph agents, Gemini prompt engineering, FastAPI endpoints | Weeks 6–9 |
| **Phase 4** | Actuation: HA MCP server, Matter 1.5 pairing, device sync, command executor | Weeks 10–12 |
| **Phase 5** | Testing, latency optimization, error handling, monitoring | Weeks 13–16 |
| **Total** | | **~16 weeks (solo developer)** |

---

## Appendix: Key Design Decisions

### Why Materialized Paths over Nested Documents?
A single `$regex` prefix query (`^floor_1,living_room`) fetches all devices in a zone in one round-trip — no recursive queries, no application-side tree traversal. This is what makes neighbor-context fetching fast enough to include in the real-time voice pipeline.

### Why Markdown for Preferences?
Markdown is human-readable, directly injectable into the LLM system prompt without transformation, and trivially editable by non-technical users. It also version-controls cleanly in MongoDB's document history.

### Why not a local LLM?
Local LLMs (Phi-3, Gemma-2B) drain mobile battery, can't handle complex multi-device reasoning at acceptable latency, and require significant on-device storage. Gemini 2.5 Flash's free tier (1,500 req/day) is sufficient for household use and delivers far superior reasoning quality.

### Why HMAC over mTLS for the tunnel?
mTLS requires certificate management infrastructure. HMAC with a pre-shared 256-bit secret provides equivalent request-level integrity verification with zero certificate overhead, and is trivially implemented in both Python and the HA add-on.

### The PII Boundary is Non-Negotiable
Every design decision that touches privacy follows one rule: **the cloud never sees real identities, ever.** The token registry lives only on the user's device, encrypted in the hardware security module. If the Render server is compromised, the attacker sees only `USER_1 wants ROOM_A lamp on` — meaningless without the local registry.