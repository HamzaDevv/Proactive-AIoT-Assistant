# config.py
from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv
import os

load_dotenv()

# Verify API key exists
if not os.getenv("GOOGLE_API_KEY"):
    raise ValueError("GOOGLE_API_KEY not found in environment variables")

# ------------------ LLM Config ------------------
# Make sure your GOOGLE_API_KEY is in your .env file
TEMPERATURE_OF_LLM = 0.0  # 0.0 = deterministic output, 1.0 = more creative
GLOBAL_LLM = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash", temperature=TEMPERATURE_OF_LLM
)

# ------------------ Embedding Config ------------------
OLLAMA_EMBED_URL = (
    "http://localhost:11434/api/embeddings"  # Ollama embeddings API endpoint
)
OLLAMA_EMBED_MODEL = "nomic-embed-text"  # Embedding model for vector search

# ------------------ Memory Config ------------------
CHROMA_PERSIST_DIR = "./chroma_db_think"
CHROMA_COLLECTION_NAME = "aiot_memory"
THRESHOLD = 0.85  # Similarity threshold for duplicate check

# ------------------ Tools Config ------------------
# This is defined but not yet used in the orchestrator. Ready for future use.
GEMINI_VISION_LLM = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash", temperature=TEMPERATURE_OF_LLM
)
