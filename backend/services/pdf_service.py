"""
PDF text extraction using PyMuPDF.
Handles multi-page resumes, cleans whitespace, 
and extracts a simple skill keyword list.
"""
import fitz  # PyMuPDF
import re
from pathlib import Path

# Common tech skills to look for in resumes
# Extend this list — recruiters scan for these
SKILL_KEYWORDS = {
    # Languages
    "python", "sql", "r", "scala", "java", "javascript", "typescript", "bash",
    # ML / DL
    "pytorch", "tensorflow", "keras", "scikit-learn", "sklearn", "xgboost",
    "lightgbm", "huggingface", "transformers", "bert", "gpt", "llm",
    "rag", "fine-tuning", "finetuning", "nlp", "computer vision", "yolo",
    "clip", "stable diffusion", "diffusion", "reinforcement learning",
    # MLOps
    "mlflow", "wandb", "kubeflow", "airflow", "prefect", "dvc",
    "docker", "kubernetes", "ci/cd", "github actions",
    # Data
    "pandas", "numpy", "spark", "pyspark", "kafka", "dbt", "bigquery",
    "snowflake", "databricks", "redshift", "postgresql", "mysql", "mongodb",
    # Cloud
    "gcp", "aws", "azure", "vertex ai", "sagemaker", "cloud run",
    # Serving
    "fastapi", "flask", "rest api", "grpc", "triton", "onnx",
    # Viz
    "tableau", "looker", "plotly", "matplotlib", "seaborn",
}


def extract_text(pdf_bytes: bytes, max_pages: int = 3) -> str:
    """Extract and clean text from PDF bytes."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pages_to_read = min(len(doc), max_pages)

    text_parts = []
    for page_num in range(pages_to_read):
        page = doc[page_num]
        text_parts.append(page.get_text("text"))

    raw_text = "\n".join(text_parts)
    return _clean_text(raw_text)


def _clean_text(text: str) -> str:
    """Remove excessive whitespace and non-printable chars."""
    # Collapse multiple blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Remove non-printable characters
    text = re.sub(r"[^\x20-\x7E\n]", " ", text)
    # Collapse multiple spaces
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


def extract_skills(text: str) -> list[str]:
    """
    Simple keyword matching against known skill list.
    Returns lowercased, deduplicated skills found in the text.
    
    In a future iteration, swap this for a NER model
    (e.g. GLiNER or a fine-tuned spaCy model).
    """
    text_lower = text.lower()
    found = set()
    for skill in SKILL_KEYWORDS:
        # Use word boundary check to avoid 'r' matching 'or', etc.
        pattern = r"\b" + re.escape(skill) + r"\b"
        if re.search(pattern, text_lower):
            found.add(skill)
    return sorted(found)


def validate_pdf_size(pdf_bytes: bytes, max_mb: int = 5) -> None:
    """Raise ValueError if PDF exceeds size limit."""
    size_mb = len(pdf_bytes) / (1024 * 1024)
    if size_mb > max_mb:
        raise ValueError(f"PDF is {size_mb:.1f}MB, max allowed is {max_mb}MB")
