from uuid import UUID

import secrets

from fastapi import Header, HTTPException

from .config import get_settings

settings = get_settings()


def require_installation_id(
    x_installation_id: str = Header(..., alias="X-Installation-ID"),
    x_app_token: str | None = Header(None, alias="X-App-Token"),
) -> str:
    if settings.app_env != "development":
        if not settings.app_access_token or not x_app_token:
            raise HTTPException(status_code=401, detail="missing app access token")
        if not secrets.compare_digest(x_app_token, settings.app_access_token):
            raise HTTPException(status_code=401, detail="invalid app access token")
    try:
        UUID(x_installation_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="invalid installation id") from exc
    return x_installation_id
