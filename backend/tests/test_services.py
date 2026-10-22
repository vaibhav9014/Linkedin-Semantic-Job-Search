"""
Tests for the core services.
Run: pytest backend/tests/ -v
"""
import pytest
import numpy as np
from unittest.mock import patch, MagicMock


# ─── PDF Service Tests ─────────────────────────────────────────────────────────

from services.pdf_service import extract_skills, _clean_text, validate_pdf_size


def test_extract_skills_basic():
    text = "Experienced in Python and PyTorch. Worked with FastAPI and Docker."
    skills = extract_skills(text)
    assert "python" in skills
    assert "pytorch" in skills
    assert "fastapi" in skills
    assert "docker" in skills


def test_extract_skills_no_false_positives():
    # "r" should not match standalone when surrounded by letters
    text = "Worked on orders and architecture at our company."
    skills = extract_skills(text)
    assert "r" not in skills


def test_extract_skills_case_insensitive():
    text = "PYTHON and PYTORCH experience required."
    skills = extract_skills(text)
    assert "python" in skills
    assert "pytorch" in skills


def test_clean_text_removes_excessive_newlines():
    text = "Hello\n\n\n\n\nWorld"
    cleaned = _clean_text(text)
    assert "\n\n\n" not in cleaned
    assert "Hello" in cleaned
    assert "World" in cleaned


def test_validate_pdf_size_passes():
    small_pdf = b"x" * (1 * 1024 * 1024)  # 1MB
    validate_pdf_size(small_pdf, max_mb=5)  # Should not raise


def test_validate_pdf_size_fails():
    big_pdf = b"x" * (6 * 1024 * 1024)  # 6MB
    with pytest.raises(ValueError, match="max allowed"):
        validate_pdf_size(big_pdf, max_mb=5)


# ─── Gap Service Tests ─────────────────────────────────────────────────────────

from services.gap_service import analyze_gap, score_to_label


def test_analyze_gap_finds_match():
    resume_skills = ["python", "pytorch", "fastapi"]
    job_desc = "We need Python and PyTorch experience. Docker is a plus."
    matched, missing = analyze_gap(resume_skills, job_desc)
    assert "python" in matched
    assert "pytorch" in matched
    assert "docker" in missing


def test_analyze_gap_all_missing():
    resume_skills = ["tableau", "sql"]
    job_desc = "Looking for Python and PyTorch engineers."
    matched, missing = analyze_gap(resume_skills, job_desc)
    assert len(matched) == 0
    assert "python" in missing
    assert "pytorch" in missing


def test_score_labels():
    assert score_to_label(0.85) == "Excellent match"
    assert score_to_label(0.70) == "Strong match"
    assert score_to_label(0.55) == "Good match"
    assert score_to_label(0.40) == "Partial match"
    assert score_to_label(0.20) == "Weak match"


# ─── Embedding Service Tests ───────────────────────────────────────────────────

from services.embedding_service import EmbeddingService


def test_embedder_singleton():
    e1 = EmbeddingService()
    e2 = EmbeddingService()
    assert e1 is e2


def test_embed_requires_load():
    embedder = EmbeddingService()
    embedder._model = None  # Force unloaded state
    with pytest.raises(RuntimeError, match="not loaded"):
        embedder.embed("test text")


def test_embed_returns_normalized_vector():
    """Integration test — requires model download (~80MB first run)."""
    pytest.importorskip("sentence_transformers")
    embedder = EmbeddingService()
    embedder.load()
    vec = embedder.embed("Python machine learning engineer")
    assert vec.shape == (384,)
    norm = np.linalg.norm(vec)
    assert abs(norm - 1.0) < 1e-5, f"Vector not normalized: norm={norm}"
