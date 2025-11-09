# THINK_module/memory.py
import chromadb
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime
import logging
import requests
import os
import shutil
from config import OLLAMA_EMBED_URL, OLLAMA_EMBED_MODEL, THRESHOLD, CHROMA_PERSIST_DIR
import json

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("sadaf.memory")


def get_ollama_embedding(text: str) -> List[float]:
    """Fetch embedding from local Ollama."""
    try:
        # Note: Ollama API for embeddings uses 'prompt' for /api/embeddings
        # but 'input' for /api/embed. Your /api/embeddings endpoint is correct.
        resp = requests.post(
            OLLAMA_EMBED_URL,
            json={"model": OLLAMA_EMBED_MODEL, "prompt": text},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        # The /api/embeddings endpoint wraps the embedding in a key
        if "embedding" in data:
            return data["embedding"]
        # Fallback for /api/embed
        elif "embeddings" in data:
            return data["embeddings"]

        logger.error(f"Ollama embedding response format unknown: {data.keys()}")
        raise ValueError("Ollama embedding response format unknown")

    except Exception as e:
        logger.error(f"Ollama embedding error: {e}")
        logger.warning("Using naive fallback embedding!")
        vec = [float((hash(text) % 1000) / 1000.0)] * 768  # nomic-embed-text size
        return vec


class ChromaStore:
    """Handles persistent fact storage and retrieval with ChromaDB."""

    def __init__(
        self, collection_name: str, persist_directory: str = "./chroma_db_think"
    ):
        self.collection_name = collection_name
        self.persist_directory = persist_directory

        try:
            # Try to use persistent client (may panic if DB files corrupted / incompatible)
            self.client = chromadb.PersistentClient(path=self.persist_directory)
            logger.info(
                "ChromaStore initialized. Collection '%s' at %s",
                self.collection_name,
                self.persist_directory,
            )
        except Exception as e:
            # Catch Rust panic / binding errors and fallback to in-memory client
            logger.exception(
                "Chroma persistent client failed (falling back to in-memory). Error: %s",
                e,
            )
            # attempt to move the corrupted persist dir for investigation
            if os.path.exists(self.persist_directory):
                try:
                    bak = f"{self.persist_directory}.bak"
                    shutil.move(self.persist_directory, bak)
                    logger.warning("Backed up corrupted Chroma persist dir to %s", bak)
                except Exception:
                    logger.exception(
                        "Failed to backup Chroma persist dir %s", self.persist_directory
                    )
            # Fallback: in-memory Chroma client (no persistence)
            self.client = chromadb.Client()
            logger.warning("Using in-memory Chroma client (no persistence).")

        self.collection = self.client.get_or_create_collection(name=collection_name)
        logger.info(
            f"ChromaStore initialized. Collection '{collection_name}' at {persist_directory}"
        )

    def _is_duplicate(self, text: str, threshold: float = THRESHOLD) -> bool:
        """
        Check if a similar fact already exists in the collection.
        Uses semantic similarity via embeddings.
        """
        if self.collection.count() == 0:
            return False  # Nothing to be duplicate of

        try:
            emb = get_ollama_embedding(text)
            results = self.collection.query(
                query_embeddings=[emb],
                n_results=1,
            )

            if results and results["documents"] and results["distances"]:
                existing_doc = results["documents"][0][0]
                distance = results["distances"][0][0]

                # Chroma's 'distance' (like L2) is smaller for similar items.
                # Cosine distance is 1 - similarity.
                # Let's assume default L2/cosine distance where 0 is identical.
                # A threshold of 0.1 means "very similar".
                # Your THRESHOLD = 0.9 suggests 1 - distance.

                similarity = 1 - distance  # Assuming cosine distance

                if similarity >= threshold:
                    logger.info(
                        f"Skipped duplicate fact: '{text}' ~ '{existing_doc}' (sim={similarity:.3f})"
                    )
                    return True
            return False
        except Exception as e:
            logger.error(f"Duplicate check error: {e}")
            return False

    def add_document(self, text: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """Add a document with Ollama embeddings if not duplicate."""
        if self._is_duplicate(text):
            return "DUPLICATE_SKIPPED"

        doc_id = str(uuid.uuid4())
        safe_meta = None
        if metadata:
            safe_meta = {}
            for k, v in metadata.items():
                if isinstance(v, (str, int, float, bool)) or v is None:
                    safe_meta[k] = v
                else:
                    # Serialize dicts/lists/objects to JSON (fallback to str)
                    try:
                        safe_meta[k] = json.dumps(v, default=str)
                    except Exception:
                        safe_meta[k] = str(v)

        safe_meta["timestamp"] = datetime.now().isoformat()

        try:
            embedding = get_ollama_embedding(text)
            self.collection.add(
                documents=[text],
                metadatas=[safe_meta],
                embeddings=[embedding],
                ids=[doc_id],
            )
            logger.info(f"Stored doc {doc_id} in '{self.collection.name}'")
            return doc_id
        except Exception as e:
            logger.error(f"Chroma add_document error: {e}")
            raise

    def get_relevant_info(self, query: str, n_results: int = 5) -> str:
        """Retrieve relevant stored facts as a single string."""
        if self.collection.count() == 0:
            return "No information in memory."

        try:
            query_emb = get_ollama_embedding(query)
            results = self.collection.query(
                query_embeddings=[query_emb],
                n_results=n_results,
            )
            if results["documents"]:
                # Return as a bulleted list string
                return "\n".join(f"- {doc}" for doc in results["documents"][0])
            return "No relevant information found in memory."
        except Exception as e:
            logger.error(f"Chroma query error: {e}")
            return "Error querying memory."
