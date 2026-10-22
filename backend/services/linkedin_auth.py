"""LinkedIn OpenID Connect token exchange and ID token validation."""

import time

import httpx
import jwt
from fastapi import HTTPException

from core.config import settings

OIDC_DISCOVERY_URL = "https://www.linkedin.com/oauth/.well-known/openid-configuration"
LOGIN_SCOPES = ["openid", "profile", "email"]
SHARE_SCOPE = "w_member_social"


def authorization_url(state: str, nonce: str, scopes: list[str]) -> str:
    if not settings.linkedin_client_id or not settings.linkedin_redirect_uri:
        raise HTTPException(status_code=503, detail="LinkedIn OAuth is not configured.")
    from urllib.parse import urlencode

    return "https://www.linkedin.com/oauth/v2/authorization?" + urlencode({
        "response_type": "code",
        "client_id": settings.linkedin_client_id,
        "redirect_uri": settings.linkedin_redirect_uri,
        "scope": " ".join(scopes),
        "state": state,
        "nonce": nonce,
    })


async def complete_oauth(code: str, expected_nonce: str) -> dict:
    if not settings.linkedin_client_id or not settings.linkedin_client_secret:
        raise HTTPException(status_code=503, detail="LinkedIn OAuth is not configured.")

    timeout = httpx.Timeout(15)
    async with httpx.AsyncClient(timeout=timeout) as client:
        discovery_response = await client.get(OIDC_DISCOVERY_URL)
        discovery_response.raise_for_status()
        discovery = discovery_response.json()

        token_response = await client.post(
            discovery["token_endpoint"],
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": settings.linkedin_redirect_uri,
                "client_id": settings.linkedin_client_id,
                "client_secret": settings.linkedin_client_secret,
            },
        )
        token_response.raise_for_status()
        token_data = token_response.json()
        access_token = token_data.get("access_token")
        id_token = token_data.get("id_token")
        if not access_token or not id_token:
            raise HTTPException(status_code=502, detail="LinkedIn did not return required tokens.")

        try:
            jwks_response = await client.get(discovery["jwks_uri"])
            jwks_response.raise_for_status()
            token_header = jwt.get_unverified_header(id_token)
            key_set = jwt.PyJWKSet.from_dict(jwks_response.json())
            signing_key = next(
                (key for key in key_set.keys if key.key_id == token_header.get("kid")),
                None,
            )
            if signing_key is None:
                raise jwt.PyJWKError("No JWKS key matched the ID token key ID.")
            claims = jwt.decode(
                id_token,
                signing_key.key,
                algorithms=["RS256"],
                audience=settings.linkedin_client_id,
                issuer=discovery["issuer"],
                options={"require": ["iss", "aud", "exp", "iat", "sub", "nonce"]},
            )
        except jwt.PyJWTError as error:
            raise HTTPException(status_code=400, detail="LinkedIn ID token validation failed.") from error
        if claims.get("nonce") != expected_nonce:
            raise HTTPException(status_code=400, detail="LinkedIn ID token nonce did not match.")

        profile_response = await client.get(
            discovery["userinfo_endpoint"],
            headers={"Authorization": f"Bearer {access_token}"},
        )
        profile_response.raise_for_status()
        profile = profile_response.json()

    if profile.get("sub") != claims.get("sub"):
        raise HTTPException(status_code=400, detail="LinkedIn profile did not match the authenticated member.")

    scopes = str(token_data.get("scope", "")).split()
    return {
        "access_token": access_token,
        "profile": profile,
        "member_id": claims["sub"],
        "expires_at": time.time() + int(token_data.get("expires_in", 3600)),
        "scopes": scopes,
    }


async def publish_post(access_token: str, member_id: str, commentary: str) -> str | None:
    payload = {
        "author": f"urn:li:person:{member_id}",
        "commentary": commentary,
        "visibility": "PUBLIC",
        "distribution": {
            "feedDistribution": "MAIN_FEED",
            "targetEntities": [],
            "thirdPartyDistributionChannels": [],
        },
        "lifecycleState": "PUBLISHED",
        "isReshareDisabledByAuthor": False,
    }
    headers = {
        "Authorization": f"Bearer {access_token}",
        "LinkedIn-Version": settings.linkedin_api_version,
        "X-Restli-Protocol-Version": "2.0.0",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.post(
            "https://api.linkedin.com/rest/posts",
            headers=headers,
            json=payload,
        )
    response.raise_for_status()
    return response.headers.get("x-restli-id")
