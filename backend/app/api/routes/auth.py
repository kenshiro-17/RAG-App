from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import (
    create_access_token,
    create_refresh_token,
    get_password_hash,
    hash_token,
    verify_password,
)
from app.db import models
from app.db.session import get_db
from app.schemas.auth import LoginRequest, RefreshRequest, RegisterRequest, TokenResponse

router = APIRouter(prefix="/auth", tags=["auth"])


def _issue_tokens(db: Session, user_id: str) -> TokenResponse:
    access_token = create_access_token(subject=user_id)
    refresh_token, expires_at = create_refresh_token(subject=user_id)

    refresh_row = models.RefreshToken(
        user_id=user_id,
        token_hash=hash_token(refresh_token),
        expires_at=expires_at,
        revoked=False,
    )
    db.add(refresh_row)
    db.commit()
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/register", response_model=TokenResponse)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> TokenResponse:
    existing = db.query(models.User).filter(models.User.email == payload.email.lower()).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user = models.User(email=payload.email.lower(), password_hash=get_password_hash(payload.password))
    db.add(user)
    db.flush()

    workspace = models.Workspace(
        name=payload.workspace_name or f"{payload.email.split('@')[0]}'s Workspace",
        created_by=user.id,
    )
    db.add(workspace)
    db.flush()

    membership = models.WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role=models.WorkspaceRole.OWNER)
    db.add(membership)
    db.commit()

    return _issue_tokens(db, user.id)


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.query(models.User).filter(models.User.email == payload.email.lower()).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    return _issue_tokens(db, user.id)


@router.post("/refresh", response_model=TokenResponse)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)) -> TokenResponse:
    token_hash = hash_token(payload.refresh_token)
    token_row = db.query(models.RefreshToken).filter(models.RefreshToken.token_hash == token_hash).first()

    if not token_row or token_row.revoked:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
    if token_row.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token expired")

    token_row.revoked = True
    db.add(token_row)
    db.commit()

    return _issue_tokens(db, token_row.user_id)
