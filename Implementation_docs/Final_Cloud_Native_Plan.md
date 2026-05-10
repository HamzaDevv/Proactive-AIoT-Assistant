# Final Implementation Blueprint: Cloud-Native, Mobile-First Home Assistant
### *Context-Aware · Zero-Cost · Privacy-Preserving (PII Tokenization) · Spatial Tree RAG*

---

## 1. Executive Summary & Core Architectural Constraints

This blueprint defines a **production-scale, not-a-toy** smart home AI assistant. It abandons local-heavy compute in favor of a **Cloud-Native, Mobile-First** architecture that operates entirely within **"Always Free"** tiers, ensuring **Zero Ongoing Cost**. 

### 1.1 The "Always Free" Cloud Stack
| Layer | Technology / Service | Tier | Role |
| :--- | :--- | :--- | :--- |
| **Edge Logic** | Mobile Phone (iOS/Android) | N/A | Regex-based PII scrubbing, Tokenization, ASR (Voice Capture), TTS (Playback). |
| **Logic Layer** | Render (FastAPI) | Free Tier | Central "Linker" logic and Multi-Agent LangGraph Orchestrator. |
| **Storage Layer** | MongoDB Atlas | M0 (Free Tier) | Stores Spatial Tree (Materialized Paths) and Markdown preferences. |
| **Reasoning** | Gemini 2.5 Flash API | Free Tier | Primary reasoning engine (fast, multimodal, generous free tier). |
| **Actuation** | Home Assistant (Matter 1.5) | Local Hub | Executes commands securely via local network. |
| **Secure Tunnel** | Cloudflare Tunnel / Tailscale | Free Tier | Secure bridge between Render server and local Home Assistant. |

---

## 2. Privacy & Governance (PII Management)

A cloud-native approach demands strict privacy controls. We employ a **Mobile-First PII Boundary** where raw personal data never leaves the user's phone.

### 2.1 Lightweight Edge Scrubbing & Tokenization
Heavy SLMs (Small Language Models) drain mobile battery and compute. Instead, the phone utilizes a **Regex + Local Registry Hybrid**.
- **Local Entity Registry:** The phone maintains a secure, local map of real identities to tokens (e.g., `{"Ameer": "{{USER_1}}", "Master Bedroom": "{{ROOM_A}}"}`).
- **Scrubbing Pipeline:** Voice input is transcribed via on-device ASR. The local registry and regex patterns swap real names, addresses, and sensitive data for tokens.
- **Payload:** The payload sent to Render looks like: `"{{USER_1}} is in {{ROOM_A}}, turn on the lamp for reading."`

### 2.2 Cloud Anonymity
Render, MongoDB, and Gemini **only ever see masked tokens and pseudonymized preferences**. When Render sends the LLM's response back to the phone, the phone's local registry "re-hydrates" the tokens back into real names for TTS playback.

---

## 3. Data & Preference Management

### 3.1 Markdown-Based Preferences
Device settings and user preferences are stored as **Markdown (`.md`) files**. 
- **Why Markdown?** It is human-readable, easily version-controlled, and seamlessly injected into the LLM context prompt. Users manage and edit these preferences directly via their Mobile app.

### 3.2 The Spatial Tree (MongoDB Materialized Paths)
Preferences are not stored flat. They are stored in MongoDB Atlas using a **Hierarchical Spatial Tree** that mimics the physical layout of the home (Floor > Room > Zone).
- **Structure:** `floor_1,living_room,relaxation_zone`
- **Neighbor Context Fetching:** When the agent retrieves preferences for a target device (e.g., a reading lamp), MongoDB queries using materialized paths to fetch the preferences of **neighboring devices** in the same zone (e.g., window blinds, room thermostat).
- **Benefit:** The LLM receives holistic spatial context in a single database query, enabling intelligent, cross-device decision making.

---

## 4. Connectivity & Interaction

### 4.1 Industry Standards
- **Matter 1.5:** Ensures vendor-neutral device interoperability and local execution.
- **Model Context Protocol (MCP):** Standardizes tool calling, allowing Home Assistant devices to be exposed as uniform resources and tools to the LangGraph agents.

### 4.2 Agentic Intuition
The AI is not a simple command parser. By feeding the Gemini 2.5 Flash model the **Spatial Tree neighbor context** and **Markdown preferences**, the AI gains "Agentic Intuition." 
- *Example:* If user `{{USER_1}}` turns on the lamp for "reading" in `{{ROOM_A}}`, the AI sees the neighbor context for the blinds and proactively suggests (or automates) closing the blinds to reduce glare.

### 4.3 Voice Pipeline Breakdown
1. **Phone (Edge):** Wake-word → ASR (Speech-to-Text) → Tokenization (PII Scrubbing).
2. **Cloud (Render):** Receives tokens → Fetches Spatial Tree + Markdown Prefs from MongoDB → Passes context to Gemini 2.5 Flash.
3. **Cloud (Render):** Receives LLM decision → Sends command via Secure Tunnel to Home Assistant.
4. **Phone (Edge):** Receives tokenized response → Re-hydrates PII → TTS (Text-to-Speech) playback.

---

## 5. Reasoning & Execution

### 5.1 Multi-Agent Orchestration (LangGraph)
Render hosts a **FastAPI** service running a **stateful, context-aware LangGraph**. 
- The LangGraph orchestrator decomposes complex intents, checks the Markdown preference contexts, and routes tasks to specific sub-agents (e.g., Comfort Agent, Security Agent).

### 5.2 The "Linker" Logic
The core intelligence of the system is the "Linker." The Linker bridges three domains:
1. **User Intent** (Tokenized NLP from the phone).
2. **Spatial Context** (MongoDB neighbor preferences).
3. **Execution** (Matter 1.5 / MCP tool definitions).

### 5.3 Secure Tunneling (Actuation)
To allow the cloud-based Render server to control local smart home devices without exposing the home network to the public internet:
- A **Cloudflare Tunnel (cloudflared)** or **Tailscale Subnet Router** runs locally alongside Home Assistant.
- Render communicates with Home Assistant strictly over this encrypted tunnel, invoking MCP tool calls which Home Assistant translates into Matter 1.5 commands.

---

## 6. Architecture Diagram

```text
┌────────────────────────────────────────────────────────────┐
│                    MOBILE EDGE (iOS/Android)               │
│  1. Voice ASR (Whisper)                                    │
│  2. Regex + Local Registry (Tokenization: Ameer → {{U1}})  │
│  3. TTS (Re-hydration & Playback)                          │
└─────────────────────────────┬──────────────────────────────┘
                              │ Tokenized Payload
┌─────────────────────────────▼──────────────────────────────┐
│                    CLOUD LOGIC (Render FastAPI)            │
│  1. The "Linker" Logic (Bridging intent & context)         │
│  2. LangGraph Multi-Agent Orchestrator                     │
│  3. MCP Client                                             │
└──────┬──────────────────────────────────────────────┬──────┘
       │ Reads/Writes                                 │ Prompts + Tools
┌──────▼──────────────────────┐               ┌───────▼──────────────────────┐
│ STORAGE (MongoDB Atlas M0)  │               │ REASONING (Gemini 2.5 API)   │
│ 1. Spatial Tree Context     │               │ 1. Primary Reasoning Engine  │
│ 2. Markdown Preferences     │               │ 2. Tool Calling (MCP)        │
│ 3. Masked PII mappings      │               │ 3. Multimodal Analysis       │
└─────────────────────────────┘               └──────────────────────────────┘
                              │ Secure Tunnel (Tailscale/Cloudflare)
┌─────────────────────────────▼──────────────────────────────┐
│                    LOCAL HOME (Actuation)                  │
│  1. Secure Bridge / Tunnel Endpoint                        │
│  2. Home Assistant (MCP Server)                            │
│  3. Matter 1.5 Controller → End Devices                    │
└────────────────────────────────────────────────────────────┘
```
