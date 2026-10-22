import re
import logging

import fitz
import httpx
from fastapi import APIRouter, UploadFile, File, HTTPException, Form
from starlette.concurrency import run_in_threadpool

from core.config import settings
from models.schemas import MatchResponse, JobMatch, EmbedResponse, HealthResponse
from services.embedding_service import embedder
from services.pdf_service import extract_text, extract_skills, validate_pdf_size
from services.gap_service import analyze_gap
from services.job_fetcher import JSearchConfigurationError, JobFetcher
from services.job_store import job_store
from services.search_service import search_jobs

router = APIRouter()
logger = logging.getLogger(__name__)
ROLE_WORDS = {
    "engineer", "developer", "scientist", "analyst", "architect", "manager",
    "researcher", "consultant", "designer", "administrator", "specialist",
    "programmer", "lead", "director",
}
LOCATION_PATTERN = re.compile(
    r"\b(?:location|based\s+in|residing\s+in|address)\s*[:\-]\s*([^\n|]{2,60})",
    re.IGNORECASE,
)


@router.get("/health", response_model=HealthResponse)
async def health():
    job_store.count_jobs()
    return HealthResponse(
        status="ok",
        model_loaded=embedder.is_loaded,
        job_store_ready=True,
    )


def derive_search_queries(resume_text: str, skills: list[str]) -> list[str]:
    titles = []
    for line in resume_text.splitlines()[:25]:
        words = line.strip().split()
        if 1 < len(words) <= 8 and ROLE_WORDS.intersection(word.lower().strip(",|/") for word in words):
            title = " ".join(words)
            if title.casefold() not in {value.casefold() for value in titles}:
                titles.append(title)
        if len(titles) == 2:
            break

    if not titles:
        if {"pytorch", "tensorflow", "scikit-learn", "sklearn", "nlp"} & set(skills):
            titles.append("Machine Learning Engineer")
        elif {"sql", "tableau", "looker", "pandas"} & set(skills):
            titles.append("Data Analyst")
        else:
            titles.append("Software Engineer")

    location_match = LOCATION_PATTERN.search(resume_text)
    location = (
        re.sub(r"\s+", " ", location_match.group(1)).strip(" ,.;")
        if location_match
        else settings.jsearch_default_location
    )
    roles = []
    for title in titles[:3]:
        if title.casefold() not in {role.casefold() for role in roles}:
            roles.append(title)
    return [f"{role} jobs in {location} via linkedin" for role in roles[:3]]


@router.post("/match", response_model=MatchResponse)
async def match_resume(
    file: UploadFile = File(..., description="PDF resume, max 5MB"),
    top_k: int = Form(default=10, ge=1, le=10),
):
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(400, "Only PDF files are accepted.")

    pdf_bytes = await file.read()
    try:
        validate_pdf_size(pdf_bytes, max_mb=settings.max_pdf_size_mb)
    except ValueError as e:
        raise HTTPException(413, str(e))

    try:
        resume_text = extract_text(pdf_bytes, max_pages=settings.max_pages)
    except (fitz.FileDataError, ValueError) as error:
        raise HTTPException(422, "The uploaded file is not a readable PDF.") from error
    if len(resume_text.strip()) < 100:
        raise HTTPException(422, "Could not extract enough text from the PDF. Is it a scanned image?")

    resume_skills = extract_skills(resume_text)
    queries = derive_search_queries(resume_text, resume_skills)
    logger.info("Searching JSearch with queries: %s", queries)
    try:
        jobs = await JobFetcher().fetch_for_queries(queries)
    except httpx.HTTPStatusError as error:
        raise HTTPException(
            502,
            f"JSearch returned HTTP {error.response.status_code}. Please try again later.",
        ) from error
    except httpx.RequestError as error:
        raise HTTPException(502, "Could not reach JSearch. Please try again later.") from error
    except JSearchConfigurationError as error:
        raise HTTPException(502, str(error)) from error
    except RuntimeError as error:
        raise HTTPException(503, str(error)) from error

    logger.info(
        "JSearch returned %s LinkedIn-published jobs across %s queries",
        len(jobs),
        len(queries),
    )
    job_store.save_jobs(jobs)
    if jobs:
        texts = [f"{job.title} at {job.company}. {job.description}" for job in jobs]
        embeddings = await run_in_threadpool(embedder.embed_batch, texts)
        resume_vector = await run_in_threadpool(embedder.embed, resume_text)
        ranked = search_jobs(resume_vector, jobs, embeddings, top_k)
    else:
        ranked = []

    job_matches = []
    for job, score in ranked:
        matched, missing = analyze_gap(resume_skills, job.description)
        job_matches.append(JobMatch(
            job_id=job.job_id,
            title=job.title,
            company=job.company,
            location=job.location,
            description_snippet=job.description[:300],
            salary=job.salary,
            apply_url=job.apply_url,
            posted_at=job.posted_at,
            source=job.source,
            experience_level=job.experience_level,
            score=score,
            matched_skills=matched,
            missing_skills=missing,
        ))

    return MatchResponse(
        resume_text_preview=resume_text[:200],
        resume_skills=resume_skills,
        search_queries=queries,
        matches=job_matches,
        total_jobs_searched=len(jobs),
    )


@router.post("/embed", response_model=EmbedResponse)
async def embed_text(text: str = Form(...)):
    """
    Debug endpoint: embed any text string and see the vector.
    Useful for testing the embedding service in isolation.
    """
    vec = await run_in_threadpool(embedder.embed, text)
    return EmbedResponse(
        text_preview=text[:100],
        embedding_dim=len(vec),
        embedding=vec.tolist(),
    )
