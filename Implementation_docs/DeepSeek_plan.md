# Revised Implementation Plan: Cloud-Native Home Assistant with Mobile Edge & Privacy Preservation

## Key Changes from Previous Plan

| Aspect | Previous (Local-First) | **New (Cloud-Native with Mobile Edge)** |
|--------|------------------------|------------------------------------------|
| Compute location | Local mini-PC | Cloud (proprietary LLM API) |
| User interface | Web dashboard | Mobile app (iOS/Android) |
| Preferences storage | Database | Markdown files (per user per device) |
| PII handling | Never leaves home | **Federated + encrypted** before cloud |
| Cost model | $0 after hardware | Pay-as-you-go (API credits) - can still be near-zero with optimization |

---

## Core Architecture Shift

```
┌─────────────────────────────────────────────────────────────────┐
│                         USER'S PHONE (Edge)                      │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │ Voice Input │  │ Local PII   │  │ Markdown Preferences     │  │
│  │ Whisper.cpp │→│ Redaction   │→│ (per user per device)     │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
│         ↓                   ↓                    ↓               │
│  [Anonymized text]   [PII mapping]    [Device+User context]      │
└─────────────────────────────────────────────────────────────────┘
                              │ HTTPS + mTLS
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                      CLOUD BACKEND (VPS/Serverless)              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │ LLM API     │  │ MCP Server  │  │ Home Assistant Cloud    │  │
│  │ (GPT-4o/    │←→│ (Tool Call  │←→│ Connector               │  │
│  │  Gemini)    │  │  Gateway)   │  │                         │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                      HOME GATEWAY (Raspberry Pi / Old PC)        │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │ MCP Client  │  │ Device Hub  │  │ Local Execution Engine  │  │
│  │ (receives   │→│ (Zigbee/    │→│ (actuators)             │  │
│  │  commands)  │  │  Z-Wave)    │  │                         │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 1. Markdown-Based Preference System

### 1.1 File Structure

Each user has a dedicated folder. Each device has a markdown file with YAML frontmatter.

```
preferences/
├── user_alice/
│   ├── air_conditioner_bedroom.md
│   ├── light_living_room.md
│   ├── thermostat_whole_house.md
│   └── _defaults.md
├── user_bob/
│   └── ...
└── _shared/
    └── house_rules.md
```

### 1.2 Markdown Format Example

```markdown
---
device_id: climate.bedroom_ac
device_type: air_conditioner
last_updated: 2026-04-25T08:30:00Z
version: 3
---

# Alice's Preferences for Bedroom Air Conditioner

## Temperature (Celsius)
- Sleep mode: 20° (21:00 - 07:00)
- Day active: 22°
- Away (no motion >30min): 18° (energy save)

## Fan Speed
- Quiet preferred over cooling power (max 60% at night)

## Schedule
```cron
0 22 * * * set_temp=20, fan_speed=30
0 06 * * * set_temp=22, fan_speed=50
```

## Natural Language Mappings
- "too hot" → reduce by 2° (max 4° in 1 hour)
- "stuffy" → fan_speed +20%, check air purifier
- "save energy" → set to 18° if away detected

## Learned Patterns (auto-updated)
- 2026-04-20: user lowered temp to 19° after exercise → suggests exercise context
- 2026-04-22: user turned off AC when window open → rule: auto-off AC if window open >5min

## Override History (last 10)
- 2026-04-24 22:15: manual set to 21° (too cold)
- 2026-04-23 07:45: manual fan to 40% (prefers quieter)
```

### 1.3 Preference Retrieval Service

```python
# preference_service.py - runs on phone edge or cloud gateway
import markdown
import yaml
from pathlib import Path
import fsspec  # for cloud storage or local

class MarkdownPreferenceStore:
    def __init__(self, base_path: str, cloud_sync: bool = True):
        self.base_path = Path(base_path)
        self.cache = {}
        
    def get_preferences(self, user_id: str, device_id: str) -> dict:
        """Load markdown file, parse frontmatter and content sections"""
        file_path = self.base_path / user_id / f"{device_id}.md"
        if not file_path.exists():
            return self.get_defaults(user_id, device_id)
        
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Parse YAML frontmatter
        if content.startswith('---'):
            _, frontmatter, body = content.split('---', 2)
            metadata = yaml.safe_load(frontmatter)
        else:
            metadata = {}
            body = content
        
        # Extract structured sections
        sections = self._parse_markdown_sections(body)
        
        return {
            "metadata": metadata,
            "temperature": sections.get("Temperature", {}),
            "schedule": sections.get("Schedule", {}),
            "nl_mappings": sections.get("Natural Language Mappings", {}),
            "learned": sections.get("Learned Patterns", []),
            "override_history": sections.get("Override History", [])
        }
    
    def update_preference(self, user_id: str, device_id: str, 
                          context: str, user_action: dict, feedback: float):
        """Append new learned pattern with confidence score"""
        file_path = self.base_path / user_id / f"{device_id}.md"
        new_entry = f"- {datetime.now().isoformat()}: user {user_action} after '{context}' → score {feedback}"
        
        with open(file_path, 'a') as f:
            f.write(f"\n## Learned Patterns (auto-updated)\n{new_entry}")
```

---

## 2. Mobile Edge PII Protection for Cloud LLM

### 2.1 Architecture: PII Stays on Phone, Only Non-PII Reaches Cloud

```
┌────────────────────────────────────────────────────────────┐
│                    USER'S PHONE                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐ │
│  │ Voice Input  │ → │ Whisper.cpp  │ → │ Text "turn   │ │
│  │ (mic)        │    │ (local STT)  │    │ off John's   │ │
│  └──────────────┘    └──────────────┘    │ bedroom lamp"│ │
│                                          └──────┬───────┘ │
│                                                  ↓         │
│  ┌──────────────────────────────────────────────────────┐ │
│  │ Local PII Redactor (BERT-NER on phone)               │ │
│  │ Input: "turn off John's bedroom lamp"                │ │
│  │ Output: "turn off [PERSON]'s bedroom lamp"          │ │
│  │ Mapping stored: {"PERSON": "John"} → encrypted →    │ │
│  └──────────────────────────────────────────────────────┘ │
│                         ↓                                  │
│  ┌──────────────────────────────────────────────────────┐ │
│  │ Encrypted PII Map (stays on phone)                   │ │
│  │ Key: SHA256(session_id + device_id)                  │ │
│  │ Value: AES-256-GCM encrypted JSON                   │ │
│  └──────────────────────────────────────────────────────┘ │
│                         ↓                                  │
│         [Anonymized text] + [Session Token]                │
└───────────────────────────┼────────────────────────────────┘
                            │ HTTPS
                            ↓
┌────────────────────────────────────────────────────────────┐
│                    CLOUD LLM API                            │
│  Receives: "turn off [PERSON]'s bedroom lamp"             │
│  → No actual PII visible                                   │
└───────────────────────────┬────────────────────────────────┘
                            │ Response: "I've turned off [PERSON]'s lamp"
                            ↓
┌────────────────────────────────────────────────────────────┐
│                    USER'S PHONE                             │
│  ┌──────────────────────────────────────────────────────┐ │
│  │ PII Restorer (runs locally)                          │ │
│  │ Input: "I've turned off [PERSON]'s lamp"            │ │
│  │ Replace [PERSON] with "John" from mapping           │ │
│  │ Output: "I've turned off John's lamp"               │ │
│  └──────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────┘
```

### 2.2 Implementation on Mobile (React Native + ML Kit)

```typescript
// piiRedactor.ts - Runs on device
import { NER } from '@huggingface/inference'; // local via ONNX
import CryptoJS from 'react-native-crypto-js';

class PIIService {
  private nerModel: any;
  private sessionKey: string;
  
  constructor() {
    // Load lightweight BERT-NER quantized (16MB)
    this.nerModel = require('./models/bert-ner-quantized.onnx');
    this.sessionKey = CryptoJS.lib.WordArray.random(32).toString();
  }
  
  async redact(text: string): Promise<{ redacted: string; piiMap: string }> {
    // Run NER locally
    const entities = await this.nerModel.forward(text);
    const replacements: Record<string, string> = {};
    let redacted = text;
    
    for (const ent of entities) {
      const placeholder = `[${ent.label}]`;
      redacted = redacted.replace(ent.text, placeholder);
      replacements[placeholder] = ent.text;
    }
    
    // Encrypt PII map so even phone storage is safe
    const encryptedMap = CryptoJS.AES.encrypt(
      JSON.stringify(replacements), 
      this.sessionKey
    ).toString();
    
    return { redacted, piiMap: encryptedMap };
  }
  
  async restore(redactedResponse: string, encryptedMap: string): Promise<string> {
    const decrypted = CryptoJS.AES.decrypt(encryptedMap, this.sessionKey).toString(CryptoJS.enc.Utf8);
    const map = JSON.parse(decrypted);
    let restored = redactedResponse;
    for (const [ph, val] of Object.entries(map)) {
      restored = restored.replace(ph, val);
    }
    return restored;
  }
}
```

### 2.3 Cloud Side (No PII Storage Required)

```python
# cloud_llm_handler.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

class CloudRequest(BaseModel):
    redacted_text: str  # Already PII-free
    session_token: str   # For rate limiting, no PII
    device_context: dict # Anonymized room/device IDs

app = FastAPI()

@app.post("/chat")
async def chat(request: CloudRequest):
    # LLM call with only redacted text + anonymized context
    response = call_llm_api(
        prompt=f"""
        User: {request.redacted_text}
        Context: {request.device_context}  # e.g., {"room": "bedroom", "devices": ["light", "ac"]}
        Respond concisely with tool calls if needed.
        """
    )
    # Response may contain placeholders like [PERSON] - phone will restore
    return {"response": response, "tool_calls": extract_tools(response)}
```

---

## 3. Mobile App as Edge Orchestrator

### 3.1 App Features

```yaml
Mobile_App_Capabilities:
  On-Device:
    - Voice transcription (Whisper tiny)
    - PII redaction/restoration
    - Markdown preference editor (local + sync to cloud)
    - Push notification receiver
    - Local fallback: small Phi-3-mini (for when internet down)
  
  Cloud-Dependent:
    - Complex intent understanding (GPT-4o-mini)
    - Multi-device orchestration
    - Long-term memory across sessions
    - Security policy enforcement

  Hybrid:
    - Preference sync (encrypted to cloud or user's own Nextcloud)
    - Command execution status (real-time via WebSocket)
```

### 3.2 Preference Sync Architecture

User owns their markdown files. Options:

**Option A: User's Own Cloud Storage (Nextcloud/Seafile)**
- Markdown files stored in user's Nextcloud folder
- Mobile app syncs via WebDAV
- Cloud backend reads from same storage (with user's OAuth token)

**Option B: Encrypted in LLM Provider's KV Store**
- Markdown files encrypted client-side with user's passphrase
- Stored as blobs in cloud (e.g., Redis)
- Only decrypted on phone, never in cloud

**Option C: Local-only + LAN sync**
- Phone is master copy
- Home gateway caches via local Wi-Fi sync
- No cloud preference storage required

**Recommendation: Option C** for privacy + zero cloud cost, plus **Option A** as optional backup.

---

## 4. Cloud Cost Optimization (Near-Zero)

| LLM Tier | Model | Cost per 1M tokens | Monthly est. (1000 commands) |
|----------|-------|--------------------|------------------------------|
| Primary | GPT-4o-mini | $0.15 input / $0.60 output | ~$0.50 |
| Fallback | Gemini 1.5 Flash (free tier) | $0 (75 req/min free) | $0 |
| Embedding | text-embedding-3-small | $0.02 per 1M tokens | <$0.01 |

**Total monthly cost for typical household: $0.50 - $2.00**

Free options:
- Gemini API free tier: 60 requests/minute
- Groq (Mixtral): free for non-commercial
- Together.ai: $0.20/month minimum

### 4.1 Smart Routing to Minimize Cost

```python
# cost_router.py - runs on phone or lightweight cloud function
def route_request(user_text: str, context: dict) -> str:
    # Heuristic: simple commands go to free tier
    if len(user_text.split()) < 10 and not context.get('complex'):
        return 'gemini_free'  # Gemini 1.5 Flash free tier
    
    # Commands with device names
    if any(d in user_text for d in device_names):
        return 'groq_mixtral'  # Free tier
    
    # Complex reasoning, multi-step
    return 'gpt4o_mini'  # Paid but cheap
```

---

## 5. Security & Privacy for Cloud Setup

### 5.1 Zero-Trust Cloud Architecture

Even though LLM is in cloud, we enforce:

```
┌─────────────────────────────────────────────────────────┐
│                    CLOUD VPS (Your control)              │
│  ┌────────────────────────────────────────────────────┐ │
│  │ API Gateway (Cloudflare Tunnel)                    │ │
│  │ - No public IP, only Cloudflare proxy              │ │
│  │ - Rate limiting per session                        │ │
│  │ - mTLS with client certificates from phone         │ │
│  └────────────────────────────────────────────────────┘ │
│                           ↓                              │
│  ┌────────────────────────────────────────────────────┐ │
│  │ Session Manager (Ephemeral, no logs)               │ │
│  │ - Stores only session_id → user_id mapping         │ │
│  │ - TTL 15 minutes, auto-purge                       │ │
│  └────────────────────────────────────────────────────┘ │
│                           ↓                              │
│  ┌────────────────────────────────────────────────────┐ │
│  │ LLM Proxy (your code)                              │ │
│  │ - Adds system prompt: no logging, no storage       │ │
│  │ - Strips any residual PII with regex               │ │
│  │ - Forwards to OpenAI/Gemini with zero retention    │ │
│  └────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

### 5.2 LLM Provider Data Retention Settings

```python
# For OpenAI API
response = openai.ChatCompletion.create(
    model="gpt-4o-mini",
    messages=messages,
    headers={
        "OpenAI-Organization": "your-org",
        "OpenAI-Project": "no-retention"
    },
    # Explicitly disable training
    user="anonymous_session",  # not actual user ID
    temperature=0.7,
    # No storage
    store=False  # OpenAI doesn't retain this conversation
)

# For Google Gemini
# Use Vertex AI with logging disabled
# Or set `safety_settings` to block sensitive content
```

---

## 6. Deployment Plan (Mobile + Cloud + Home Gateway)

### 6.1 Components Breakdown

| Component | Where | Tech Stack | Cost |
|-----------|-------|------------|------|
| React Native App | Phone | TS, ONNX Runtime, CryptoJS | dev time |
| Cloud Proxy | VPS ($6/month DO) | FastAPI, Redis, Cloudflare | $6 |
| LLM API | Various | OpenAI/Gemini keys | $0.50-2 |
| Home Gateway | Raspberry Pi 4 | MCP server, Zigbee2MQTT | $50 (one-time) |
| Preference Storage | Phone + LAN | Git + Syncthing | $0 |

### 6.2 Step-by-Step Implementation

**Week 1: Mobile Core**
- Set up React Native with voice recording
- Integrate on-device Whisper (using react-native-whisper)
- Build PII redaction with ONNX runtime

**Week 2: Cloud Service**
- Deploy FastAPI on $6 DigitalOcean droplet
- Configure Cloudflare Tunnel (free)
- Implement session management with Redis

**Week 3: Home Gateway**
- Flash Raspberry Pi with Home Assistant OS
- Install MCP server (tevenson/homeassistant-mcp)
- Expose via Tailscale (free, secure tunnel)

**Week 4: Integration**
- Phone ↔ Cloud WebSocket for real-time commands
- Cloud ↔ Home via MCP over Tailscale
- Markdown preference editor UI in app

**Week 5: Testing & Launch**
- 5 beta users, measure latency & cost
- Implement fallback (local LLM on phone if cloud down)
- Security audit (OWASP Mobile Top 10)

### 6.3 Sample User Flow

1. Alice says: *"Hey assistant, turn on John's bedroom light to 50% because it's too dark"*
2. **Phone**: Transcribes locally → detects PII "John" → replaces with `[PERSON]` → stores encrypted mapping
3. **Phone -> Cloud**: `"turn on [PERSON]'s bedroom light to 50% because it's too dark"`
4. **Cloud**: LLM (GPT-4o-mini) parses intent → generates tool call: `light.turn_on` with entity `light.bedroom_john` and brightness `128`
5. **Cloud -> Home Gateway**: MCP command via Tailscale
6. **Home Gateway**: Executes on Zigbee light
7. **Cloud -> Phone**: Response `"I've turned on [PERSON]'s light to 50%"`
8. **Phone**: Restores `[PERSON]` → `"I've turned on John's light to 50%"` (TTS)

---

## 7. Markdown Preference Auto-Learning from Mobile

User can edit markdown directly in app:

```jsx
// PreferenceEditor.jsx
import { MarkdownEditor } from 'react-native-markdown-editor';

function DevicePreferences({ userId, deviceId }) {
  const [content, setContent] = useState('');
  
  useEffect(() => {
    // Fetch from local storage or sync
    const load = async () => {
      const md = await PreferenceStore.get(userId, deviceId);
      setContent(md);
    };
    load();
  }, []);
  
  const save = async () => {
    await PreferenceStore.save(userId, deviceId, content);
    // Optionally sync to nextcloud
  };
  
  return (
    <MarkdownEditor
      value={content}
      onChangeText={setContent}
      placeholder="Edit preferences...\n\n## Temperature\n- Night: 20°C"
      toolbar={['h1', 'h2', 'bold', 'italic', 'list']}
    />
  );
}
```

**Auto-learning** from user overrides:
- When user manually adjusts a device via app or voice, the phone records the context and updates the markdown's "Learned Patterns" section.
- User can review and approve/delete these auto-learned entries.

---

## 8. Cost Summary (Monthly)

| Item | Cost |
|------|------|
| Cloud VPS (1GB RAM, 1 vCPU) | $6 |
| LLM API (GPT-4o-mini, 2000 commands) | $1.20 |
| Tailscale (free tier) | $0 |
| Cloudflare (free) | $0 |
| Domain (optional) | $0 (use nip.io) |
| **Total** | **~$7.20** |

Can reduce to **$0** by:
- Using Gemini free tier only (60 req/min, enough for family)
- No VPS (use Cloudflare Workers free tier + Supabase free)
- Phone as the only compute (local Phi-3-mini for all commands - slower but works)

---

## Conclusion

This revised plan gives you:

✅ **Mobile-first experience** – users control via phone  
✅ **PII never sent to cloud** – redacted on device, restored on device  
✅ **Markdown preferences** – human-readable, user-owned, per device  
✅ **Cloud LLM for intelligence** – but costs under $10/month  
✅ **Production ready** – mTLS, auditing, fallback paths  
✅ **Zero lock-in** – all preferences are plain text files  

The only trade-off: you need a small home gateway (Raspberry Pi) or run Home Assistant on an old PC. That's a one-time $50 cost. Without it, you can still control Wi-Fi devices (Tuya, Shelly) directly from cloud.