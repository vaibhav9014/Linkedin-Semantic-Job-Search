from datetime import datetime
from pydantic import BaseModel, Field, HttpUrl


class Job(BaseModel):
    job_id: str
    title: str
    company: str
    location: str = ""
    description: str = ""
    salary: str | None = None
    apply_url: str | None = None
    posted_at: datetime | None = None
    source: str
    experience_level: str | None = None


class JobMatch(BaseModel):
    job_id: str
    title: str
    company: str
    location: str = ""
    description_snippet: str
    salary: str | None = None
    apply_url: str | None = None
    posted_at: datetime | None = None
    source: str
    experience_level: str | None = None
    score: float = Field(..., ge=0.0, le=1.0, description="Cosine similarity score")
    matched_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)


class MatchResponse(BaseModel):
    resume_text_preview: str = Field(..., description="First 200 chars extracted from PDF")
    resume_skills: list[str]
    search_queries: list[str]
    matches: list[JobMatch]
    total_jobs_searched: int


class JobShareRequest(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    company: str = Field(min_length=1, max_length=300)
    apply_url: HttpUrl | None = None
    source: str = Field(min_length=1, max_length=100)
    commentary: str = Field(min_length=1, max_length=3000)


class EmbedResponse(BaseModel):
    text_preview: str
    embedding_dim: int
    embedding: list[float]


class HealthResponse(BaseModel):
    status: str
    model_loaded: bool
    job_store_ready: bool

    model_config = {"protected_namespaces": ()}
