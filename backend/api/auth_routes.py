"""LinkedIn sign-in, optional sharing consent, and user-triggered publishing."""

import secrets
import time
import hashlib
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from core.config import settings
from models.schemas import JobShareRequest
from services.job_store import job_store
from services.linkedin_auth import (
    LOGIN_SCOPES,
    SHARE_SCOPE,
    authorization_url,
    complete_oauth,
    publish_post,
)

router = APIRouter()
STATE_COOKIE = "linkedin_oauth_state"
SESSION_COOKIE = "semantic_job_session"
STATE_MAX_AGE = 600
SESSION_MAX_AGE = 60 * 60 * 24 * 14


def _serializer(salt: str) -> URLSafeTimedSerializer:
    if not settings.app_secret_key:
        raise HTTPException(status_code=503, detail="APP_SECRET_KEY is not configured.")
    return URLSafeTimedSerializer(
        settings.app_secret_key,
        salt=salt,
        signer_kwargs={"digest_method": hashlib.sha256},
    )


def _cookie_options() -> dict:
    return {
        "httponly": True,
        "secure": settings.auth_cookie_secure,
        "samesite": settings.auth_cookie_samesite,
        "path": "/",
    }


def _read_session(request: Request) -> dict | None:
    encoded = request.cookies.get(SESSION_COOKIE)
    if not encoded:
        return None
    try:
        session_id = _serializer("linkedin-session").loads(encoded, max_age=SESSION_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return None
    return job_store.get_session(session_id)


def _read_state(request: Request, returned_state: str) -> dict:
    signed_state = request.cookies.get(STATE_COOKIE)
    if not signed_state:
        raise HTTPException(status_code=400, detail="LinkedIn OAuth state is missing.")
    try:
        payload = _serializer("linkedin-oauth-state").loads(signed_state, max_age=STATE_MAX_AGE)
    except (BadSignature, SignatureExpired) as error:
        raise HTTPException(status_code=400, detail="LinkedIn OAuth state is invalid or expired.") from error
    if not secrets.compare_digest(payload["state"], returned_state):
        raise HTTPException(status_code=400, detail="LinkedIn OAuth state did not match.")
    return payload


def _authorization_redirect(purpose: str, session_id: str | None = None) -> RedirectResponse:
    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    scopes = LOGIN_SCOPES + ([SHARE_SCOPE] if purpose == "share" else [])
    response = RedirectResponse(authorization_url(state, nonce, scopes), status_code=302)
    payload = {"state": state, "nonce": nonce, "purpose": purpose, "session_id": session_id}
    response.set_cookie(
        STATE_COOKIE,
        _serializer("linkedin-oauth-state").dumps(payload),
        max_age=STATE_MAX_AGE,
        **_cookie_options(),
    )
    return response


@router.get("/auth/linkedin/login")
async def linkedin_login():
    return _authorization_redirect("login")


@router.get("/auth/linkedin/share-permission")
async def linkedin_share_permission(request: Request):
    session = _read_session(request)
    if not session or session["expires_at"] <= time.time():
        raise HTTPException(status_code=401, detail="Sign in with LinkedIn before enabling sharing.")
    return _authorization_redirect("share", session["session_id"])


@router.get("/auth/linkedin/callback")
async def linkedin_callback(
    request: Request,
    code: str | None = Query(default=None),
    state: str = Query(...),
    error: str | None = Query(default=None),
):
    context = _read_state(request, state)
    if error:
        raise HTTPException(status_code=400, detail=f"LinkedIn authorization failed: {error}")
    if not code:
        raise HTTPException(status_code=400, detail="LinkedIn did not return an authorization code.")

    try:
        auth_result = await complete_oauth(code, context["nonce"])
    except httpx.HTTPStatusError as error:
        raise HTTPException(
            status_code=502,
            detail=f"LinkedIn OAuth returned HTTP {error.response.status_code}.",
        ) from error
    except httpx.RequestError as error:
        raise HTTPException(status_code=502, detail="Could not reach LinkedIn OAuth.") from error
    if context["purpose"] == "share":
        existing = _read_session(request)
        if (
            not existing
            or existing["session_id"] != context["session_id"]
            or existing["member_id"] != auth_result["member_id"]
        ):
            raise HTTPException(status_code=400, detail="LinkedIn sharing consent did not match the signed-in member.")
        session_id = existing["session_id"]
    else:
        session_id = secrets.token_urlsafe(32)

    granted_scopes = auth_result["scopes"]
    if context["purpose"] == "share" and SHARE_SCOPE not in granted_scopes:
        granted_scopes.append(SHARE_SCOPE)
    job_store.save_session(
        session_id=session_id,
        member_id=auth_result["member_id"],
        profile=auth_result["profile"],
        access_token=auth_result["access_token"],
        expires_at=auth_result["expires_at"],
        scopes=granted_scopes,
    )

    response = RedirectResponse(
        f"{settings.frontend_url}/?{urlencode({'linkedin': 'connected'})}",
        status_code=302,
    )
    response.delete_cookie(STATE_COOKIE, **_cookie_options())
    response.set_cookie(
        SESSION_COOKIE,
        _serializer("linkedin-session").dumps(session_id),
        max_age=SESSION_MAX_AGE,
        **_cookie_options(),
    )
    return response


@router.get("/auth/me")
async def linkedin_me(request: Request):
    session = _read_session(request)
    if not session or session["expires_at"] <= time.time():
        raise HTTPException(status_code=401, detail="Not signed in.")
    return {"profile": session["profile"], "sharing_enabled": SHARE_SCOPE in session["scopes"]}


@router.post("/linkedin/share")
async def share_job_match(payload: JobShareRequest, request: Request):
    session = _read_session(request)
    if not session or session["expires_at"] <= time.time():
        raise HTTPException(status_code=401, detail="Sign in with LinkedIn to share a job.")
    if SHARE_SCOPE not in session["scopes"]:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "sharing_permission_required",
                "message": "Enable LinkedIn sharing permission before publishing.",
            },
        )
    try:
        post_id = await publish_post(
            session["access_token"],
            session["member_id"],
            payload.commentary,
        )
    except httpx.HTTPStatusError as error:
        raise HTTPException(
            status_code=502,
            detail=f"LinkedIn rejected the post (HTTP {error.response.status_code}).",
        ) from error
    except httpx.RequestError as error:
        raise HTTPException(status_code=502, detail="Could not reach LinkedIn to publish the post.") from error
    return {"status": "published", "post_id": post_id}
