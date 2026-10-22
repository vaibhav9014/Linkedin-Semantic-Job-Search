from pydantic_settings import BaseSettings
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]

class Settings(BaseSettings):
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dim: int = 384

    top_k: int = 10

    max_pdf_size_mb: int = 5
    max_pages: int = 3

    api_prefix: str = "/api"
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]
    frontend_url: str = "http://localhost:5173"
    jobs_db_path: Path = ROOT_DIR / "data" / "jobs.sqlite3"

    jsearch_base_url: str = ""
    jsearch_auth_header: str = ""
    jsearch_api_key: str = ""
    jsearch_max_retries: int = 2
    jsearch_country: str = "us"
    jsearch_date_posted: str = "all"
    jsearch_cache_ttl_seconds: int = 86400
    jsearch_default_location: str = "India"

    linkedin_client_id: str = ""
    linkedin_client_secret: str = ""
    linkedin_redirect_uri: str = "http://localhost:8000/api/auth/linkedin/callback"
    linkedin_api_version: str = "202610"

    app_secret_key: str = ""
    auth_cookie_secure: bool = False
    auth_cookie_samesite: str = "lax"

    model_config = {
        "env_file": ROOT_DIR / "backend" / ".env",
        "extra": "ignore",
    }

settings = Settings()
