"""Fetch and normalize LinkedIn-published listings through the JSearch API."""

import asyncio
import hashlib
import json
import logging
import re
import unicodedata
from datetime import datetime
from email.utils import parsedate_to_datetime
from html import unescape
from html.parser import HTMLParser
from urllib.parse import urlsplit

import httpx

from core.config import settings
from models.schemas import Job
from services.job_store import job_store

logger = logging.getLogger(__name__)
JOB_FIELDS = ",".join((
    "job_publisher",
    "job_title",
    "employer_name",
    "job_city",
    "job_state",
    "job_country",
    "job_description",
    "job_min_salary",
    "job_max_salary",
    "job_salary_currency",
    "job_salary_period",
    "job_apply_link",
    "job_posted_at_datetime_utc",
    "job_required_experience",
))


class JSearchConfigurationError(RuntimeError):
    """The configured JSearch subscription or endpoint rejected the request."""


def _job_records(payload: dict) -> list[dict]:
    data = payload.get("data")
    if isinstance(data, dict):
        records = data.get("jobs")
    else:
        records = data
    if not isinstance(records, list):
        raise RuntimeError("JSearch returned an unexpected response payload.")
    if not all(isinstance(result, dict) for result in records):
        raise RuntimeError("JSearch returned an invalid job record.")
    return records


def _response_cursor(payload: dict) -> str | None:
    data = payload.get("data")
    cursor = data.get("cursor") if isinstance(data, dict) else payload.get("cursor")
    return str(cursor) if cursor else None


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skip_depth = 0

    def handle_data(self, data: str) -> None:
        if not self.skip_depth:
            self.parts.append(data)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in {"script", "style"}:
            self.skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style"} and self.skip_depth:
            self.skip_depth -= 1


def clean_html(value: str | None) -> str:
    if not value:
        return ""
    parser = _TextExtractor()
    parser.feed(str(value))
    return re.sub(r"\s+", " ", unescape(" ".join(parser.parts))).strip()


def _normalize(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()


def dedupe_key(title: str, company: str, city: str) -> str:
    return "|".join(_normalize(part) for part in (title, company, city))


def dedupe_jobs(jobs: list[Job]) -> list[Job]:
    unique: dict[str, Job] = {}
    for job in jobs:
        city = job.location.split(",")[0].strip()
        unique.setdefault(dedupe_key(job.title, job.company, city), job)
    return list(unique.values())


def _posted_at(value: str | None) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed


def _salary(result: dict) -> str | None:
    minimum = result.get("job_min_salary")
    maximum = result.get("job_max_salary")
    if minimum is None and maximum is None:
        return None
    currency = result.get("job_salary_currency") or ""
    period = result.get("job_salary_period") or ""

    def format_amount(value: object) -> str:
        try:
            return f"{float(value):g}"
        except (TypeError, ValueError):
            return str(value)

    if minimum is not None and maximum is not None:
        amount = f"{format_amount(minimum)}–{format_amount(maximum)}"
    else:
        amount = format_amount(minimum if minimum is not None else maximum)
    return " ".join(part for part in (currency, amount, period) if part)


def _experience_level(value: dict | None) -> str | None:
    if not isinstance(value, dict) or not value:
        return None
    level = value.get("experience_level")
    if level:
        return str(level)
    months = value.get("required_experience_in_months")
    if months is None:
        return None
    try:
        months = int(months)
    except (TypeError, ValueError):
        return str(months)
    if months <= 12:
        return "Entry level"
    if months <= 36:
        return "Mid level"
    return "Senior level"


def _safe_apply_url(value: str | None) -> str | None:
    if not value:
        return None
    url = str(value).strip()
    try:
        parsed = urlsplit(url)
    except ValueError:
        return None
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return None
    return url


def map_job(result: dict) -> Job | None:
    if str(result.get("job_publisher", "")).strip().casefold() != "linkedin":
        return None

    title = clean_html(result.get("job_title"))
    company = clean_html(result.get("employer_name"))
    if not title or not company:
        return None
    city = clean_html(result.get("job_city"))
    location_parts = [city, clean_html(result.get("job_state")), clean_html(result.get("job_country"))]
    location = ", ".join(part for part in location_parts if part)
    description = clean_html(result.get("job_description"))
    key = dedupe_key(title, company, city)
    return Job(
        job_id=hashlib.sha256(key.encode()).hexdigest()[:24],
        title=title,
        company=company,
        location=location,
        description=description,
        salary=_salary(result),
        apply_url=_safe_apply_url(result.get("job_apply_link")),
        posted_at=_posted_at(result.get("job_posted_at_datetime_utc")),
        source="LinkedIn",
        experience_level=_experience_level(result.get("job_required_experience")),
    )


class JobFetcher:
    def __init__(
        self,
        client: httpx.AsyncClient | None = None,
        max_retries: int | None = None,
        store=job_store,
    ):
        self.client = client
        self.max_retries = max_retries if max_retries is not None else settings.jsearch_max_retries
        self.store = store

    async def fetch(self, query: str, cursor: str | None = None) -> list[Job]:
        jobs, _ = await self.fetch_page(query, cursor)
        return jobs

    async def fetch_page(
        self,
        query: str,
        cursor: str | None = None,
    ) -> tuple[list[Job], str | None]:
        missing_settings = [
            name
            for name, value in (
                ("JSEARCH_BASE_URL", settings.jsearch_base_url),
                ("JSEARCH_AUTH_HEADER", settings.jsearch_auth_header),
                ("JSEARCH_API_KEY", settings.jsearch_api_key),
            )
            if not value
        ]
        if missing_settings:
            raise RuntimeError(
                f"Missing JSearch configuration: {', '.join(missing_settings)}."
            )

        cache_params = {
            "query": query,
            "country": settings.jsearch_country,
            "date_posted": settings.jsearch_date_posted,
            "num_pages": "1",
            "fields": JOB_FIELDS,
        }
        if cursor:
            cache_params["cursor"] = cursor
        cache_key = hashlib.sha256(
            json.dumps(
                {"url": settings.jsearch_base_url, **cache_params},
                sort_keys=True,
            ).encode()
        ).hexdigest()
        cached_response = self.store.get_cached_search(
            cache_key,
            settings.jsearch_cache_ttl_seconds,
        )
        if cached_response is not None:
            records = _job_records(cached_response)
            jobs = [
                job
                for result in records
                if (job := map_job(result)) is not None
            ]
            return jobs, _response_cursor(cached_response)

        parsed_url = urlsplit(settings.jsearch_base_url)
        if parsed_url.scheme not in {"http", "https"} or not parsed_url.hostname:
            raise RuntimeError("JSEARCH_BASE_URL must be an absolute HTTP(S) URL.")
        headers = {
            settings.jsearch_auth_header: settings.jsearch_api_key,
            "x-rapidapi-host": parsed_url.hostname,
            "accept": "application/json",
        }
        params = {
            **cache_params,
        }
        if self.client is not None:
            response = await self._get(self.client, headers, params)
        else:
            async with httpx.AsyncClient(timeout=20) as client:
                response = await self._get(client, headers, params)
        if response.status_code in {401, 403, 404}:
            body = response.text.replace(settings.jsearch_api_key, "[REDACTED]")
            request_url = str(response.request.url) if response.request else settings.jsearch_base_url
            logger.error(
                "JSearch configuration error status=%s url=%s body=%s",
                response.status_code,
                request_url,
                body[:2000],
            )
            raise JSearchConfigurationError(
                f"JSearch configuration error (HTTP {response.status_code}). "
                "Check JSEARCH_BASE_URL, subscription, and RapidAPI credentials."
            )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise RuntimeError("JSearch returned an unexpected response payload.")
        records = _job_records(payload)
        self.store.cache_search(cache_key, payload)
        jobs = [job for result in records if (job := map_job(result)) is not None]
        return jobs, _response_cursor(payload)

    async def fetch_for_queries(self, queries: list[str]) -> list[Job]:
        jobs: list[Job] = []
        for query in queries[:3]:
            jobs.extend(await self.fetch(query))
        return dedupe_jobs(jobs)

    async def _get(
        self,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        params: dict[str, str],
    ) -> httpx.Response:
        for attempt in range(self.max_retries + 1):
            response = await client.get(
                settings.jsearch_base_url,
                headers=headers,
                params=params,
            )
            if response.status_code in {401, 403, 404}:
                return response
            if response.status_code != 429 and response.status_code < 500:
                return response
            if attempt == self.max_retries:
                return response
            await asyncio.sleep(self._retry_delay(response, attempt))
        raise RuntimeError("JSearch retry loop ended unexpectedly.")

    @staticmethod
    def _retry_delay(response: httpx.Response, attempt: int) -> float:
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            try:
                return min(max(float(retry_after), 0), 10)
            except ValueError:
                try:
                    retry_at = parsedate_to_datetime(retry_after)
                    now = datetime.now(retry_at.tzinfo)
                    return min(max((retry_at - now).total_seconds(), 0), 10)
                except (TypeError, ValueError, OverflowError):
                    pass
        return min(0.5 * (2**attempt), 8)
