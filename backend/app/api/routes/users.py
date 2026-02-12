from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db import models
from app.db.session import get_db
from app.schemas.auth import UserOut
from app.schemas.workspace import WorkspaceOut

router = APIRouter(tags=["users"])


@router.get("/me")
def me(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    memberships = (
        db.query(models.Workspace)
        .join(models.WorkspaceMember, models.WorkspaceMember.workspace_id == models.Workspace.id)
        .filter(models.WorkspaceMember.user_id == current_user.id)
        .order_by(models.Workspace.created_at.asc())
        .all()
    )
    return {
        "user": UserOut.model_validate(current_user),
        "workspaces": [WorkspaceOut.model_validate(w) for w in memberships],
    }
