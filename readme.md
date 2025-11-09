# README.md
# Sadaf - Proactive Home Assistant

This project contains the complete code for the Sadaf assistant, split into three modules:

1.  **Module 1 (SENSE):** Simulates sensor inputs and builds a `ContextPacket`.
2.  **Module 2 (THINK):** Uses a two-pass LLM pipeline and rules to generate a `SuggestionSchema`.
3.  **Module 3 (ACTION):** Simulates IoT devices, executes actions, and provides a real-time frontend.

## How to Run

1.  Install dependencies:
    `pip install -r requirements.txt`

2.  Run the main script:
    `python run.py`

This will start all three services on different ports:
* **Module 1 (SENSE):** `http://localhost:8001`
* **Module 2 (THINK):** `http://localhost:8002`
* **Module 3 (ACTION):** `http://localhost:8003`

3.  **Open the frontend in your browser:**
    **`http://localhost:8003`**

You can see the system state and suggestions appear on this page. Module 1 will automatically send a new context every 10 seconds.