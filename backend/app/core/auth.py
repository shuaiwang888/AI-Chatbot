"""Small, dependency-free bearer-style access control for the single-user app."""
from __future__ import annotations

import secrets

from fastapi import Header, HTTPException, status

from app.config import settings


def _require_configured_token(value: str, header: str, supplied: str | None) -> None:
    if not value:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Access control is not configured on this deployment.",
        )
    if not supplied or not secrets.compare_digest(supplied, value):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Valid {header} required.",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def require_access_token(x_api_token: str | None = Header(default=None)) -> None:
    """Protect user-facing data and write endpoints.

    The setting is deliberately fail-closed: a public deployment missing its
    secret returns 503 instead of silently becoming an open knowledge base.
    """
    if not settings.auth_required:
        return
    _require_configured_token(
        settings.api_access_token.get_secret_value(), "X-API-Token", x_api_token
    )


async def require_admin_token(x_admin_token: str | None = Header(default=None)) -> None:
    """Protect operational actions independently from normal application access."""
    if not settings.auth_required:
        return
    _require_configured_token(
        settings.admin_access_token.get_secret_value(), "X-Admin-Token", x_admin_token
    )
