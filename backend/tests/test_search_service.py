import numpy as np

from models.schemas import Job
from services.search_service import search_jobs


def test_search_jobs_ranks_live_jobs_with_in_memory_faiss_index():
    jobs = [
        Job(job_id="first", title="Python Engineer", company="A", source="LinkedIn"),
        Job(job_id="second", title="Data Analyst", company="B", source="LinkedIn"),
    ]
    embeddings = np.array([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32)

    results = search_jobs(
        query_vec=np.array([1.0, 0.0], dtype=np.float32),
        jobs=jobs,
        embeddings=embeddings,
        top_k=2,
    )

    assert results[0] == (jobs[0], 1.0)
    assert results[1] == (jobs[1], 0.0)
