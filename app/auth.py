import logging
import os
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from passlib.context import CryptContext
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from app.config import Settings
from app.db import get_db
from app.models import User

_settings = Settings()

logger = logging.getLogger(__name__)

if _settings.jwt_secret:
    _SECRET = _settings.jwt_secret
else:
    _SECRET = secrets.token_hex(32)
    logger.warning(
        "JWT_SECRET not set; generated a random per-boot secret "
        "(issued tokens stop working on restart). Set JWT_SECRET in production."
    )

if os.environ.get("AUTH_TOKEN"):
    logger.warning("AUTH_TOKEN is retired and ignored; use JWT auth (POST /api/auth/login)")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

_bearer = HTTPBearer(auto_error=False)

TOKEN_TTL = timedelta(days=30)


class Credentials(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=8)

    @field_validator("username", "password", mode="before")
    @classmethod
    def _strip(cls, v):
        return v.strip() if isinstance(v, str) else v


def create_token(user_id: int) -> str:
    payload = {
        "sub": str(user_id),
        "exp": datetime.now(timezone.utc) + TOKEN_TTL,
    }
    return jwt.encode(payload, _SECRET, algorithm="HS256")


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
    try:
        payload = jwt.decode(credentials.credentials, _SECRET, algorithms=["HS256"])
        user_id = int(payload["sub"])
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing token",
        )
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing token",
        )
    return user


def _issue_token(db: Session, username: str) -> str:
    user = db.scalars(select(User).where(User.username == username)).one()
    return create_token(user.id)


router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(payload: Credentials, db: Session = Depends(get_db)) -> dict:
    existing = db.scalar(select(User).where(User.username == payload.username))
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already taken",
        )
    user = User(
        username=payload.username,
        password_hash=pwd_context.hash(payload.password),
    )
    db.add(user)
    db.commit()
    return {"token": create_token(user.id)}


@router.post("/login")
def login(payload: Credentials, db: Session = Depends(get_db)) -> dict:
    user = db.scalar(select(User).where(User.username == payload.username))
    if user is None or not pwd_context.verify(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )
    return {"token": create_token(user.id)}
