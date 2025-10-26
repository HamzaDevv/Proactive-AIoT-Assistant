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

for the “THINK” layer to consume.

Module 2: The “THINK” Layer — Core AI & Memory

Owner: [Team Member 2]
Description: The “brain” — manages reasoning, orchestration, and memory.

Key Files:

main.py

memory/conversational_memory.py

memory/knowledge_base.py

Responsibilities:

Build the main async event loop in main.py.

Fetch context data from the SENSE module.

Manage user preference storage using ChromaDB.

Perform prompt engineering for the LLM.

Parse LLM responses and forward commands to the ACT layer.

Module 3: The “ACT” Layer — Interface & IoT Control

Owner: [Team Member 3]
Description: The “hands and voice” — handles all output to users and devices.

Key Files:

speak.py

listen.py

iot_control.py or tools/mqtt_client.py

Responsibilities:

Implement voice I/O (text-to-speech + speech recognition).

Capture user confirmations (Yes/No).

Send standardized MQTT commands like:

home/lights/set 'on'


(Future) Add MQTT subscription for sensor feedback.

🧰 Tech Stack
Layer	Technology
Core Logic	Python
Reasoning Engine	LLM (Ollama, Gemini)
Memory	ChromaDB (Vector Database)
APIs	Google Fit, Google Maps, Google Calendar
IoT Protocol	MQTT
Voice I/O	SpeechRecognition, pyttsx3 (or macOS say)
⚙️ Setup & Installation
# 1. Clone the repository
git clone https://github.com/HamzaDevv/IOT-Sadaf-BOT.git
cd IOT-Sadaf-BOT

# 2. Create a virtual environment
python3 -m venv venv
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure API Keys
cp .env.example .env
# Add your Google Fit, Maps, Calendar, and Gemini API keys

# 5. Run Ollama (if using)
ollama pull llama3

# 6. Start the assistant
python3 main.py

🔮 Future Work

🛰️ Add More Senses: Local MQTT-based sensors (air quality, temperature, light).

⚡ Add More Actions: Control smart blinds, kitchen appliances, or media devices.

🧩 Refine Memory: Learn from user “No” responses to improve personalization.

🤝 Contributors
Module	Owner	Role
SENSE	[Team Member 1]	API & Data Integration
THINK	[Team Member 2]	Core Logic & Memory
ACT	[Team Member 3]	Voice & IoT Control
📜 License

This project is licensed under the MIT License.
Feel free to use, modify, and build upon it.

“Sadaf isn’t just smart — it’s aware. It learns, adapts, and supports you before you even have to ask.”
- Implement API clients for Google Fit, Maps, and Calendar.  
- Provide standardized interfaces like:
  ```python
  get_user_status()
  get_upcoming_events()
