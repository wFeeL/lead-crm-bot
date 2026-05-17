from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import Settings, get_settings
from app.core.exceptions import PermissionDeniedError

bearer_scheme = HTTPBearer(auto_error=False)


def is_admin(telegram_id: int | None, settings: Settings | None = None) -> bool:
    if telegram_id is None:
        return False
    resolved_settings = settings or get_settings()
    return telegram_id in resolved_settings.admin_ids


def require_admin(telegram_id: int | None, settings: Settings | None = None) -> None:
    if not is_admin(telegram_id, settings):
        raise PermissionDeniedError("admin privileges required")


async def require_admin_api_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    settings: Settings = Depends(get_settings),
) -> None:
    if credentials is None or credentials.credentials != settings.admin_api_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid admin api token",
        )

