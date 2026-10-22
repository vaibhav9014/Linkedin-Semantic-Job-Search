import logging
import httpx
import pytest

from models.schemas import Job
from services import job_fetcher
from services import job_store as job_store_module
from services.job_store import JobStore
from services.job_fetcher import (
    JSearchConfigurationError,
    JobFetcher,
    dedupe_jobs,
    map_job,
)
from api.routes import derive_search_queries


def configure_jsearch(monkeypatch):
    monkeypatch.setattr(
        job_fetcher.settings,
        "jsearch_base_url",
        "https://jsearch.p.rapidapi.com/search-v2",
    )
    monkeypatch.setattr(
        job_fetcher.settings,
        "jsearch_auth_header",
        "x-rapidapi-key",
    )
    monkeypatch.setattr(job_fetcher.settings, "jsearch_api_key", "test-key")


class MemoryCache:
    def __init__(self):
        self.values = {}
        self.lookups = []

    def get_cached_search(self, cache_key, ttl_seconds):
        self.lookups.append((cache_key, ttl_seconds))
        return self.values.get(cache_key)

    def cache_search(self, cache_key, response):
        self.values[cache_key] = response


def listing(
    title="Data Scientist",
    company="Example Inc.",
    city="New York",
    publisher="LinkedIn",
    description="<p>Build&nbsp;<b>machine learning</b> systems.</p><script>discard()</script>",
):
    return {
        "job_title": title,
        "employer_name": company,
        "job_city": city,
        "job_state": "NY",
        "job_country": "USA",
        "job_description": description,
        "job_min_salary": 100000,
        "job_max_salary": 150000,
        "job_salary_currency": "USD",
        "job_salary_period": "YEAR",
        "job_apply_link": "https://jobs.example/apply",
        "job_posted_at_datetime_utc": "2026-10-20T12:00:00Z",
        "job_publisher": publisher,
        "job_required_experience": {"required_experience_in_months": 24},
    }


@pytest.mark.asyncio
async def test_fetch_retries_rate_limit_and_server_errors_and_filters_publisher(monkeypatch):
    configure_jsearch(monkeypatch)
    statuses = iter([429, 503, 200])
    sleeps = []

    async def no_sleep(seconds):
        sleeps.append(seconds)

    monkeypatch.setattr(job_fetcher.asyncio, "sleep", no_sleep)

    def handler(request):
        assert request.headers["x-rapidapi-key"] == "test-key"
        assert request.url.path == "/search-v2"
        assert request.url.params["num_pages"] == "1"
        assert "page" not in request.url.params
        assert request.url.params["country"] == job_fetcher.settings.jsearch_country
        assert request.url.params["date_posted"] == "all"
        assert "job_publisher" in request.url.params["fields"]
        status = next(statuses)
        if status != 200:
            return httpx.Response(status, headers={"Retry-After": "0"})
        return httpx.Response(
            200,
            json={"data": {
                "jobs": [listing(), listing(title="Designer", publisher="Indeed")],
                "cursor": "next-page",
            }},
        )

    cache = MemoryCache()
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        fetcher = JobFetcher(client=client, max_retries=2, store=cache)
        jobs = await fetcher.fetch("data scientist")
        cached_jobs = await fetcher.fetch("data scientist")

    assert len(sleeps) == 2
    assert len(jobs) == 1
    assert len(cached_jobs) == 1
    assert len(cache.lookups) == 2
    assert cache.lookups[0][1] == 86400
    assert jobs[0].source == "LinkedIn"
    assert jobs[0].description == "Build machine learning systems."
    assert jobs[0].experience_level == "Mid level"
    assert jobs[0].salary == "USD 100000–150000 YEAR"


def test_job_mapping_rejects_non_web_apply_urls():
    job = map_job(listing() | {"job_apply_link": "javascript:alert(1)"})

    assert job is not None
    assert job.apply_url is None


def test_dedupe_uses_normalized_title_company_and_city():
    first = Job(
        job_id="1",
        title="Senior Data Scientist",
        company="Example, Inc.",
        location="New York, NY, USA",
        description="First",
        source="LinkedIn",
    )
    duplicate = Job(
        job_id="2",
        title=" SENIOR   Data Scientist ",
        company="Example Inc",
        location="new york, NY",
        description="Second",
        source="LinkedIn",
    )
    other_city = duplicate.model_copy(update={"job_id": "3", "location": "Boston, MA"})

    result = dedupe_jobs([first, duplicate, other_city])

    assert [job.job_id for job in result] == ["1", "3"]


def test_resume_queries_use_role_location_and_linkedin_suffix(monkeypatch):
    monkeypatch.setattr(
        job_fetcher.settings,
        "jsearch_default_location",
        "India",
    )
    queries = derive_search_queries(
        "Senior Data Scientist\nLocation: Bengaluru, India\nData Engineer",
        ["python", "sql"],
    )

    assert queries == [
        "Senior Data Scientist jobs in Bengaluru, India via linkedin",
        "Data Engineer jobs in Bengaluru, India via linkedin",
    ]


def test_resume_queries_default_to_configured_india_location(monkeypatch):
    monkeypatch.setattr(
        job_fetcher.settings,
        "jsearch_default_location",
        "India",
    )
    queries = derive_search_queries(
        "Experienced professional in Python, SQL and analytics. " * 4,
        ["python", "sql", "pandas"],
    )

    assert queries
    assert all(" jobs in India via linkedin" in query for query in queries)


@pytest.mark.parametrize("status_code", [401, 403, 404])
@pytest.mark.asyncio
async def test_configuration_errors_are_logged_and_not_retried(
    status_code,
    caplog,
    monkeypatch,
):
    configure_jsearch(monkeypatch)
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(
            status_code,
            json={"message": "JSearch configuration rejected the request"},
        )

    cache = MemoryCache()
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        fetcher = JobFetcher(client=client, max_retries=2, store=cache)
        monkeypatch.setattr(job_fetcher.settings, "jsearch_api_key", "test-key")
        with caplog.at_level(logging.ERROR):
            with pytest.raises(
                JSearchConfigurationError,
                match=f"HTTP {status_code}",
            ):
                await fetcher.fetch("data scientist jobs in Boston via linkedin")

    assert len(requests) == 1
    assert f"status={status_code}" in caplog.text
    assert "/search-v2" in caplog.text
    assert "JSearch configuration rejected" in caplog.text


@pytest.mark.asyncio
async def test_fetch_for_queries_caps_requests_at_three_and_forwards_cursor(monkeypatch):
    configure_jsearch(monkeypatch)
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={"data": {"jobs": [], "cursor": "next"}})

    cache = MemoryCache()
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        fetcher = JobFetcher(client=client, store=cache)
        await fetcher.fetch_for_queries(["one", "two", "three", "four"])
        _, next_cursor = await fetcher.fetch_page("cursor origin")
        await fetcher.fetch("next query", cursor=next_cursor)

    assert len(requests) == 5
    assert [request.url.params["query"] for request in requests[:3]] == [
        "one",
        "two",
        "three",
    ]
    assert requests[3].url.params["query"] == "cursor origin"
    assert requests[4].url.params["cursor"] == "next"
    assert all(request.url.params["num_pages"] == "1" for request in requests)


@pytest.mark.asyncio
async def test_fetch_requires_explicit_environment_configuration(monkeypatch):
    monkeypatch.setattr(job_fetcher.settings, "jsearch_base_url", "")
    monkeypatch.setattr(job_fetcher.settings, "jsearch_auth_header", "")
    monkeypatch.setattr(job_fetcher.settings, "jsearch_api_key", "")

    with pytest.raises(RuntimeError, match="JSEARCH_BASE_URL"):
        await JobFetcher(store=MemoryCache()).fetch("data analyst jobs in India via linkedin")


def test_search_cache_expires_after_24_hours(tmp_path, monkeypatch):
    now = [1_000_000.0]
    monkeypatch.setattr(job_store_module.time, "time", lambda: now[0])
    store = JobStore(tmp_path / "search-cache.sqlite3")
    store.cache_search("query-key", {"data": {"jobs": [], "cursor": "next"}})

    assert store.get_cached_search("query-key", 86400) == {
        "data": {"jobs": [], "cursor": "next"}
    }
    now[0] += 86400
    assert store.get_cached_search("query-key", 86400) is None
