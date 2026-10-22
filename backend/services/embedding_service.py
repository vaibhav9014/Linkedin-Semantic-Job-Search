"""
Embedding service using Sentence-BERT.

Model: all-MiniLM-L6-v2
- 384-dimensional embeddings
- Very fast (~14k sentences/sec on CPU)
- Great quality for semantic similarity tasks
- 80MB download, cached by HuggingFace after first run

Usage:
    embedder = EmbeddingService()
    vec = embedder.embed("machine learning engineer with pytorch experience")
"""
import numpy as np
from sentence_transformers import SentenceTransformer
from core.config import settings


class EmbeddingService:
    _instance = None  # singleton — model loads once at startup

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._model = None
        return cls._instance

    def load(self) -> None:
        """Load model into memory. Call once at app startup."""
        if self._model is None:
            print(f"Loading embedding model: {settings.embedding_model}")
            self._model = SentenceTransformer(settings.embedding_model)
            print("Model loaded.")

    @property
    def is_loaded(self) -> bool:
        return self._model is not None

    def embed(self, text: str) -> np.ndarray:
        """
        Embed a single text string.
        Returns normalized float32 array of shape (384,).
        Normalization is important — FAISS IndexFlatIP with 
        normalized vectors gives cosine similarity.
        """
        if not self.is_loaded:
            raise RuntimeError("Model not loaded. Call .load() first.")
        vec = self._model.encode(text, normalize_embeddings=True)
        return vec.astype(np.float32)

    def embed_batch(self, texts: list[str], batch_size: int = 64) -> np.ndarray:
        """
        Embed multiple texts efficiently.
        Returns array of shape (N, 384).
        Used by the index builder script.
        """
        if not self.is_loaded:
            raise RuntimeError("Model not loaded. Call .load() first.")
        vecs = self._model.encode(
            texts,
            batch_size=batch_size,
            normalize_embeddings=True,
            show_progress_bar=True,
        )
        return vecs.astype(np.float32)


# Module-level singleton
embedder = EmbeddingService()
