# Production Smart Home AI Assistant — Full Implementation Plan
### *Context-Aware · Voice-First · Privacy-by-Design · Zero Ongoing Cost*

---

> **Scope:** This document is a production-grade technical blueprint. Every technology choice is justified against reliability, maintainability, zero-cost operation, and regulatory compliance (GDPR / India DPDP Act 2023). Toy-project shortcuts are explicitly called out and replaced with production alternatives throughout.
>
> **v2 Changes:** (1) Per-user, per-device preference system using Markdown files as the preference store. (2) Mobile phone as the primary edge device — heavy processing moves to cloud, with a revised PII architecture that handles the mobile-first deployment model.

---

## Table of Contents

1. [Architecture Philosophy](#1-architecture-philosophy)
2. [Full System Architecture](#2-full-system-architecture)
3. [Technology Stack (Definitive)](#3-technology-stack-definitive)
4. [LLM Strategy — Proprietary + Tunable Hybrid](#4-llm-strategy)
5. [PII & Privacy Governance Architecture — Mobile-First](#5-pii--privacy-governance-architecture--mobile-first)
6. [Voice Interface Pipeline](#6-voice-interface-pipeline)
7. [Device Integration Layer (Matter / HA / MCP)](#7-device-integration-layer)
8. [Per-User Per-Device Preference System (Markdown)](#8-per-user-per-device-preference-system-markdown)
9. [LLM Fine-Tuning & Alignment Plan](#9-llm-fine-tuning--alignment-plan)
10. [Security & Zero-Trust Governance](#10-security--zero-trust-governance)
11. [Phased Deployment Plan](#11-phased-deployment-plan)
12. [Zero-Cost Budget Breakdown](#12-zero-cost-budget-breakdown)
13. [Production Readiness Checklist](#13-production-readiness-checklist)

---

## 1. Architecture Philosophy

### Core Design Principles

| Principle | Decision | Rationale |
|---|---|---|
| **Mobile-First Edge** | Phone handles VAD, wake word, lightweight ASR, and on-device PII scrubbing | Phone is always with user; Pi 5 hub is the home server, cloud handles heavy reasoning |
| **PII Scrubbed on Device** | All PII is tokenised on the phone *before* any data leaves it | Phone is the new "trust boundary" in mobile-first deployment |
| **Markdown Preference Files** | Per-user, per-device `.md` preference files as the preference store | Human-readable, git-versionable, directly injectable into LLM context |
| **Free-Tier Proprietary** | Gemini 2.0 Flash (free tier) as primary orchestrator | 1M tokens/day free, multimodal, best-in-class reasoning |
| **Tunable Local LLMs** | Quantised Llama-3.2-3B on hub for sensitive fallback tasks | Sensitive tasks stay inside the home network |
| **Standards-First** | Matter 1.3 + Home Assistant + MCP | Future-proof; not vendor-locked |
| **Reliability > Features** | Self-correction loops, circuit breakers, safe-mode | Production uptime target: 99.5% |

### The Four Hard Rules for Production (Updated for Mobile-First)

1. **No PII touches any cloud API — ever.** PII is detected and tokenised on the phone itself, the cloud model reasons over tokens, the local hub re-hydrates the response before TTS playback.
2. **The phone is the PII perimeter.** In mobile-first mode, the phone replaces the Pi 5 as the PII firewall. The hub still enforces its own PII check as a second layer — defence in depth.
3. **Every actuator action has a safety gate.** No AI decision can unlock a door, disable an alarm, or run a high-wattage device without passing a hard-coded rule engine first.
4. **The system degrades gracefully.** Cloud LLM unreachable → hub Llama-3.2-3B takes over. Hub unreachable → phone handles simple cached commands. Full offline → manual device control via HA app.

---

## 2. Full System Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│              LAYER 0 — USER INTERFACE (Mobile-First)                 │
│  iOS / Android App  │  Voice (mic on phone)  │  Web Dashboard        │
│  Wearable (BT to phone)                                              │
└─────────────────┬────────────────────────────────────────────────────┘
                  │ Raw audio (stays on phone)
┌─────────────────▼────────────────────────────────────────────────────┐
│           LAYER 1 — SENSE + PII FIREWALL (On-Phone — MANDATORY)      │
│                                                                      │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │  VAD (WebRTC) → Wake Word (openWakeWord ONNX) → Whisper tiny  │  │
│  │              (on-device ASR, CoreML / NNAPI)                  │  │
│  └────────────────────────┬──────────────────────────────────────┘  │
│                           │ Raw transcription text                   │
│  ┌────────────────────────▼──────────────────────────────────────┐  │
│  │            MOBILE PII FIREWALL (On-Phone)                     │  │
│  │  Presidio-lite (Python → compiled ONNX NER model)             │  │
│  │  + Fine-tuned Llama-1B ONNX (smart home PII classifier)       │  │
│  │  Token Vault (AES-256-GCM, iOS Secure Enclave / Android HSM)  │  │
│  └────────────────────────┬──────────────────────────────────────┘  │
│                           │ Sanitised text + sensor context          │
└─────────────────┬─────────┴────────────────────────────────────────-┘
                  │ Encrypted payload (TLS 1.3) — NO raw PII
      ┌───────────┴─────────────┐
      │                         │
      ▼                         ▼
[Home Hub — Pi 5]        [Cloud — Gemini API]
(on LAN, if reachable)   (if hub is unreachable
                          or heavy reasoning needed)
┌─────────────────────────────────────────────────────────────────────┐
│               LAYER 2 — HUB PII GUARD (Second Layer, On-Hub)        │
│  Presidio NER re-check (catches anything that slipped through phone) │
│  Token Vault sync (phone tokens recognised at hub level)            │
└─────────────────┬───────────────────────────────────────────────────┘
                  │ Double-sanitised context
┌─────────────────▼───────────────────────────────────────────────────┐
│            LAYER 3 — THINK (Hybrid Cloud + Local)                   │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │          ORCHESTRATOR AGENT (LangGraph StateMachine)        │    │
│  │   Gemini 2.0 Flash (cloud, free tier) — primary reasoning   │    │
│  │   Llama-3.2-3B (hub local, GGUF Q4) — fallback & sensitive  │    │
│  └──────┬────────────────────┬────────────────────────┬────────┘    │
│         │                    │                         │            │
│  ┌──────▼──────┐  ┌─────────▼──────┐  ┌─────────────▼──────┐        │
│  │ Comfort &   │  │  Security &    │  │   Kitchen &         │       │
│  │ Ambiance    │  │  Safety Agent  │  │   Culinary Agent    │       │
│  │ Agent (CAA) │  │  (SSA)         │  │   (KCA)             │       │
│  └──────┬──────┘  └─────────┬──────┘  └─────────────┬──────┘        │
│         │                    │                         │            │
│  ┌──────▼──────┐  ┌─────────▼──────┐                             │
│  │ Entertain.  │  │  Resource Mgmt  │  Preference Loader          │
│  │ Agent (EWA) │  │  Agent (RMA)    │  (Markdown files per user   │
│  └─────────────┘  └────────────────┘   per device — see §8)      │
│                                         ChromaDB (vector memory)   │
│                                         SQLite (audit + state)     │
└─────────────────┬───────────────────────────────────────────────────┘
                  │ Validated action plan
┌─────────────────▼───────────────────────────────────────────────────┐
│              LAYER 4 — SAFETY GATE (On-Hub — MANDATORY)             │
│  Rule Engine (hard-coded constraints) │ Action Validator             │
│  Human-in-Loop trigger (for sensitive ops) │ Audit Logger            │
└─────────────────┬───────────────────────────────────────────────────┘
                  │ Safe, authorised commands
┌─────────────────▼───────────────────────────────────────────────────┐
│              LAYER 5 — ACT (Home Assistant + MCP)                   │
│  MCP Server per device class │ Matter 1.3 Controller                │
│  Zigbee2MQTT │ Z-Wave JS │ SmartThings REST API                    │
│  Response → encrypted back to phone → Piper TTS (on phone)         │
└─────────────────────────────────────────────────────────────────────┘
```

### Data Flow — Mobile-First Utterance (Updated)

```
User speaks into phone: "I'm feeling cold, check if the front door is locked"

PHONE (on-device):
1. VAD detects speech → openWakeWord (ONNX) confirms wake phrase
2. Whisper-tiny (CoreML/NNAPI) transcribes audio → raw text
3. Mobile PII Firewall scans:
   - No PERSON/LOCATION entities found in this utterance → pass-through
   - Context payload assembled with pseudonymised user_token
4. Encrypted payload dispatched to Hub (or directly to Gemini if hub offline):
   { user_token: "u_a7f3", location_tag: "LOC_HOME", activity: "resting",
     temp_reading: 19.2, time: "21:45",
     text: "I'm feeling cold, check if the front door is locked" }

HUB (on-LAN) or CLOUD (fallback):
5. Hub PII Guard re-checks → clean, passes
6. Preference Loader reads Markdown files:
   - prefs/u_a7f3/hvac_living_room.md  → preferred_temp_resting: 23°C
   - prefs/u_a7f3/front_door_lock.md   → no special prefs; default: report status
7. LangGraph Orchestrator decomposes → 2 subtasks:
   - CAA: set temp to 23°C (from preference file)
   - SSA: query door lock status (read-only)
8. Safety Gate: temp change ✓ (within 16–28°C), lock query ✓
9. HA executes commands → door is locked, HVAC updated
10. Response built: "I've set heating to 23°C. Front door is locked."
11. Response encrypted → sent back to phone

PHONE:
12. PII Rehydrator: no tokens to replace (this utterance had none)
13. Piper TTS (on-phone) plays response
```

---

## 3. Technology Stack (Definitive)

### 3.1 Hardware

| Component | Recommended | Why | Cost |
|---|---|---|---|
| **Edge Device** | User's existing Android / iPhone | Always with user; handles ASR + PII scrubbing | $0 (already owned) |
| **Home Hub** | Raspberry Pi 5 (8GB) | Runs Llama-3.2-3B Q4, HA, ChromaDB, all local services | ~₹8,000 one-time |
| **Better Hub** | Mini PC (N100 / Ryzen 5) | 2–4× faster inference for >3 occupants | ~₹12,000–18,000 |
| **Audio I/O** | Phone microphone (primary) + optional ReSpeaker array (hub-side) | Phone mic sufficient for mobile-first | $0 / ~₹2,500 optional |
| **Network** | Dedicated VLAN on router | IoT isolation — non-negotiable | $0 (config only) |

### 3.2 Software Stack

```
LAYER           TECHNOLOGY                    PLATFORM    COST
──────────────────────────────────────────────────────────────
MOBILE (On-Phone)
Wake Word       openWakeWord (ONNX export)    iOS/Android $0
ASR             Whisper.cpp (CoreML/NNAPI)    iOS/Android $0
PII Detection   Presidio NER → ONNX           iOS/Android $0
PII Model       Llama-1B fine-tune → ONNX     iOS/Android $0
Token Vault     iOS Secure Enclave / Android  OS-level    $0
                Keystore + AES-256-GCM
TTS             Piper TTS (ONNX, on-phone)    iOS/Android $0
Mobile App      Flutter (single codebase)     iOS/Android $0
──────────────────────────────────────────────────────────────
HUB (Raspberry Pi 5 / Mini PC)
HA Core         Home Assistant OS             Linux       $0
Device Bridge   Zigbee2MQTT / Z-Wave JS /     Linux       $0
                Matter Server
PII Guard       Presidio (second layer)       Python      $0
MCP             FastMCP (Python SDK)          Python      $0
Orchestration   LangGraph                     Python      $0
Agent Memory    LangChain                     Python      $0
Vector DB       ChromaDB (AES-256)            Python      $0
Pref Store      Markdown files (git-tracked)  Filesystem  $0
Relational      SQLite + SQLCipher            Embedded    $0
──────────────────────────────────────────────────────────────
CLOUD
Primary LLM     Gemini 2.0 Flash (free tier)  Google      $0
                1M tokens/day, 1500 req/day
──────────────────────────────────────────────────────────────
LLMs (Hub)
Fallback LLM    Llama-3.2-3B Q4_K_M (GGUF)   llama.cpp   $0
PII Model       Llama-3.2-1B fine-tune (GGUF) llama.cpp   $0
──────────────────────────────────────────────────────────────
INFRA
Secret Mgmt     Infisical (self-hosted AGPL)  Docker      $0
TLS             Caddy (auto-cert)             Docker      $0
Auth            Authelia (OIDC/SSO)           Docker      $0
Monitoring      Prometheus + Grafana + Loki   Docker      $0
CI/CD           Gitea + Woodpecker CI         Docker      $0
```

---

## 4. LLM Strategy

### 4.1 The Hybrid Model Architecture (Mobile-First Updated)

```
┌──────────────────────────────────────────────────────────────┐
│                    LLM DECISION ROUTER                       │
│                                                              │
│  Sanitised input arrives at Hub from Phone                  │
│                                                              │
│  IF (hub_unreachable) AND (simple_cached_intent)            │
│      → On-phone cached command executor (no LLM)            │
│  IF (contains_residual_PII) OR (sensitive_action)           │
│      → Hub Llama-3.2-3B (GGUF Q4_K_M) — never leaves LAN   │
│  ELIF (complex reasoning) OR (multimodal)                   │
│      → Gemini 2.0 Flash (sanitised context only)            │
│  ELIF (PII classification — phone layer)                    │
│      → Fine-tuned Llama-1B ONNX (on phone)                  │
│  ELIF (simple intent, preference file hit)                  │
│      → Preference file lookup → zero LLM calls              │
└──────────────────────────────────────────────────────────────┘
```

### 4.2 Primary Model — Gemini 2.0 Flash (Free Tier)

**Free Tier Capacity Analysis for a 3-person household (mobile-first):**
```
Average utterances/day:           ~150
Average tokens per exchange:       ~800 input + 300 output = 1,100
Daily token usage:                 150 × 1,100 = 165,000 tokens
Free tier limit:                   1,000,000 tokens/day
Headroom:                          83.5% — very comfortable
Estimated cost:                    $0
```

```python
# core/llm/gemini_client.py
import google.generativeai as genai
from tenacity import retry, stop_after_attempt, wait_exponential

class GeminiOrchestrator:
    def __init__(self, api_key: str, preference_loader):
        genai.configure(api_key=api_key)
        self.preference_loader = preference_loader   # NEW: injects Markdown prefs
        self.model = genai.GenerativeModel(
            model_name="gemini-2.0-flash",
            system_instruction=SYSTEM_PROMPT,
            tools=MCP_TOOL_DEFINITIONS,
            generation_config=genai.GenerationConfig(
                temperature=0.1,
                max_output_tokens=2048,
            )
        )
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=3,
            recovery_timeout=30,
            fallback=self.local_llm_fallback
        )

    async def reason(self, sanitised_context: dict) -> AgentPlan:
        # Load relevant preference files for this user + devices in context
        pref_context = await self.preference_loader.build_pref_context(
            user_token=sanitised_context["user_token"],
            devices_mentioned=sanitised_context.get("devices", [])
        )
        # Preference Markdown content is appended to the prompt — not stored in cloud
        enriched_context = {**sanitised_context, "user_preferences": pref_context}

        if self.circuit_breaker.is_open():
            return await self.local_llm_fallback(enriched_context)

        response = await self.model.generate_content_async(
            self._build_prompt(enriched_context),
            request_options={"timeout": 8}
        )
        self.circuit_breaker.record_success()
        return self._parse_agent_plan(response)
```

### 4.3 Fallback — Llama-3.2-3B (Hub, Local)

```
Model:          Llama-3.2-3B-Instruct Q4_K_M (GGUF)
File size:      ~2.0 GB
RAM usage:      ~2.5 GB
TTFT:           ~1.2 seconds on Pi 5
Throughput:     ~10 tokens/sec
Full latency:   ~4–6 seconds — acceptable for voice assistant
```

### 4.4 On-Phone PII Model — Fine-tuned Llama-1B → ONNX

In mobile-first mode the PII model must run on the phone, not the hub. This requires exporting the fine-tuned Llama-3.2-1B to ONNX format for CoreML (iOS) and NNAPI (Android) acceleration.

```python
# training/export_pii_model_to_onnx.py
# Run after fine-tuning on Colab T4

from optimum.exporters.onnx import main_export
from peft import PeftModel

# 1. Merge LoRA weights into base model
base = AutoModelForTokenClassification.from_pretrained("meta-llama/Llama-3.2-1B")
merged = PeftModel.from_pretrained(base, "./pii-llama-1b-lora").merge_and_unload()
merged.save_pretrained("./pii-llama-1b-merged")

# 2. Export to ONNX
main_export(
    model_name_or_path="./pii-llama-1b-merged",
    output="./pii-llama-1b-onnx",
    task="token-classification",
    opset=17,
    optimize="O3",         # Aggressive optimisation for mobile inference
)

# 3. Convert to CoreML (iOS)
# coremltools converts the ONNX model for iOS Neural Engine
import coremltools as ct
mlmodel = ct.convert("./pii-llama-1b-onnx/model.onnx",
                     compute_units=ct.ComputeUnit.ALL)
mlmodel.save("PIIClassifier.mlpackage")

# Android: Use ONNX Runtime Mobile with NNAPI provider — no extra conversion needed
```

**On-phone PII model performance targets:**
```
iOS (iPhone 14+):    <80ms inference (Neural Engine)
Android (SD 8 Gen2): <120ms inference (NNAPI)
Model size on disk:  ~320MB (Q4 quantised ONNX)
RAM at runtime:      ~250MB (acceptable alongside app)
```

---

## 5. PII & Privacy Governance Architecture — Mobile-First

### 5.1 The Two-Layer PII Architecture

In mobile-first deployment, PII scrubbing happens at **two independent layers** — defence in depth:

```
Layer 1 — Phone (Primary):   Presidio ONNX + Llama-1B ONNX
                              Token Vault in iOS Secure Enclave / Android HSM
                              ↓ (sanitised payload only leaves phone)
Layer 2 — Hub (Secondary):   Presidio Python (full) re-checks incoming payload
                              Rejects and flags if any PII slips through Layer 1
                              ↓ (clean context reaches orchestrator)
Layer 3 — Cloud:             Gemini sees ONLY sanitised tokens — never raw PII
```

**Why two layers?**
- Mobile ONNX models are optimised for speed, not maximum recall — they may miss edge cases
- Hub-side Presidio runs the full English + multilingual pipeline with no resource constraint
- If Layer 1 misses something, Layer 2 catches it before it reaches Gemini
- Dual-layer gives defence even if the phone model is compromised or outdated

### 5.2 Mobile PII Firewall Implementation

```python
# mobile/lib/pii_firewall.dart  (Flutter implementation concept)
# The actual inference runs via platform channels to native ONNX Runtime

class MobilePIIFirewall {
  final ONNXInferenceEngine _presidioOnnx;   // Compiled Presidio NER → ONNX
  final ONNXInferenceEngine _llamaPII;        // Fine-tuned Llama-1B → ONNX
  final SecureTokenVault _vault;              // iOS Secure Enclave / Android HSM

  Future<SanitisedPayload> sanitise(
      String rawText, String userToken) async {
    // Stage 1: Fast Presidio ONNX pass (catches obvious PII, ~20ms)
    final presidioEntities = await _presidioOnnx.runNER(rawText);

    // Stage 2: Llama-1B ONNX (catches contextual / smart-home PII, ~80ms)
    final llamaEntities = await _llamaPII.runNER(rawText);

    // Merge detections, sort by position (right-to-left for safe replacement)
    final allEntities = _mergeAndDeduplicate(presidioEntities, llamaEntities);

    String sanitisedText = rawText;
    final tokenMap = <String, PIIEntity>{};

    for (final entity in allEntities.reversed) {
      // Store original in hardware-backed vault
      final token = await _vault.store(
        original: rawText.substring(entity.start, entity.end),
        entityType: entity.label,
        userToken: userToken,
        ttlSeconds: 3600,        // Tokens auto-expire after 1 hour
      );
      // Replace with reversible placeholder
      sanitisedText = sanitisedText.replaceRange(
        entity.start, entity.end, '[${entity.label}_$token]'
      );
      tokenMap[token] = entity;
    }

    return SanitisedPayload(
      safeText: sanitisedText,
      tokenMap: tokenMap,
      userToken: userToken,
      // Never include raw text or original PII in the payload
    );
  }

  String rehydrate(String llmResponse, Map<String, PIIEntity> tokenMap) {
    // Called on phone after response returns from hub/cloud
    // Replaces [TYPE_TOKEN] placeholders with originals for TTS playback
    String result = llmResponse;
    for (final entry in tokenMap.entries) {
      final original = _vault.retrieve(entry.key);
      if (original != null) {
        result = result.replaceAll('[${entry.value.label}_${entry.key}]', original);
      }
    }
    return result;
  }
}
```

### 5.3 Hub-Side PII Guard (Second Layer)

```python
# core/privacy/hub_pii_guard.py
class HubPIIGuard:
    """
    Second-layer PII guard running on the hub.
    Receives already-sanitised payloads from phone.
    Catches anything the mobile layer missed.
    """
    def __init__(self):
        self.analyzer = AnalyzerEngine()   # Full Presidio, no resource constraint
        self.alert = SecurityAlertSystem()

    def inspect(self, payload: dict) -> InspectionResult:
        text_fields = [payload.get("text", ""), payload.get("context", "")]
        for field in text_fields:
            results = self.analyzer.analyze(text=field, language="en")
            if results:
                # PII slipped through phone layer — flag and sanitise
                self.alert.raise_alert(
                    level="WARNING",
                    message=f"PII bypass detected: {[r.entity_type for r in results]}",
                    payload_hash=sha256(field.encode()).hexdigest()
                )
                # Sanitise before passing downstream — never reject entirely
                # (rejection would break UX; sanitise + alert is the right trade-off)
                payload = self._sanitise_residual(payload, results)
        return InspectionResult(clean_payload=payload)
```

### 5.4 Token Vault — Phone vs. Hub Synchronisation

Because the phone tokenises PII but the hub may need to rehydrate for TTS (if TTS is moved hub-side), the token vault uses a **one-way encrypted sync**:

```
Phone Token Vault (source of truth)
  ↓ Push encrypted token metadata to hub at session start
Hub Token Store (read-only replica, session-scoped)
  ↓ Discarded at session end
Cloud (Gemini)
  → Never receives token metadata — only the [TYPE_TOKEN] placeholders
```

```python
# core/privacy/token_sync.py
class TokenVaultSync:
    def push_session_tokens(
        self, token_map: dict, hub_session_key: bytes
    ) -> bytes:
        """
        Phone calls this to push token metadata to hub at session start.
        Encrypted with a session-ephemeral key (ECDH key exchange).
        Hub can rehydrate for TTS but cannot persist tokens beyond session.
        """
        payload = json.dumps(token_map).encode()
        encrypted = AES_GCM.encrypt(key=hub_session_key, plaintext=payload)
        return encrypted   # Sent over mTLS to hub

    def receive_session_tokens(
        self, encrypted_payload: bytes, session_key: bytes
    ) -> dict:
        """Hub side — decrypt and hold in RAM only (never write to disk)."""
        return json.loads(AES_GCM.decrypt(key=session_key, ciphertext=encrypted_payload))
```

### 5.5 Data Governance Policy

| Data Category | Storage Location | Encryption | Retention | Legal Basis |
|---|---|---|---|---|
| Voice audio | Phone RAM only | N/A (never written) | Session only | Consent |
| Transcriptions | Hub SQLite | AES-256 (SQLCipher) | 30 days | Legitimate interest |
| PII tokens | Phone Secure Enclave / HSM | Hardware-backed | 1 hour TTL | Consent |
| Token metadata sync | Hub RAM only | AES-256-GCM session key | Session only | Consent |
| Activity patterns | Hub SQLite | AES-256 | 90 days | Contract |
| Preferences (Markdown) | Hub filesystem | AES-256 at rest | Indefinite | Consent |
| Device commands | Hub SQLite (audit) | AES-256 | 1 year | Legal obligation |
| Cloud LLM input | Sanitised tokens only | TLS 1.3 in transit | Never stored | N/A — no PII sent |

### 5.6 User Rights Implementation (GDPR / DPDP Act 2023)

```python
# core/privacy/data_rights.py
class UserDataRightsManager:
    async def right_to_access(self, user_token: str) -> dict:
        return {
            "transcriptions": self.db.get_transcriptions(user_token),
            "preferences": self.preference_loader.export_all(user_token),
            "activity_log": self.db.get_activities(user_token),
            "device_history": self.db.get_commands(user_token),
        }

    async def right_to_erasure(self, user_token: str) -> bool:
        self.db.delete_user(user_token)
        self.preference_loader.delete_user_prefs(user_token)
        self.token_vault.purge_user(user_token)
        self.audit_log.record_erasure(user_token)
        return True
```

---

## 6. Voice Interface Pipeline

### 6.1 Full Mobile-First Pipeline

```
Phone Mic → VAD (WebRTC) → Wake Word (ONNX) → Whisper-tiny (CoreML/NNAPI)
                                                        ↓
                                            Mobile PII Firewall
                                                        ↓
                                          Encrypted payload (TLS 1.3)
                                                        ↓
                                     Hub (or Gemini direct if hub offline)
                                                        ↓
                                         Orchestrator → MCP → HA
                                                        ↓
                                       Response (sanitised) back to phone
                                                        ↓
                                    PII Rehydrator (on phone) → Piper TTS
```

### 6.2 ASR on Mobile

```swift
// iOS — WhisperKit integration (CoreML acceleration)
import WhisperKit

let whisper = try await WhisperKit(model: "openai/whisper-tiny.en")
let result = try await whisper.transcribe(audioPath: recordingURL.path)
let rawText = result.text   // → immediately fed to MobilePIIFirewall
```

```kotlin
// Android — whisper.cpp via JNI + NNAPI
val whisper = WhisperContext.createContextFromAsset(assets, "whisper-tiny.en.bin")
val text = whisper.transcribeData(audioFloats)  // → immediately fed to MobilePIIFirewall
```

**Mobile ASR performance:**
```
Device              Model         Latency    WER
iPhone 14 Pro       tiny.en       ~80ms      ~8%
Pixel 8             tiny.en       ~120ms     ~8%
Mid-range Android   tiny.en       ~300ms     ~8%
All devices         base (multi)  ~400ms     ~5%   (for Hindi/regional)
```

### 6.3 Wake Word (On-Phone, ONNX)

```python
# Exported to ONNX for mobile — same training pipeline as hub model
# Custom wake word training: 500 positive samples + Google Speech Commands negatives
# Training: ~30 minutes on Colab T4 → export ONNX → ship in app bundle
```

### 6.4 TTS — Piper (On-Phone)

Piper ONNX runs on-device so the voice response is synthesised on the phone after PII rehydration — the cloud/hub never speaks raw PII aloud.

```python
# Piper ONNX for mobile: en_US-lessac-medium (~50MB ONNX model)
# iOS: CoreML-converted Piper model
# Android: ONNX Runtime Mobile
# Synthesis latency on phone: ~150ms for typical smart home response
# This means TTS output never leaves the phone — privacy preserved
```

---

## 7. Device Integration Layer

### 7.1 Home Assistant as the Universal Hub

The strategy is unchanged: **HA owns all device communication, the AI layer talks to HA through typed MCP servers.**

```
AI Agent → MCP Tool Call → MCP Server → HA REST API → Device
```

### 7.2 Matter 1.3 Integration

Matter devices work fully locally (Thread mesh) — they do not require internet connectivity. This is critical when the cloud LLM is the primary reasoner: the actuator layer stays offline-capable even when reasoning is in the cloud.

### 7.3 MCP Server Architecture

```python
# mcp_servers/comfort_server.py
@mcp.tool()
async def set_temperature(zone: str, temperature: float, mode: str = "auto") -> dict:
    if not (16.0 <= temperature <= 30.0):
        raise ValueError(f"Temperature {temperature}°C outside safe range")
    return await ha.call_service("climate", "set_temperature",
                                  entity_id=f"climate.{zone}_hvac",
                                  temperature=temperature, hvac_mode=mode)

# Security server — unlock is NOT exposed as MCP tool
@mcp.tool()
async def get_lock_status(device_id: str) -> dict:
    return await ha.get_state(f"lock.{device_id}")

@mcp.tool()
async def lock_door(device_id: str, reason: str) -> dict:
    audit_log.write(action="lock", device=device_id, reason=reason)
    return await ha.call_service("lock", "lock", entity_id=f"lock.{device_id}")
# UNLOCK IS NOT AN MCP TOOL — requires human action in the app
```

---

## 8. Per-User Per-Device Preference System (Markdown)

This is the preference layer. Every combination of **user × device class** gets its own Markdown file. These files are the single source of truth for personalisation — they replace a NoSQL preference store with something human-readable, git-versionable, and directly injectable into an LLM context window.

### 8.1 Design Rationale

| Property | Why Markdown? |
|---|---|
| **Human-readable** | Any household member can open and edit their own file |
| **LLM-injectable** | Markdown text can be appended directly to the Gemini / Llama prompt with zero transformation |
| **Git-versionable** | Gitea on the hub tracks every preference change; full rollback history |
| **Structured enough** | YAML front-matter provides machine-parseable fields; body provides rich natural-language context for the LLM |
| **Zero DB dependency** | No schema migrations, no ORM, no cloud sync required |
| **Diff-friendly** | Changes are auditable line-by-line |

### 8.2 File System Layout

```
/hub/preferences/
├── {user_token}/                       # One directory per user (pseudonymised ID)
│   ├── _profile.md                    # User-level global preferences
│   ├── hvac_living_room.md            # HVAC in living room
│   ├── hvac_bedroom_main.md           # HVAC in master bedroom
│   ├── hvac_bedroom_guest.md
│   ├── lighting_living_room.md
│   ├── lighting_bedroom_main.md
│   ├── lighting_kitchen.md
│   ├── front_door_lock.md
│   ├── main_gate_lock.md
│   ├── tv_living_room.md
│   ├── music_system_living_room.md
│   ├── kitchen_oven.md
│   ├── kitchen_appliances.md
│   └── ev_charger.md
│
├── u_a7f3/                             # Example: User A (token pseudonym)
├── u_b912/                             # Example: User B
└── shared/                            # Household-level shared prefs
    ├── guest_mode.md
    └── energy_policy.md
```

> **Privacy note:** Directory names use the same pseudonymised `user_token` as the rest of the system. The mapping from real identity to token exists only in the phone's Secure Enclave / Android HSM — never on the hub filesystem.

### 8.3 Preference File Format

Every file has two sections: a **YAML front-matter** block (machine-parseable, used by the Preference Loader for quick lookups) and a **Markdown body** (natural-language context injected verbatim into the LLM prompt).

#### `_profile.md` — Global User Preferences

```markdown
---
user_token: u_a7f3
display_name: "User A"          # No real name stored on hub
language: en-IN
temperature_unit: celsius
timezone: Asia/Kolkata
accessibility:
  tts_speed: 1.0
  tts_volume: 80
  prefer_confirmations: false   # Don't ask "are you sure?" for simple actions
interaction_style: concise      # brief | verbose | concise
---

## Global Preferences

User A prefers concise responses without filler phrases. When reporting device
status, lead with the answer then add detail only if asked.

User A is usually the first to wake (around 06:30) and the last to sleep
(around 23:30). Adjust proactive suggestions to this schedule.

User A has a mild cold sensitivity — when ambient temperature drops below 21°C
in any occupied room, proactively suggest raising the temperature without
waiting to be asked.

For energy-saving suggestions, User A prefers to hear them as "you'll save ₹X
per month" framing rather than kWh figures.
```

#### `hvac_living_room.md` — HVAC Preferences for One Room

```markdown
---
user_token: u_a7f3
device_class: hvac
device_id: climate.living_room_hvac
zone: living_room
last_updated: 2026-04-15T18:22:00+05:30

# Machine-parseable quick-lookup fields
defaults:
  temperature_resting: 23
  temperature_active: 22
  temperature_sleeping: 26         # If this user falls asleep on the couch
  mode_default: auto
  fan_speed_default: auto

thresholds:
  comfort_min: 21                  # Below this → proactively suggest heating
  comfort_max: 26                  # Above this → proactively suggest cooling
  outdoor_temp_auto_off: 24        # Don't run AC if outdoor temp is comfortable

schedule:
  weekday_morning_on: "06:30"
  weekday_morning_temp: 23
  weekday_away_mode: "09:30"       # Reduce to eco mode when user leaves
  evening_return_temp: 23
  night_off: "23:45"
---

## HVAC Preferences — Living Room

User A prefers the living room at **23°C when resting** and **22°C when active**
(exercising, cooking nearby). During movie-watching, keep the temperature at 23°C
and do not change it mid-session even if the outdoor temperature drops — disrupting
a movie for climate adjustments is annoying.

When User A says "it's stuffy" rather than giving a temperature, interpret this as
a request to increase ventilation (fan speed: high) first before cooling.

If User A asks to "make it comfortable", default to 23°C auto mode without
asking for clarification.

Do not use dry mode unless explicitly requested — User A finds dry air
uncomfortable for extended periods.

Energy note: User A has agreed to pre-cooling between 14:00–17:00 at off-peak
tariff (₹4.2/kWh) rather than running full cooling at peak evening rates.
This is a standing preference — apply it automatically.
```

#### `lighting_bedroom_main.md` — Lighting Preferences

```markdown
---
user_token: u_a7f3
device_class: lighting
device_id: light.bedroom_main
zone: bedroom_main
last_updated: 2026-03-28T21:10:00+05:30

defaults:
  brightness_morning: 30          # % — gentle wake-up
  brightness_reading: 80
  brightness_evening: 40
  brightness_night: 5             # Nightlight level
  color_temp_morning: 4000        # Kelvin — cool white for waking up
  color_temp_evening: 2700        # Warm white for winding down
  color_temp_reading: 5000        # Daylight for reading

scene_mappings:
  wake_up: {brightness: 30, color_temp: 4000, transition: 300}   # 5-min sunrise
  reading: {brightness: 80, color_temp: 5000}
  movie:   {brightness: 10, color_temp: 2700}
  sleep:   {brightness: 0}
---

## Lighting Preferences — Master Bedroom

User A uses the bedroom light for reading most evenings. When they say "reading
light", set brightness to 80% at 5000K without asking which light.

User A dislikes abrupt light changes at night. Any adjustment after 21:00 should
use a 10-second transition rather than instant switching.

For the morning alarm integration: begin a 5-minute simulated sunrise at 06:25
(5 minutes before the alarm) — start at 0% warm white (2200K) and smoothly
transition to 30% cool white (4000K) by 06:30.

If User A says "dim it a bit", reduce brightness by 20 percentage points from
the current level, not to a fixed value.

Never turn off the bedroom lights completely via voice when the room is occupied
after 22:00 — instead switch to nightlight mode (5% warm) as a safety measure.
User A can explicitly say "lights off" to override this.
```

#### `front_door_lock.md` — Lock Preferences

```markdown
---
user_token: u_a7f3
device_class: lock
device_id: lock.front_door
last_updated: 2026-04-10T09:00:00+05:30

defaults:
  auto_lock_delay_minutes: 5      # Auto-lock 5 min after unlocking via app
  notify_on_unlock: true
  notify_on_left_open_minutes: 3  # Alert if door left open > 3 min

access_rules:
  ai_can_lock: true               # AI may lock door autonomously
  ai_can_unlock: false            # AI may NEVER unlock — human app action only
  unlock_requires: phone_confirm  # Even manual unlock shows a push confirmation
---

## Lock Preferences — Front Door

User A wants to be notified immediately any time the front door is unlocked,
regardless of who unlocked it.

When reporting door status, always state: locked/unlocked AND how long it has
been in that state (e.g., "locked since 21:40, about 2 hours ago").

If the door has been unlocked for more than 3 minutes without a person entering
(checked via motion sensor in the hallway), send a push alert and offer to lock
it. Do not auto-lock without user confirmation — just alert.

**Unlocking via AI is prohibited.** If User A asks the AI to unlock the door,
the AI must respond: "For security, I can't unlock the door remotely — please
use the app button." Then send a push notification with a one-tap unlock button
to the phone.
```

#### `shared/guest_mode.md` — Household-Level Shared Preferences

```markdown
---
scope: household
mode: guest
last_updated: 2026-04-01T12:00:00+05:30

guest_defaults:
  hvac_temp: 24
  lighting_brightness: 60
  music_volume: 40
  lock_notifications: true
  ai_access_level: limited        # Guests cannot change security settings
---

## Guest Mode

When guest mode is active, the AI should:
- Greet visitors with "Welcome! I'm the home assistant. I can help with
  lighting, temperature, and entertainment."
- Not disclose any information about the regular occupants' schedules or
  preferences.
- Not execute any security-related commands (locks, alarm) even if requested.
- Default all comfort settings to the household guest defaults above.
- Inform guests that security actions require the homeowner to be present.
```

### 8.4 Preference Loader

The `PreferenceLoader` is responsible for reading, parsing, and injecting the right Markdown files into the LLM context at request time.

```python
# core/preferences/preference_loader.py
import frontmatter      # python-frontmatter: parses YAML front-matter
import os, glob, asyncio
from pathlib import Path
from functools import lru_cache

class PreferenceLoader:
    """
    Loads per-user, per-device Markdown preference files and injects
    them into the LLM context. The YAML front-matter is used for
    machine-readable quick lookups; the Markdown body is injected
    verbatim into the LLM prompt as natural-language context.
    """

    PREF_ROOT = Path("/hub/preferences")

    def load_file(self, user_token: str, device_key: str) -> dict | None:
        """
        Load a single preference file and return:
          - metadata: parsed YAML front-matter (for quick parameter lookups)
          - prose: Markdown body (for LLM injection)
        """
        path = self.PREF_ROOT / user_token / f"{device_key}.md"
        if not path.exists():
            return None
        post = frontmatter.load(str(path))
        return {
            "metadata": post.metadata,    # Dict from YAML block
            "prose": post.content,        # Markdown body string
            "device_key": device_key,
        }

    def get_quick_param(
        self, user_token: str, device_key: str, *param_path: str
    ) -> any:
        """
        Fast lookup for machine-readable defaults — no LLM call needed.
        Example: get_quick_param("u_a7f3", "hvac_living_room",
                                 "defaults", "temperature_resting") → 23
        """
        pref = self.load_file(user_token, device_key)
        if pref is None:
            return None
        node = pref["metadata"]
        for key in param_path:
            if not isinstance(node, dict) or key not in node:
                return None
            node = node[key]
        return node

    def build_pref_context(
        self, user_token: str, devices_mentioned: list[str]
    ) -> str:
        """
        Build the preference context string to inject into the LLM prompt.
        Loads _profile.md + all device files relevant to this request.
        Returns a Markdown string ready for prompt injection.
        """
        sections = []

        # Always load the global user profile
        profile = self.load_file(user_token, "_profile")
        if profile:
            sections.append(f"### User Global Preferences\n{profile['prose']}")

        # Load device-specific files
        for device_key in devices_mentioned:
            pref = self.load_file(user_token, device_key)
            if pref:
                sections.append(
                    f"### Device Preferences: {device_key}\n{pref['prose']}"
                )

        # Also load shared/guest_mode if guest mode is active
        shared = self.load_file("shared", "guest_mode")
        if shared and self._is_guest_mode_active():
            sections.append(f"### Guest Mode Active\n{shared['prose']}")

        return "\n\n".join(sections)

    def update_preference(
        self, user_token: str, device_key: str,
        yaml_updates: dict, prose_append: str | None = None
    ) -> None:
        """
        Update a preference file programmatically (e.g., after learning
        from implicit feedback).
        Thread-safe write: write to temp file, then atomic rename.
        """
        path = self.PREF_ROOT / user_token / f"{device_key}.md"
        if path.exists():
            post = frontmatter.load(str(path))
        else:
            post = frontmatter.Post("")

        # Merge YAML updates (deep merge)
        post.metadata = _deep_merge(post.metadata, yaml_updates)
        if prose_append:
            post.content += f"\n\n{prose_append}"

        # Atomic write
        tmp = path.with_suffix(".tmp")
        with open(tmp, "w") as f:
            f.write(frontmatter.dumps(post))
        tmp.rename(path)

        # Commit change to Gitea (self-hosted git, audit trail)
        os.system(f"git -C {self.PREF_ROOT} add {path} && "
                  f"git -C {self.PREF_ROOT} commit -m "
                  f"'auto: update {device_key} for {user_token}'")

    def export_all(self, user_token: str) -> list[dict]:
        """For GDPR/DPDP right-to-access: export all preference files as dicts."""
        pattern = str(self.PREF_ROOT / user_token / "*.md")
        return [
            {"file": Path(p).stem, **frontmatter.load(p).metadata,
             "prose": frontmatter.load(p).content}
            for p in glob.glob(pattern)
        ]

    def delete_user_prefs(self, user_token: str) -> None:
        """GDPR/DPDP right-to-erasure."""
        import shutil
        shutil.rmtree(self.PREF_ROOT / user_token, ignore_errors=True)
        os.system(f"git -C {self.PREF_ROOT} commit -am "
                  f"'erasure: deleted all prefs for {user_token}'")
```

### 8.5 How Preference Files Are Used at Runtime

```
Request arrives (example: "set the bedroom lights for reading")

1. Device Classifier identifies: device_key = "lighting_bedroom_main"
   user_token = "u_a7f3" (from session)

2. Quick param lookup (no LLM):
   get_quick_param("u_a7f3", "lighting_bedroom_main",
                   "scene_mappings", "reading")
   → {brightness: 80, color_temp: 5000}
   → Dispatched directly as MCP call — ZERO LLM tokens spent

3. For ambiguous requests ("make it cosy in the bedroom"):
   build_pref_context("u_a7f3", ["lighting_bedroom_main", "_profile"])
   → Injects the Markdown prose into the Gemini prompt
   → LLM reads natural-language preferences and infers "cosy" = warm + dim
   → Selects {brightness: 40, color_temp: 2700}

4. For learning from feedback (user overrides brightness to 60%):
   update_preference("u_a7f3", "lighting_bedroom_main",
     yaml_updates={"scene_mappings": {"cosy": {brightness: 60, color_temp: 2700}}},
     prose_append="User A prefers 60% brightness for cosy lighting, not 40%."
   )
   → File updated atomically → git commit logged
```

### 8.6 Multi-User Disambiguation

When multiple users are in the same zone:

```python
# core/preferences/multi_user_resolver.py
class MultiUserPreferenceResolver:
    """
    When 2+ users are present in a zone, resolve conflicts between
    their preference files before passing to the orchestrator.
    """

    def resolve(
        self, user_tokens: list[str], device_key: str,
        context: dict
    ) -> dict:
        prefs = {
            token: self.loader.load_file(token, device_key)
            for token in user_tokens
        }

        # If one user explicitly requested — their pref wins
        if context.get("requesting_user"):
            return prefs[context["requesting_user"]]

        # Otherwise: find the median/compromise for numeric values
        # and pass all prose sections to LLM for natural language negotiation
        numeric_fields = self._extract_numeric_fields(prefs)
        compromise_yaml = {
            field: self._compromise(values)
            for field, values in numeric_fields.items()
        }

        # Build combined prose for LLM
        combined_prose = "\n\n".join([
            f"**{token}'s preferences:**\n{p['prose']}"
            for token, p in prefs.items() if p
        ])

        return {"metadata": compromise_yaml, "prose": combined_prose}
```

### 8.7 Mobile Access to Preference Files

Users can view and edit their preference files from the phone app:

```
Mobile App → Preference Editor Screen
├── Device list (shows all devices user has preferences for)
├── Tap a device → opens Markdown editor (split view: raw text + rendered preview)
├── Save → encrypted PUT to hub → hub writes file + git commits
├── "Reset to defaults" → restores factory preference template for that device
└── Export all → downloads all .md files as a ZIP (GDPR portability)
```

The app also exposes a **natural-language preference update** flow:

```
User: "Remember that I like the bedroom warmer than this"
→ Orchestrator detects preference update intent
→ Extracts: device=hvac_bedroom_main, field=temperature, direction=higher
→ Reads current temperature_resting from YAML front-matter (e.g. 23)
→ Updates to 24, appends prose note to the file
→ Confirms: "Got it — I've noted that you prefer the bedroom at 24°C when resting."
```

---

## 9. LLM Fine-Tuning & Alignment Plan

### 9.1 Where Fine-Tuning is Required vs. Prompt Engineering

| Component | Approach | Platform | Why |
|---|---|---|---|
| PII Detection (mobile) | **Fine-tune** Llama-3.2-1B → ONNX | Colab T4 → phone | Rule-based NER misses ~16% of smart home PII |
| PII Detection (hub) | **Presidio** (full Python) | Hub | Second-layer guard, no resource constraint |
| Wake Word | **Train custom** openWakeWord → ONNX | Colab T4 → phone + hub | Generic models: 5–10% false positive rate |
| HAR (Activity Recognition) | **Fine-tune** LightGBM on household data | Hub CPU | User-specific activity patterns |
| Preference Updater | **Prompt engineering** with Gemini | Cloud | LLM extracts preference updates from natural language |
| Intent Classification | **Prompt engineering** with Gemini | Cloud | Function calling sufficient |
| Safety Gate | **Hard-coded rules — NOT neural** | Hub | Neural safety gates are unreliable by design |

### 9.2 PII Model Fine-Tuning (with ONNX Mobile Export)

```python
# Full pipeline: fine-tune on Colab T4 → ONNX → CoreML/NNAPI

TRAINING_EXAMPLES = [
  {"text": "John usually gets home at 6pm from Koramangala",
   "entities": [{"start": 0, "end": 4, "label": "PERSON"},
                {"start": 37, "end": 47, "label": "LOCATION"}]},
  {"text": "unlock when my wife's car enters the gate",
   "entities": [{"start": 14, "end": 19, "label": "FAMILY_RELATION"}]},
  # Minimum 2,000 examples for production F1 > 90%
]

# Training: ~2 hours on Colab T4 free tier
# Export pipeline:  fine-tuned weights → ONNX → CoreML (iOS) + ONNX Runtime Mobile (Android)
# Target F1:        >94% on smart home PII corpus
# Mobile latency:   <80ms iOS, <120ms Android
```

### 9.3 Alignment — Preference File Learning

Rather than RLHF, the system learns by updating Markdown preference files directly from implicit and explicit feedback. This is simpler, more transparent, and auditable (git history):

```python
# core/alignment/preference_learner.py
class PreferenceLearner:
    """
    When a user overrides an AI decision, learn from it by updating
    the relevant Markdown preference file. No reward model needed.
    """

    async def on_user_override(
        self, user_token: str, device_key: str,
        ai_action: dict, user_override: dict
    ) -> None:
        # Determine what changed
        diff = self._compute_diff(ai_action, user_override)

        # Update YAML front-matter with new numeric preference
        yaml_update = self._diff_to_yaml_update(diff)

        # Generate a prose explanation using the hub Llama model
        prose_note = await self.llama.generate(
            f"The user overrode {ai_action} with {user_override}. "
            f"Write one sentence explaining what they prefer, "
            f"starting with 'User prefers...'"
        )

        # Atomically update the file and commit to git
        self.preference_loader.update_preference(
            user_token, device_key,
            yaml_updates=yaml_update,
            prose_append=prose_note
        )
```

---

## 10. Security & Zero-Trust Governance

### 10.1 Network Architecture (Updated for Mobile-First)

```
Internet
    │
    ▼
[Router — Firewall]
    │
    ├── VLAN 10 (Main devices) — laptops, phones (on home Wi-Fi)
    │
    ├── VLAN 20 (IoT devices) — all smart home hardware
    │       Blocked from internet
    │       Cannot initiate connections to VLAN 10
    │
    ├── VLAN 30 (AI Hub — Pi 5)
    │       Outbound HTTPS only:
    │         - generativelanguage.googleapis.com (Gemini)
    │         - huggingface.co (model update checks)
    │       Inbound: only from VLAN 10 (phone app) via mTLS
    │       NO inbound from internet
    │
    └── Remote Access (phone off home network)
            WireGuard VPN → VLAN 30
            All phone ↔ hub traffic inside VPN tunnel
            Gemini calls still go phone → hub → Gemini (hub is the egress point)
            OR phone → Gemini direct (if hub unreachable) — sanitised only
```

**Mobile off-network behaviour:**
```
Phone on mobile data / external Wi-Fi:
  Option A (preferred):  WireGuard VPN → home hub → Gemini
                         Hub remains the PII second-layer + safety gate
  Option B (fallback):   Phone → Gemini direct (if VPN unreachable)
                         Phone PII layer is the ONLY guard in this path
                         Only simple, non-sensitive commands allowed in this mode
                         Hub-dependent commands (lock status etc.) deferred
```

### 10.2 Agent Access Control Matrix

```python
AGENT_PERMISSIONS = {
    "comfort_agent": {
        "allowed_domains": ["climate", "light", "cover", "media_player"],
        "denied_domains": ["lock", "alarm_control_panel", "camera"],
        "max_temperature": 28, "min_temperature": 16,
        "require_human_approval": []
    },
    "security_agent": {
        "allowed_domains": ["lock", "alarm_control_panel", "binary_sensor"],
        "denied_domains": ["camera"],
        "allowed_lock_actions": ["lock"],    # NOT unlock — ever
        "require_human_approval": ["alarm_control_panel.disarm"]
    },
    "kitchen_agent": {
        "allowed_domains": ["switch", "sensor", "input_number"],
        "denied_domains": ["lock", "camera", "alarm_control_panel"],
        "max_oven_temperature": 250,
        "require_human_approval": ["switch.oven_main"]
    }
}
```

### 10.3 Audit Logging

```python
# Append-only SQLite WAL with hash chain — tamper-evident
class AuditLogger:
    def log_action(self, action: AuditEvent):
        entry = {
            "timestamp": utcnow().isoformat(),
            "event_id": uuid4().hex,
            "agent": action.agent_id,
            "intent": action.sanitised_intent,      # PII-free
            "tool_called": action.tool_name,
            "parameters": action.sanitised_params,
            "auth_result": action.auth_result,
            "outcome": action.outcome,
            "llm_used": action.llm_backend,         # gemini/llama/cached
            "pii_layer_triggered": action.pii_layer, # phone/hub/none
            "user_token": action.user_token,        # Pseudonymised
        }
        self.db.execute("INSERT INTO audit_log VALUES (?)", (json.dumps(entry),))
        prev_hash = self.db.get_last_hash()
        current_hash = sha256(json.dumps(entry) + prev_hash)
        self.db.update_hash_chain(entry["event_id"], current_hash)
```

---

## 11. Phased Deployment Plan

### Phase 0 — Foundation (Weeks 1–2)

```bash
□ Flash Raspberry Pi 5 with Raspberry Pi OS Lite (64-bit)
□ Install Docker + Docker Compose
□ Deploy Home Assistant OS in Docker
□ Configure VLANs + WireGuard VPN (for mobile remote access)
□ Deploy Infisical (secret management)
□ Deploy Caddy (TLS + mTLS for hub ↔ phone)
□ Deploy Authelia (SSO/OIDC)
□ Deploy Gitea (preference file version control)
□ Set up Prometheus + Grafana + Loki (observability first)
□ Configure automated daily encrypted backups
```

### Phase 1 — Mobile App + Voice Baseline (Weeks 3–5)

```bash
□ Build Flutter mobile app skeleton (iOS + Android)
□ Integrate WhisperKit (iOS) + whisper.cpp JNI (Android)
□ Integrate openWakeWord ONNX on phone
□ Integrate Piper TTS ONNX on phone
□ Test end-to-end voice pipeline (phone only, no hub yet)
□ Verify ASR accuracy on all household members' voices
□ Custom wake word training → ONNX → ship in app

# Acceptance criteria:
✓ Wake word: <2% false positives/day
✓ ASR: >90% accuracy on typical home commands
✓ TTS: naturalness rating >3.5/5
✓ Phone-only pipeline latency: p95 < 3s
```

### Phase 2 — Mobile PII Firewall (Weeks 6–7) — MANDATORY BEFORE CLOUD LLM

```bash
□ Collect 500+ smart home PII annotation examples
□ Fine-tune Llama-3.2-1B on Colab T4 (free tier, ~2 hours)
□ Export to ONNX → CoreML (iOS) → ONNX Runtime Mobile (Android)
□ Integrate MobilePIIFirewall into Flutter app
□ Implement SecureTokenVault using iOS Secure Enclave + Android HSM
□ Deploy Presidio on hub (second-layer guard)
□ Implement token vault sync protocol (phone → hub, session-scoped)
□ Run PII audit: verify ZERO unredacted PII reaches Gemini or hub filesystem

# Acceptance criteria:
✓ Mobile PII detection F1: >90%
✓ Hub second-layer catches residual: verified in adversarial test
✓ Zero PII in any cloud API call (log verified)
✓ Token rehydration: 100% accuracy
✓ Vault encryption: hardware-backed (Secure Enclave / HSM confirmed)
```

### Phase 3 — Preference File System (Weeks 8–9)

```bash
□ Create preference directory structure on hub (/hub/preferences/)
□ Write preference file templates for all device classes
□ Initialise preference files for all household users (with defaults)
□ Implement PreferenceLoader (load, quick-param, build-pref-context)
□ Implement preference editor UI in mobile app (Markdown editor + preview)
□ Implement natural-language preference update intent detection
□ Implement PreferenceLearner (implicit feedback → file update → git commit)
□ Wire preference context into Gemini prompt construction
□ Wire quick-param lookup for simple commands (zero LLM token path)

# Acceptance criteria:
✓ Simple command using quick-param: 0 LLM tokens consumed
✓ Preference prose correctly injected into LLM context (verified in logs)
✓ User override → file updated → git committed (verified)
✓ All preference files readable by household members via app editor
```

### Phase 4 — Core AI Orchestration (Weeks 10–12)

```bash
□ Set up Gemini API key (Google AI Studio — free)
□ Implement LangGraph orchestrator with 5 agents
□ Build MCP servers for each device class
□ Implement circuit breaker (cloud → hub Llama fallback)
□ Deploy llama.cpp server (Llama-3.2-3B Q4_K_M) on hub
□ Build LLM Decision Router
□ Connect orchestrator to HA via MCP
□ Implement Safety Gate (hard-coded rule engine)
□ Implement Action Authority (access control)
□ Test 50 common household utterances — 100% must pass safety gate
□ Multi-user disambiguation test with 2 concurrent users

# Acceptance criteria:
✓ Task completion rate: >85% on test suite
✓ Zero safety violations in 1,000 adversarial commands
✓ Preference context correctly shapes LLM decisions (A/B verified)
✓ All actions in audit log with correct user_token and pii_layer fields
```

### Phase 5 — HAR + Proactive (Weeks 13–15)

```bash
□ Deploy HAR data collection pipeline (passive, 4-week run)
□ Train LightGBM HAR model on collected household data
□ Build proactive trigger engine (activity change → contextual suggestion)
□ Tune proactive suggestion threshold (avoid annoyance)
□ User acceptance testing — proactive suggestion acceptance rate target: >40%
```

### Phase 6 — Production Hardening (Weeks 16–17)

```bash
□ Penetration test on local network + mobile app (OWASP Mobile Top 10)
□ Disaster recovery drill (restore from backup, measure RTO)
□ Load test: 3 occupants × 10 requests/hour sustained
□ GDPR/DPDP compliance review and sign-off
□ Monthly preference-learning pipeline verified end-to-end
□ Write operational runbook
□ User acceptance testing — all household members, minimum 1 week

# Production exit criteria:
✓ System uptime: >99.5% over 2-week test period
✓ Zero PII leakage events
✓ Safety gate: 100% pass on adversarial set
✓ Backup restore: tested and verified
✓ All household members comfortable with voice interface
```

---

## 12. Zero-Cost Budget Breakdown

### One-Time Hardware Costs

| Item | Cost (INR) | Notes |
|---|---|---|
| Raspberry Pi 5 (8GB) | ₹8,000 | Or use existing PC/laptop |
| ReSpeaker USB (optional) | ₹2,500 | Phone mic is primary — this is optional for hub-side ASR |
| UWB Dev Kit (optional) | ₹4,000 | Location-aware features |
| Zigbee USB Dongle | ₹2,000 | If using Zigbee devices |
| **Total hardware** | **₹8,000–16,500** | One-time only |

> If you already own a PC (≥16GB RAM), hardware cost = ₹0.

### Ongoing Monthly Costs

| Service | Cost | Notes |
|---|---|---|
| Gemini 2.0 Flash API | **$0** | Free tier: 1M tokens/day |
| Home Assistant | **$0** | Open source, self-hosted |
| All AI/ML libraries | **$0** | Open source |
| Mobile app distribution | **$0** | Sideload on Android; TestFlight for iOS household |
| Hosting/Cloud | **$0** | Everything runs locally or on free Gemini tier |
| **Total monthly** | **$0** | Zero ongoing cost |

### Free Resources for Fine-Tuning

| Task | Resource | Cost |
|---|---|---|
| PII model fine-tune + ONNX export | Google Colab T4 (free tier) | $0 |
| HAR model training | Hub CPU (LightGBM is fast) | $0 |
| Wake word training + ONNX export | Google Colab T4 | $0 |
| Monthly preference learner review | Hub CPU | $0 |

---

## 13. Production Readiness Checklist

### Security
- [ ] All secrets in Infisical vault — zero hardcoded credentials
- [ ] IoT devices on isolated VLAN
- [ ] WireGuard VPN for mobile remote access
- [ ] mTLS between phone and hub
- [ ] TLS 1.3 on all external calls (Gemini)
- [ ] Authelia SSO protecting admin interfaces
- [ ] Audit log with hash chain implemented and tested
- [ ] OWASP Mobile Top 10 review completed for Flutter app
- [ ] Agent access control matrix implemented and tested

### Privacy
- [ ] Mobile PII firewall validated — zero cloud PII leakage confirmed
- [ ] Hub second-layer PII guard operational and alerting
- [ ] Token vault hardware-backed (Secure Enclave / Android HSM confirmed)
- [ ] Token vault sync is session-scoped and RAM-only on hub
- [ ] Preference files: no real names or raw PII in filenames or content
- [ ] User data rights endpoints (access, erase, export Markdown files) operational
- [ ] Data retention policies implemented
- [ ] Consent mechanism for new users implemented

### Reliability
- [ ] Circuit breaker tested (cloud LLM failure → hub Llama within 2s)
- [ ] Hub offline → phone executes cached simple commands
- [ ] All MCP tools have input validation and safe defaults
- [ ] Safety gate tested with 1,000 adversarial commands — 0 violations
- [ ] Backup tested — restore from backup verified
- [ ] Health checks on all services with Prometheus alerts

### Preference System
- [ ] All device classes have preference file templates
- [ ] All household users have initialised preference files
- [ ] Quick-param lookup working (simple commands consume 0 LLM tokens)
- [ ] Prose injection verified in LLM prompt logs
- [ ] Preference editor working in mobile app (view + edit + preview)
- [ ] Natural-language preference update intent correctly updates files
- [ ] Implicit feedback (user override) correctly updates preference file + git commit
- [ ] Multi-user conflict resolution tested with 2 concurrent users

### Performance
- [ ] End-to-end latency p50 < 3s, p95 < 6s (phone → response)
- [ ] Mobile PII firewall latency: <120ms on mid-range Android
- [ ] Quick-param path: <50ms (file read + MCP call)
- [ ] Whisper ASR accuracy >90% for all household members on their devices

### Compliance
- [ ] GDPR Article 13 / DPDP equivalent notice available to users
- [ ] Data processing register maintained
- [ ] Preference file export (portability) verified end-to-end
- [ ] Preference file deletion (erasure) verified with git audit trail

---

## Appendix A — Directory Structure (Updated)

```
smart-home-ai/
├── docker-compose.yml
│
├── core/
│   ├── orchestrator/
│   │   ├── graph.py
│   │   ├── router.py
│   │   └── agents/
│   │       ├── comfort_agent.py
│   │       ├── security_agent.py
│   │       ├── kitchen_agent.py
│   │       ├── entertainment_agent.py
│   │       └── resource_agent.py
│   │
│   ├── llm/
│   │   ├── gemini_client.py
│   │   ├── llama_client.py
│   │   ├── circuit_breaker.py
│   │   └── task_memory.py
│   │
│   ├── preferences/                   # NEW
│   │   ├── preference_loader.py       # Load, parse, inject Markdown prefs
│   │   ├── preference_learner.py      # Implicit feedback → file update
│   │   ├── multi_user_resolver.py     # Conflict resolution for shared zones
│   │   └── templates/                 # Default .md templates per device class
│   │       ├── hvac.md.template
│   │       ├── lighting.md.template
│   │       ├── lock.md.template
│   │       ├── tv.md.template
│   │       ├── kitchen_oven.md.template
│   │       └── ev_charger.md.template
│   │
│   ├── privacy/
│   │   ├── hub_pii_guard.py           # Second-layer Presidio check
│   │   ├── token_sync.py              # Phone→hub token vault sync
│   │   ├── token_vault.py             # Hub-side session token store (RAM)
│   │   └── data_rights.py
│   │
│   ├── security/
│   │   ├── access_control.py
│   │   ├── safety_gate.py
│   │   └── audit_logger.py
│   │
│   └── voice/
│       ├── pipeline.py
│       └── context_builder.py
│
├── mobile/                            # NEW — Flutter app
│   ├── lib/
│   │   ├── pii/
│   │   │   ├── mobile_pii_firewall.dart
│   │   │   └── secure_token_vault.dart
│   │   ├── voice/
│   │   │   ├── whisper_client.dart
│   │   │   ├── wake_word_detector.dart
│   │   │   └── piper_tts.dart
│   │   ├── preferences/
│   │   │   ├── preference_editor.dart  # Markdown editor UI
│   │   │   └── preference_api.dart     # Hub REST client for prefs
│   │   └── main.dart
│   ├── ios/
│   │   └── Runner/
│   │       └── PIIClassifier.mlpackage  # CoreML model
│   └── android/
│       └── app/src/main/assets/
│           └── pii_classifier.onnx      # ONNX Runtime Mobile model
│
├── preferences/                       # NEW — per-user per-device Markdown files
│   ├── u_a7f3/
│   │   ├── _profile.md
│   │   ├── hvac_living_room.md
│   │   ├── lighting_bedroom_main.md
│   │   ├── front_door_lock.md
│   │   └── ...
│   ├── u_b912/
│   │   └── ...
│   └── shared/
│       ├── guest_mode.md
│       └── energy_policy.md
│
├── mcp_servers/
│   ├── comfort_server.py
│   ├── security_server.py
│   ├── kitchen_server.py
│   ├── entertainment_server.py
│   └── resource_server.py
│
├── har/
│   ├── data_collector.py
│   ├── feature_engineer.py
│   ├── lgbm_model.py
│   └── inference_service.py
│
├── training/
│   ├── pii_finetune.py
│   ├── export_pii_model_to_onnx.py    # NEW — ONNX + CoreML export pipeline
│   ├── har_training.py
│   └── wakeword_training.py
│
├── monitoring/
│   ├── prometheus/
│   ├── grafana/
│   └── loki/
│
└── tests/
    ├── safety/
    │   └── adversarial_commands.py
    ├── privacy/
    │   ├── pii_leakage_test.py
    │   └── mobile_pii_bypass_test.py   # NEW — tests hub second layer catches bypasses
    ├── preferences/
    │   └── preference_loader_test.py    # NEW
    └── integration/
        └── full_pipeline_test.py
```

---

## Appendix B — Critical Anti-Patterns to Avoid

| Anti-Pattern | Production Problem | Correct Approach |
|---|---|---|
| Sending raw transcriptions to hub or cloud | PII/GDPR violation | Mobile PII Firewall first — always, before any network call |
| Phone as thin client (raw audio sent to hub) | Audio contains biometric data | ASR + PII scrubbing on phone; only sanitised text leaves the device |
| Single PII layer (phone only) | Mobile ONNX model misses edge cases | Defence in depth: phone (primary) + hub Presidio (secondary) |
| Storing preference data in a cloud DB | Privacy / cost risk | Markdown files on hub filesystem, git-versioned, never cloud-synced |
| Hardcoding preferences in code | Cannot update without redeploy | All preferences in Markdown files, editable at runtime via app |
| Real names in preference file paths | PII in filesystem | Pseudonymised user_token as directory name; token mapping on phone only |
| Exposing `unlock_door` as MCP tool | AI can unlock house | Unlock removed from tool registry; requires human one-tap in app |
| Neural network as safety gate | Safety bypass via adversarial prompt | Hard-coded rule engine — zero LLM involvement |
| Voice audio written to disk | Biometric data retention risk | Audio processed in phone RAM only; never persisted |
| Single LLM (no fallback) | System breaks on API outage | Circuit breaker: cloud → hub Llama → cached simple commands |
| Task memory in RAM only | Preferences lost on restart | Markdown files persist to disk + git; ChromaDB on encrypted disk |
| Generic wake word | High false positive rate | Train custom wake word on 500 household samples → ONNX for phone |

---

*Document version: 2.0 — Mobile-First Production Blueprint*
*Changes from v1.0: (1) Per-user per-device Markdown preference system. (2) Mobile phone as primary edge device with on-phone PII firewall, dual-layer PII architecture, ONNX model export pipeline, and WireGuard VPN for remote access.*
*Regulatory references: GDPR (EU) 2016/679, India DPDP Act 2023, Matter Specification 1.3*
*All cost estimates verified against free tier terms as of April 2026*