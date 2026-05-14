from __future__ import annotations

from typing import Any

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings

# ── Scheme ────────────────────────────────────────────────────────────────────
bearer = HTTPBearer()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _decode(token: str) -> dict[str, Any]:
    """Decode and verify a JWT.  Raises HTTP 401 on any JWT error."""
    try:
        return jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired token: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


# ── Dependencies ──────────────────────────────────────────────────────────────

async def get_current_user(
    creds: HTTPAuthorizationCredentials = Depends(bearer),
) -> dict[str, Any]:
    """Return the decoded JWT payload for any authenticated caller."""
    return _decode(creds.credentials)


async def require_admin(
    creds: HTTPAuthorizationCredentials = Depends(bearer),
) -> dict[str, Any]:
    """Return the decoded JWT payload, enforcing role == 'admin'.

    * HTTP 401 — token missing / invalid / expired
    * HTTP 403 — valid token but role != 'admin'
    """
    payload = _decode(creds.credentials)
    if payload.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required.",
        )
    return payload
