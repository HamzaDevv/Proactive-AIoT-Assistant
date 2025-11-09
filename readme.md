Proactive AIoT Assistant (Sadaf)
An intelligent, proactive assistant that senses user and environmental context, thinks using a reasoning-and-memory pipeline, and takes safe, human-in-the-loop actions on IoT devices.

This repository contains the source code for Sadaf, a modular AIoT assistant built with FastAPI, Gemini, and ChromaDB. It is designed to be extensible, reliable, and safe, moving beyond simple voice commands to provide proactive, contextual help.

🏛️ Core Architecture
The system is built on a clear, three-module "SENSE-THINK-ACTION" pipeline, inspired by human cognition.

Code snippet

graph TD;
    subgraph SENSE Layer (Module 1)
        direction TB
        A[Sensors (Google Fit, Maps, CCTV)] --> B(FastAPI Gateway);
        B --> C[Context Packet Builder];
    end
    subgraph THINK Layer (Module 2)
        direction TB
        C --> D{Decision Graph};
        D --> E[LLM Pipeline (Gemini)];
        E --> F[Vector Memory (ChromaDB)];
        F --> G[Safety Rule Layer];
    end
    subgraph ACTION Layer (Module 3)
        direction TB
        G --> H(Action API);
        H --> I[IoT Devices (Simulated)];
        H --> J[React Frontend];
    end

    %% Feedback Loops
    I --> A;
    J -- User Feedback --> F;
✨ Key Features
Proactive & Context-Aware: Instead of waiting for commands, the assistant monitors the "Context Packet" (biometrics, location, schedule, environment) to proactively suggest actions.

Extensible Plugin System: The SENSE layer is built as a plugin system, making it easy to add new sensors (e.g., air_quality.py, light_sensor.py) without rewriting core logic.

Safety-First Reasoning: The THINK layer uses a "Decision Graph" for preliminary logic and a "Safety Rule Layer" to hard-code critical rules (e.g., "Never turn off the refrigerator"), reducing LLM hallucinations.

Adaptive Memory: Learns from user acceptance ("Yes") and rejection ("No") by storing preferences in a ChromaDB vector store, preventing repeated bad suggestions.

Human-in-the-Loop: All proactive actions are presented as suggestions to the user for confirmation, maintaining user control.

Real-time & Observable: The ACTION layer uses WebSockets/SSE to stream state changes instantly to the frontend and maintains detailed action logs for debugging.

🔧 Technical Deep Dive
1. SENSE Layer (Module 1)
This module's sole job is to gather data, normalize it, and package it.

Data Sources: Integrates with APIs like Google Fit, Calendar, and Maps, as well as sensors like cameras and mobile device states.

Context Packet: All data is bundled into a single, timestamped ContextPacket object every cycle. This packet includes "Confidence Scores" for each piece of data to handle sensor noise.

Gateway: A FastAPI endpoint serves as the main entry point for all sensor data.

2. THINK Layer (Module 2)
This is the brain of the assistant. It receives the ContextPacket and decides what to do.

Technology: Gemini Flash 2.0, ChromaDB, Pydantic.

Flow:

Decision Graph: A simple logic engine runs first (e.g., IF room_empty AND lights_on THEN...).

LLM Pipeline (Two-Pass):

Pass 1 (Reasoning): The LLM receives the context, memory, and decision graph output to form an intention and a human-friendly summary.

Pass 2 (Action): The LLM formats the intention into a strict Pydantic JSON schema for the ACTION layer.

Memory Hooks: User feedback is used to update the ChromaDB vector store.

Safety Rule Layer: A final check ensures the validated action doesn't violate hard-coded safety rules.

3. ACTION Layer (Module 3)
This module executes the validated commands from the THINK layer and reports state back to the user.

Device Capability Schema: Each IoT device (even simulated) publishes a schema of its "functions" (["wash", "dry"]) and "parameters" ({"temp": [20, 50]}). The THINK layer uses this to validate commands.

State Stream: A WebSocket or Server-Sent Events (SSE) stream provides real-time updates to any connected frontend (e.g., React).

Action Log: All actions, triggers, and user responses are logged to a database for debugging and pattern analysis.

💻 Technology Stack
Backend: FastAPI, Pydantic (for strict data validation)

AI & LLM: Google Gemini Flash 2.0

Vector Database: ChromaDB

Frontend (Recommended): React or Next.js

Real-time: WebSockets or Server-Sent Events (SSE)

Core: Python 3.11+

🚀 Getting Started
These instructions will get you a copy of the project up and running on your local machine for development and testing.

Prerequisites
Python 3.11+

Poetry or pip with venv

A Google AI Studio API Key for Gemini

Installation
Clone the repository:

Bash

git clone https://github.com/HamzaDevv/Proactive-AIoT-Assistant.git
cd Proactive-AIoT-Assistant
Create a virtual environment:

Bash

python -m venv venv
On Windows: .\venv\Scripts\activate

On macOS/Linux: source venv/bin/activate

Install dependencies: (Make sure you have a requirements.txt file in your root directory)

Bash

pip install -r requirements.txt
Set up environment variables: Create a .env file in the root directory and add your API keys:

Code snippet

GOOGLE_API_KEY="YOUR_GEMINI_API_KEY_HERE"
Run the application: The project uses FastAPI. You can run it with uvicorn:

Bash

uvicorn src.main:app --reload
This will start the server at http://127.0.0.1:8000.

License
This project is licensed under the MIT License - see the LICENSE file for details.

📁 Recommended File Structure & Basic Files
To get you started, here is a recommended file structure based on the modular architecture from the PDF. You can create these folders and files to build your project.

Recommended Directory Tree
Proactive-AIoT-Assistant/
├── .gitignore               # (Content provided below)
├── README.md                # (The file above)
├── requirements.txt         # (Content provided below)
├── .env                     # (For your API keys)
└── src/
    ├── __init__.py
    ├── main.py              # (Your main FastAPI app)
    │
    ├── core/                # (Shared logic)
    │   ├── __init__.py
    │   ├── schemas.py       # (Pydantic models, e.g., ContextPacket)
    │   └── logging_config.py # (Event logging setup)
    │
    ├── module_1_sense/      # (SENSE Layer)
    │   ├── __init__.py
    │   ├── sense_manager.py # (Orchestrates all plugins)
    │   └── plugins/
    │       ├── __init__.py
    │       ├── fit.py       # (Google Fit plugin)
    │       ├── maps.py      # (Google Maps plugin)
    │       ├── calendar.py  # (Google Calendar plugin)
    │       └── camera.py    # (CCTV/Occupancy plugin)
    │
    ├── module_2_think/      # (THINK Layer)
    │   ├── __init__.py
    │   ├── think_manager.py # (Main entrypoint for this layer)
    │   ├── decision_graph.py # (Pre-LLM logic rules)
    │   ├── llm_pipeline.py  # (Gemini two-pass logic)
    │   ├── memory.py        # (ChromaDB connection and hooks)
    │   └── safety.py        # (The final Safety Rule Layer)
    │
    ├── module_3_action/     # (ACTION Layer)
    │   ├── __init__.py
    │   ├── action_manager.py # (Receives commands, talks to devices)
    │   ├── device_simulator.py # (Simulates IoT devices)
    │   ├── schemas.py       # (Device Capability Schemas)
    │   └── websocket_manager.py # (SSE/WebSocket stream)
    │
    └── frontend/                # (Your React app can live here)
        └── ...
Basic File Contents
Here is the content for the basic files you should add to your repository.

1. .gitignore
This file tells Git to ignore common Python files and environment folders.

Code snippet

# Virtual Environment
venv/
.venv/
env/
.env

# Python cache
__pycache__/
*.pyc
*.pyo
*.pyd

# IDE / Editor
.vscode/
.idea/
*.swp
*.swo

# OS-specific
.DS_Store
Thumbs.db
2. requirements.txt
This lists the core dependencies mentioned in your architectural plan. You will need to add more as you build.

# Core Web Framework
fastapi
uvicorn[standard]

# Data Validation
pydantic

# LLM & AI
google-generativeai

# Vector Database
chromadb

# API Clients (examples)
google-api-python-client
google-auth-httplib2
google-auth-oauthlib
You can now create these files, git add ., git commit -m "Initial project structure", and git push them to your GitHub repository.
