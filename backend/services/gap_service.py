"""
Skill gap analysis.

Given a list of resume skills and a job description,
returns which skills matched and which are missing.

This is what makes the app genuinely useful — not just
showing a similarity score, but explaining WHY a job matched
and what the candidate needs to learn.
"""
import re
from services.pdf_service import SKILL_KEYWORDS


def analyze_gap(
    resume_skills: list[str],
    job_description: str,
) -> tuple[list[str], list[str]]:
    """
    Compare resume skills against skills mentioned in a job description.

    Returns:
        matched_skills: Skills in both resume and job description
        missing_skills: Skills in job description but NOT in resume
    """
    job_skills = _extract_skills_from_text(job_description)
    resume_set = set(resume_skills)

    matched = sorted(job_skills & resume_set)
    missing = sorted(job_skills - resume_set)

    return matched, missing


def _extract_skills_from_text(text: str) -> set[str]:
    """Extract skills from a job description text."""
    text_lower = text.lower()
    found = set()
    for skill in SKILL_KEYWORDS:
        pattern = r"\b" + re.escape(skill) + r"\b"
        if re.search(pattern, text_lower):
            found.add(skill)
    return found


def score_to_label(score: float) -> str:
    """Human-readable label for a cosine similarity score."""
    if score >= 0.80:
        return "Excellent match"
    elif score >= 0.65:
        return "Strong match"
    elif score >= 0.50:
        return "Good match"
    elif score >= 0.35:
        return "Partial match"
    else:
        return "Weak match"
