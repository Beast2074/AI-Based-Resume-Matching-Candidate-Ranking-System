import os
from pathlib import Path
from typing import List
import numpy as np

# Enforce offline model loading
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

_embedder_instance = None

def get_models_dir() -> Path:
    # Points to backend/models
    return Path(__file__).resolve().parent.parent.parent / "models"

class Embedder:
    def __init__(self, cache_dir: str | None = None):
        if cache_dir is None:
            cache_dir = str(get_models_dir())
        from fastembed import TextEmbedding
        self.model = TextEmbedding(
            model_name="BAAI/bge-small-en-v1.5",
            cache_dir=cache_dir
        )

    def embed_texts(self, texts: List[str], batch_size: int = 32) -> np.ndarray:
        if not texts:
            return np.empty((0, 384), dtype=np.float32)
        embeddings = list(self.model.embed(texts, batch_size=batch_size))
        arr = np.array(embeddings, dtype=np.float32)
        # L2-normalise so dot product equals cosine similarity
        norms = np.linalg.norm(arr, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return arr / norms

def get_embedder() -> Embedder:
    global _embedder_instance
    if _embedder_instance is None:
        _embedder_instance = Embedder()
    return _embedder_instance
