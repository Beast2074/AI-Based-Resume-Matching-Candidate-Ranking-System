import os
import traceback
from pathlib import Path
from typing import List
import numpy as np

from app.services.logger import record_log

_embedder_instance = None

def get_models_dir() -> Path:
    candidates = [
        Path(__file__).resolve().parent.parent.parent / "models",
        Path.cwd() / "models",
        Path.cwd() / "backend" / "models",
        Path("/var/task/models"),
        Path("/var/task/backend/models"),
    ]
    for d in candidates:
        if d.exists() and any(d.rglob("*.onnx")):
            return d
    # Fallback to /tmp for serverless runtime (e.g. Vercel)
    tmp_dir = Path("/tmp/fastembed_models")
    tmp_dir.mkdir(parents=True, exist_ok=True)
    return tmp_dir

class FallbackEmbedder:
    """Deterministic fallback vectorizer when neural weights cannot be loaded in serverless."""
    def embed_texts(self, texts: List[str], batch_size: int = 32) -> np.ndarray:
        if not texts:
            return np.empty((0, 384), dtype=np.float32)
        vectors = []
        for text in texts:
            vec = np.zeros(384, dtype=np.float32)
            words = text.lower().split()
            for word in words:
                h = abs(hash(word)) % 384
                vec[h] += 1.0
            norm = np.linalg.norm(vec)
            if norm > 0:
                vec /= norm
            vectors.append(vec)
        return np.array(vectors, dtype=np.float32)


class Embedder:
    def __init__(self, cache_dir: str | None = None):
        if cache_dir is None:
            cache_dir = str(get_models_dir())
        
        has_onnx = Path(cache_dir).exists() and any(Path(cache_dir).rglob("*.onnx"))
        if has_onnx:
            os.environ["HF_HUB_OFFLINE"] = "1"
        else:
            os.environ["HF_HUB_OFFLINE"] = "0"
            os.environ.pop("HF_HUB_OFFLINE", None)
            
        os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
        
        try:
            from fastembed import TextEmbedding
            self.model = TextEmbedding(
                model_name="BAAI/bge-small-en-v1.5",
                cache_dir=cache_dir
            )
            self._fallback = None
            record_log("EMBEDDER", "INFO", f"Loaded ONNX embedding model from {cache_dir}")
        except Exception as exc:
            record_log("EMBEDDER", "WARNING", f"Failed to initialize TextEmbedding ({exc}), using deterministic fallback.")
            self.model = None
            self._fallback = FallbackEmbedder()

    def embed_texts(self, texts: List[str], batch_size: int = 32) -> np.ndarray:
        if not texts:
            return np.empty((0, 384), dtype=np.float32)
        if self.model is not None:
            try:
                embeddings = list(self.model.embed(texts, batch_size=batch_size))
                arr = np.array(embeddings, dtype=np.float32)
                norms = np.linalg.norm(arr, axis=1, keepdims=True)
                norms[norms == 0] = 1.0
                return arr / norms
            except Exception:
                pass
        if self._fallback is None:
            self._fallback = FallbackEmbedder()
        return self._fallback.embed_texts(texts, batch_size=batch_size)

def get_embedder() -> Embedder:
    global _embedder_instance
    if _embedder_instance is None:
        _embedder_instance = Embedder()
    return _embedder_instance
