from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import BOOTSTRAP_USERNAME, Principal, get_current_user, require_admin
from app.db import get_db
from app.models import Tag, Task, User
from app.schemas import MemberCreate, MemberRead

router = APIRouter(
    prefix="/api/members",
    tags=["members"],
)

_INT4_MAX = 2_147_483_647


@router.get("", response_model=list[MemberRead])
def list_members(db: Session = Depends(get_db)):
    # Public on purpose: the app's identity picker lists usernames before any
    # login exists. Writes below still require the caller and admin role.
    return db.scalars(select(User).order_by(User.username)).all()


@router.post("", response_model=MemberRead, status_code=status.HTTP_201_CREATED)
def create_member(
    payload: MemberCreate,
    principal: Principal = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_admin(principal)
    # Rows are stored lowercase; the lower() compare also covers any legacy
    # mixed-case rows so duplicates are caught case-insensitively.
    exists = db.scalar(
        select(func.count()).select_from(User).where(func.lower(User.username) == payload.username)
    )
    if exists:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Username already taken"
        )
    member = User(username=payload.username, password_hash="")
    db.add(member)
    db.commit()
    db.refresh(member)
    return member


@router.delete("/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_member(
    member_id: int = Path(ge=1, le=_INT4_MAX),
    principal: Principal = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_admin(principal)
    member = db.get(User, member_id)
    if member is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Member not found"
        )
    if member.username == BOOTSTRAP_USERNAME:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The workspace owner cannot be removed",
        )
    # Members are username-only today, but legacy rows can own data; deleting
    # them would trip FKs (500). Block with a clear 409 instead.
    owns_tasks = db.scalar(
        select(func.count()).select_from(Task).where(Task.user_id == member.id)
    )
    owns_tags = db.scalar(
        select(func.count()).select_from(Tag).where(Tag.user_id == member.id)
    )
    if owns_tasks or owns_tags:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Member still has tasks or tags",
        )
    db.delete(member)
    db.commit()


