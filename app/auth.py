"""Identity and access.

Two credential classes share one bearer scheme:

- The workspace key (env ``AUTH_TOKEN``) - the administrator credential.
  Full read/write on every route; resolves to the bootstrap user.
- Member tokens - issued per username via ``POST /api/members/login``
  (username-only: members have no passwords by design). Stored as SHA-256
  hex on the user row; each login replaces the previous token. Members are
  view-only: every write route raises 403 for them.

External identity (Google Sign-In etc.) later replaces the issuance step
in ``members_login``; tokens, roles and scoping stay as they are.
"""

import hashlib
import logging
import secrets
from dataclasses import dataclass

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from sqlalchemy import func, select
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


@dataclass
class Principal:
    """Authenticated caller: the scoped user row plus its role."""

    user: User
    role: str  # "admin" | "member"

    @property
    def id(self) -> int:
        return self.user.id

    @property
    def username(self) -> str:
        return self.user.username


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> Principal:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    presented = credentials.credentials
    if secrets.compare_digest(presented.encode(), _settings.auth_token.encode()):
        user = db.scalar(select(User).where(User.username == BOOTSTRAP_USERNAME))
        if user is None:
            # init_db() creates it at startup; absent means startup never ran.
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or missing token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return Principal(user=user, role="admin")

    member = db.scalar(select(User).where(User.token_hash == _sha256(presented)))
    if member is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return Principal(user=member, role="member")


def require_admin(principal: Principal) -> None:
    """Write routes call this; members are view-only by design."""
    if principal.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Members have view-only access",
        )


router = APIRouter(prefix="/api", tags=["identity"])


class MemberLoginRequest(BaseModel):
    username: str


class TokenResponse(BaseModel):
    token: str
    role: str
    username: str


class MeResponse(BaseModel):
    id: int
    username: str
    role: str


class AdminVerifyRequest(BaseModel):
    token: str


@router.post("/members/login", response_model=TokenResponse)
def members_login(payload: MemberLoginRequest, db: Session = Depends(get_db)):
    username = payload.username.strip().lower()
    user = db.scalar(select(User).where(func.lower(User.username) == username))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Unknown member"
        )
    if user.username == BOOTSTRAP_USERNAME:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The administrator signs in with the workspace key",
        )
    token = secrets.token_urlsafe(32)
    user.token_hash = _sha256(token)
    db.commit()
    return TokenResponse(token=token, role="member", username=user.username)


@router.get("/members/me", response_model=MeResponse)
def members_me(principal: Principal = Depends(get_current_user)):
    return MeResponse(id=principal.id, username=principal.username, role=principal.role)


@router.post("/admin/verify", response_model=MeResponse)
def admin_verify(payload: AdminVerifyRequest, db: Session = Depends(get_db)):
    if not secrets.compare_digest(
        payload.token.encode(), _settings.auth_token.encode()
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid workspace key",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = db.scalar(select(User).where(User.username == BOOTSTRAP_USERNAME))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not initialised"
        )
    return MeResponse(id=user.id, username=user.username, role="admin")
