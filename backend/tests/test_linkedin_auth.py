import json
import time

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from api import auth_routes
from api.main import app
from core.config import settings
from services import linkedin_auth
from services.job_store import job_store


def test_authorization_url_requests_oidc_login_scopes(monkeypatch):
    monkeypatch.setattr(settings, "linkedin_client_id", "client-id")
    monkeypatch.setattr(settings, "linkedin_redirect_uri", "http://localhost/callback")
    monkeypatch.setattr(settings, "app_secret_key", "test-only-secret")

    response = auth_routes._authorization_redirect("login")
    from urllib.parse import parse_qs, urlparse

    params = parse_qs(urlparse(response.headers["location"]).query)

    assert params["scope"] == ["openid profile email"]
    assert params["state"]
    assert params["nonce"]

    share_response = auth_routes._authorization_redirect("share", "session-id")
    share_params = parse_qs(urlparse(share_response.headers["location"]).query)
    assert share_params["scope"] == ["openid profile email w_member_social"]


def test_callback_rejects_mismatched_oauth_state(monkeypatch):
    monkeypatch.setattr(settings, "app_secret_key", "test-only-secret")
    signed_state = auth_routes._serializer("linkedin-oauth-state").dumps({
        "state": "expected-state",
        "nonce": "test-nonce",
        "purpose": "login",
        "session_id": None,
    })
    client = TestClient(app, follow_redirects=False)
    client.cookies.set(auth_routes.STATE_COOKIE, signed_state)

    response = client.get(
        "/api/auth/linkedin/callback",
        params={"code": "auth-code", "state": "attacker-state"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "LinkedIn OAuth state did not match."


@pytest.mark.asyncio
async def test_publish_post_uses_linkedin_rest_posts_api(monkeypatch):
    monkeypatch.setattr(settings, "linkedin_api_version", "202610")

    def handler(request):
        assert request.url == "https://api.linkedin.com/rest/posts"
        assert request.headers["Authorization"] == "Bearer member-access-token"
        assert request.headers["LinkedIn-Version"] == "202610"
        assert request.headers["X-Restli-Protocol-Version"] == "2.0.0"
        payload = json.loads(request.read())
        assert payload["author"] == "urn:li:person:member-42"
        assert payload["lifecycleState"] == "PUBLISHED"
        return httpx.Response(201, headers={"x-restli-id": "post-42"})

    original_client = httpx.AsyncClient
    monkeypatch.setattr(
        linkedin_auth.httpx,
        "AsyncClient",
        lambda **kwargs: original_client(
            transport=httpx.MockTransport(handler),
            **kwargs,
        ),
    )

    post_id = await linkedin_auth.publish_post(
        "member-access-token",
        "member-42",
        "A user-confirmed job post.",
    )

    assert post_id == "post-42"


@pytest.mark.asyncio
async def test_linkedin_callback_exchanges_code_and_creates_signed_session(
    monkeypatch,
    tmp_path,
):
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_jwk = jwt.algorithms.RSAAlgorithm.to_jwk(private_key.public_key(), as_dict=True)
    public_jwk.update({"kid": "test-key", "alg": "RS256", "use": "sig"})
    expected_nonce = "oauth-nonce"
    id_token = jwt.encode(
        {
            "iss": "https://www.linkedin.com/oauth",
            "aud": "client-id",
            "iat": int(time.time()),
            "exp": int(time.time()) + 300,
            "sub": "member-42",
            "nonce": expected_nonce,
        },
        private_key,
        algorithm="RS256",
        headers={"kid": "test-key"},
    )

    monkeypatch.setattr(settings, "linkedin_client_id", "client-id")
    monkeypatch.setattr(settings, "linkedin_client_secret", "client-secret")
    monkeypatch.setattr(settings, "linkedin_redirect_uri", "http://testserver/api/auth/linkedin/callback")
    monkeypatch.setattr(settings, "app_secret_key", "test-only-secret")
    monkeypatch.setattr(settings, "frontend_url", "http://frontend.test")
    monkeypatch.setattr(settings, "jobs_db_path", tmp_path / "test.sqlite3")
    monkeypatch.setattr(job_store, "path", tmp_path / "test.sqlite3")
    job_store.initialize()

    def handler(request):
        if request.url.path.endswith("/.well-known/openid-configuration"):
            return httpx.Response(
                200,
                json={
                    "issuer": "https://www.linkedin.com/oauth",
                    "token_endpoint": "https://www.linkedin.com/oauth/v2/accessToken",
                    "userinfo_endpoint": "https://api.linkedin.com/v2/userinfo",
                    "jwks_uri": "https://www.linkedin.com/oauth/openid/jwks",
                },
            )
        if request.url.path.endswith("/accessToken"):
            assert request.content.decode().find("code=auth-code") >= 0
            return httpx.Response(
                200,
                json={
                    "access_token": "server-side-access-token",
                    "id_token": id_token,
                    "expires_in": 3600,
                    "scope": "openid profile email",
                },
            )
        if request.url.path.endswith("/jwks"):
            return httpx.Response(200, json={"keys": [public_jwk]})
        if request.url.path.endswith("/userinfo"):
            assert request.headers["Authorization"] == "Bearer server-side-access-token"
            return httpx.Response(
                200,
                json={"sub": "member-42", "name": "Example Member", "email": "member@example.test"},
            )
        raise AssertionError(f"Unexpected LinkedIn request: {request.url}")

    original_client = httpx.AsyncClient
    monkeypatch.setattr(
        linkedin_auth.httpx,
        "AsyncClient",
        lambda **kwargs: original_client(
            transport=httpx.MockTransport(handler),
            **kwargs,
        ),
    )
    state = "random-csrf-state"
    signed_state = auth_routes._serializer("linkedin-oauth-state").dumps({
        "state": state,
        "nonce": expected_nonce,
        "purpose": "login",
        "session_id": None,
    })

    client = TestClient(app, follow_redirects=False)
    client.cookies.set(auth_routes.STATE_COOKIE, signed_state)
    response = client.get(
        "/api/auth/linkedin/callback",
        params={"code": "auth-code", "state": state},
    )

    assert response.status_code == 302
    assert response.headers["location"] == "http://frontend.test/?linkedin=connected"
    session_cookie = response.cookies[auth_routes.SESSION_COOKIE]
    assert response.headers["set-cookie"].lower().find("httponly") >= 0
    assert "server-side-access-token" not in session_cookie
    session_id = auth_routes._serializer("linkedin-session").loads(session_cookie)
    session = job_store.get_session(session_id)
    assert session["member_id"] == "member-42"
    assert session["access_token"] == "server-side-access-token"
    assert session["profile"]["name"] == "Example Member"
