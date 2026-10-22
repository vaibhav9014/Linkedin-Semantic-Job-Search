"""Build an in-memory exact FAISS index for each live job batch."""

import faiss
import numpy as np

from models.schemas import Job


def search_jobs(
    query_vec: np.ndarray,
    jobs: list[Job],
    embeddings: np.ndarray,
    top_k: int,
) -> list[tuple[Job, float]]:
    if not jobs:
        return []
    index = faiss.IndexFlatIP(embeddings.shape[1])
    index.add(np.ascontiguousarray(embeddings, dtype=np.float32))
    scores, indices = index.search(
        np.ascontiguousarray(query_vec.reshape(1, -1), dtype=np.float32),
        min(top_k, len(jobs)),
    )
    return [
        (jobs[index], float(round(score, 4)))
        for score, index in zip(scores[0], indices[0])
        if index >= 0
    ]
