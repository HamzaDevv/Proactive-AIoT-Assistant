import httpx
import logging
import json  # <-- IMPORTED
from pathlib import Path  # <-- IMPORTED
from fastapi import FastAPI, HTTPException, BackgroundTasks, Request

# Import the new config and memory classes
from config import GLOBAL_LLM, CHROMA_COLLECTION_NAME, CHROMA_PERSIST_DIR
from memory import ChromaStore

# Import the refactored orchestrator and client
from THINK_module.think_orchestrator import ThinkOrchestrator, LangchainLLMClient
from common.schemas import ContextPacket, SuggestionSchema

# --- Config ---
ACTION_MODULE_URL = "http://localhost:8003"
# --- FIX: Define path to devices.json (assuming it's in the project root) ---
DEVICES_JSON_PATH = Path(__file__).parent.parent / "devices.json"
# --------------

app = FastAPI(title="Module 2: THINK")
client = httpx.AsyncClient()
logger = logging.getLogger("sadaf.think.service")


# --- Startup Initialization ---
@app.on_event("startup")
async def startup_event():
    """
    Initializes all required services on startup and stores them in app.state.
    """
    try:
        # 0. Load Device Capabilities
        if not DEVICES_JSON_PATH.exists():
            logger.error(f"FATAL: devices.json not found at {DEVICES_JSON_PATH}")
            # We can't continue without this.
            raise FileNotFoundError(f"devices.json not found at {DEVICES_JSON_PATH}")

        with open(DEVICES_JSON_PATH, "r") as f:
            devices_data = json.load(f)

        # Convert list of devices to a map[id, caps] for fast lookup
        app.state.device_capabilities = {
            dev["id"]: {
                "functions": dev.get("functions", []),
                "parameters": dev.get("parameters", {}),
            }
            for dev in devices_data.get("devices", [])
        }
        logger.info(
            f"Loaded capabilities for {len(app.state.device_capabilities)} devices."
        )

        # 1. Initialize Memory Store (using your new class)
        app.state.memory = ChromaStore(
            collection_name=CHROMA_COLLECTION_NAME, persist_directory=CHROMA_PERSIST_DIR
        )

        # 2. Initialize LLM Client (using LLM from config)
        if GLOBAL_LLM is None:
            raise ValueError("GLOBAL_LLM is None. Check config.py and LLM service.")
        app.state.llm_client = LangchainLLMClient(llm=GLOBAL_LLM)

        # 3. Initialize the main Orchestrator
        # --- FIX: Pass device capabilities map to orchestrator ---
        app.state.orchestrator = ThinkOrchestrator(
            llm_client=app.state.llm_client,
            memory=app.state.memory,
            device_capabilities=app.state.device_capabilities,
            cooldown_minutes=10,  # Use a reasonable default cooldown
        )

        # 4. Pre-populate memory (using new add_document method)
        app.state.memory.add_document(
            "User prefers a bath at 42 degrees Celsius after a workout.",
            {"tag": "preference", "type": "fact"},
        )

        app.state.memory.add_document(
            "After stressful meetings, the user likes soft lighting and calm music.",
            {"tag": "preference", "type": "fact"},
        )

        logger.info("THINK: Service started, orchestrator and memory initialized.")
    except Exception as e:
        logger.exception(f"FATAL: Failed to initialize THINK module: {e}")
        app.state.orchestrator = None  # Mark as failed


# --- Utility Functions ---
async def forward_suggestion(suggestion: SuggestionSchema):
    """Sends the suggestion to Module 3."""
    if not suggestion.should_suggest:
        return

    logger.info(f"THINK: Forwarding suggestion to ACTION: {suggestion.suggestion_text}")
    try:
        await client.post(
            f"{ACTION_MODULE_URL}/suggest",
            json=suggestion.dict(exclude_unset=True),
            timeout=5.0,
        )
    except Exception as e:
        logger.error(f"THINK: Error forwarding suggestion to ACTION: {e}")


# --- API Endpoints ---
@app.post("/process_context", status_code=202)
async def process_context_endpoint(
    packet: ContextPacket,
    request: Request,  # <-- Add request to access app.state
    background_tasks: BackgroundTasks,
):
    """
    Receives a ContextPacket, processes it, and forwards suggestions.
    """
    orchestrator: ThinkOrchestrator = request.app.state.orchestrator

    if not orchestrator:
        logger.error("Rejecting request: THINK module is not initialized.")
        raise HTTPException(
            status_code=503, detail="THINK module is not initialized. Check logs."
        )

    try:
        suggestion = await orchestrator.process_context(packet)

        if suggestion.should_suggest:
            background_tasks.add_task(forward_suggestion, suggestion)

        return {"status": "processing", "suggestion_confidence": suggestion.confidence}
    except Exception as e:
        logger.exception(f"THINK: Error in process_context: {e}")
        raise HTTPException(status_code=500, detail="Error processing context")


@app.get("/")
def read_root(request: Request):
    is_ready = (
        hasattr(request.app.state, "orchestrator")
        and request.app.state.orchestrator is not None
    )
    return {
        "module": "THINK",
        "status": "running" if is_ready else "failed_initialization",
    }
