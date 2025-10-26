# 🌐 Sadaf: A Proactive AIoT Assistant

**Sadaf** is an intelligent **AIoT (Artificial Intelligence of Things)** orchestrator — a centralized "brain" that moves beyond reactive smart assistants toward *proactive, context-aware support*.  
It doesn’t just respond to your commands; it *anticipates your needs* by fusing real-time data from your personal devices and environment.

---

## 🚀 The Problem We Solve

Current “smart” devices are merely *connected*, not *intelligent*. They live in isolated data silos:

- Your **smartwatch** knows you slept poorly — but your **coffee maker** doesn’t.
- Your **calendar** knows you have a stressful meeting — but your **smart lights** don’t.
- Your **voice assistant** forgets what you told it yesterday.

**Sadaf** breaks down these silos to create a unified, *context-aware* ecosystem that understands your holistic state and learns your preferences over time.

---

## 🧠 Core Concept: The Sense–Think–Act Loop

Sadaf operates on a simple but powerful continuous loop:

### 1. **SENSE**
Gathers real-time data from multiple sources:
- **Biometric:** Smartwatch (heart rate, sleep, activity)
- **Contextual:** Location & ETA (Google Maps)
- **Schedule:** Events (Google Calendar)
- **Environmental (Future):** Air quality, temperature, light level sensors

### 2. **THINK**
Processes all this information using:
- **Large Language Model (LLM):** (Ollama, Gemini)
- **Long-Term Vector Memory:** (ChromaDB)
  
This layer reasons about your *context* and *preferences* to anticipate what you might need next.

### 3. **ACT**
Executes or suggests actions:
- Voice prompt: _“You’re home from your run; should I start the bath?”_
- With confirmation, it controls IoT devices via **MQTT**.

---

## 🌟 Key Features

✅ **Proactive Suggestions** — Anticipates needs from fused, real-time data.  
🧠 **Long-Term Memory** — Learns habits and preferences via ChromaDB.  
🙋 **Human-in-the-Loop** — Always asks for confirmation before acting.  
🔌 **Extensible Tool System** — Easily add new APIs or devices.  
📡 **Decoupled IoT Control** — Uses lightweight MQTT for scalable communication.  

---

## 🧩 Architecture & Modular Breakdown

Sadaf is built around three core modules — ideal for parallel team development.

---

### **Module 1: The “SENSE” Layer** — *Data & API Integration*

**Owner:** [Team Member 1]  
**Description:** The “senses” of the AI — handles all external data input.  

**Key Files:**  
- `tools/google_fit.py`  
- `tools/google_maps.py`  
- `tools/google_calendar.py`  

**Responsibilities:**
- Implement API clients for Google Fit, Maps, and Calendar.  
- Provide standardized interfaces like:
  ```python
  get_user_status()
  get_upcoming_events()
