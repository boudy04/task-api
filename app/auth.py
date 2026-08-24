"""Static bearer-token auth.

Accounts are deferred - see git tag api-v2-auth-deferred for the full
JWT/register/login design this temporarily replaced. A single admin token
(env AUTH_TOKEN) maps to the bootstrap user; every route still scopes all
reads/writes through that User row, so future accounts slot back in without
touching the routers.
"""

import logging
import secrets

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.db import get_db
from app.models import User

_settings = Settings()

logger = logging.getLogger(__name__)

_bearer = HTTPBearer(auto_error=False)

# The internal owner all API access is scoped to while accounts are deferred.
BOOTSTRAP_USERNAME = "boudy04"

# Mirrors the old bootstrap-password warning: loud default credentials.
if _settings.auth_token == "dev-token":
    logger.warning(
        "AUTH_TOKEN is left at its default - the workspace is exposed; "
        "set a real value before deploying"
    )


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    # compare_digest over bytes: constant-time and safe for any input.
    if not secrets.compare_digest(
        credentials.credentials.encode(), _settings.auth_token.encode()
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = db.scalar(select(User).where(User.username == BOOTSTRAP_USERNAME))
    if user is None:
        # init_db() creates it at startup; absent means startup never ran.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing token",
        )
    return user
