from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import TokenError, decode_token
from app.db import models
from app.db.session import get_db

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


def _ensure_default_identity(db: Session) -> models.User:
    settings = get_settings()
    user = db.query(models.User).filter(models.User.email == settings.auth_default_email).first()
    if not user:
        try:
            user = models.User(
                email=settings.auth_default_email,
                password_hash="auth-disabled",
            )
            db.add(user)
            db.flush()
        except IntegrityError:
            db.rollback()
            user = db.query(models.User).filter(models.User.email == settings.auth_default_email).first()
            if not user:
                raise

    workspace = (
        db.query(models.Workspace)
        .join(models.WorkspaceMember, models.WorkspaceMember.workspace_id == models.Workspace.id)
        .filter(
            models.WorkspaceMember.user_id == user.id,
            models.Workspace.name == settings.auth_default_workspace_name,
        )
        .first()
    )
    if not workspace:
        workspace = models.Workspace(
            name=settings.auth_default_workspace_name,
            created_by=user.id,
        )
        db.add(workspace)
        db.flush()

    membership = (
        db.query(models.WorkspaceMember)
        .filter(
            models.WorkspaceMember.workspace_id == workspace.id,
            models.WorkspaceMember.user_id == user.id,
        )
        .first()
    )
    if not membership:
        membership = models.WorkspaceMember(
            workspace_id=workspace.id,
            user_id=user.id,
            role=models.WorkspaceRole.OWNER,
        )
        db.add(membership)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
    db.refresh(user)
    return user


def get_current_user(db: Session = Depends(get_db), token: str | None = Depends(oauth2_scheme)) -> models.User:
    settings = get_settings()

    if settings.auth_disabled and not token:
        return _ensure_default_identity(db)

    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing token")

    try:
        payload = decode_token(token)
    except TokenError as exc:
        if settings.auth_disabled:
            return _ensure_default_identity(db)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc

    if payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")

    user_id = payload.get("sub")
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    return user


def require_workspace_member(
    workspace_id: str,
    user: models.User,
    db: Session,
) -> models.WorkspaceMember:
    membership = (
        db.query(models.WorkspaceMember)
        .filter(models.WorkspaceMember.workspace_id == workspace_id, models.WorkspaceMember.user_id == user.id)
        .first()
    )
    if get_settings().auth_disabled:
        workspace = db.query(models.Workspace).filter(models.Workspace.id == workspace_id).first()
        if not workspace:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")
        if not membership:
            membership = models.WorkspaceMember(
                workspace_id=workspace_id,
                user_id=user.id,
                role=models.WorkspaceRole.MEMBER,
            )
            db.add(membership)
            db.commit()
            db.refresh(membership)
        return membership

    if not membership:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a member of this workspace")
    return membership
