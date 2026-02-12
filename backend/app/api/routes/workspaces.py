from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db import models
from app.db.session import get_db
from app.schemas.workspace import WorkspaceCreateRequest, WorkspaceOut

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


@router.get("", response_model=list[WorkspaceOut])
def list_workspaces(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[WorkspaceOut]:
    workspaces = (
        db.query(models.Workspace)
        .join(models.WorkspaceMember, models.WorkspaceMember.workspace_id == models.Workspace.id)
        .filter(models.WorkspaceMember.user_id == current_user.id)
        .order_by(models.Workspace.created_at.asc())
        .all()
    )
    return [WorkspaceOut.model_validate(workspace) for workspace in workspaces]


@router.post("", response_model=WorkspaceOut)
def create_workspace(
    payload: WorkspaceCreateRequest,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WorkspaceOut:
    workspace = models.Workspace(name=payload.name, created_by=current_user.id)
    db.add(workspace)
    db.flush()

    membership = models.WorkspaceMember(
        workspace_id=workspace.id,
        user_id=current_user.id,
        role=models.WorkspaceRole.OWNER,
    )
    db.add(membership)
    db.commit()
    db.refresh(workspace)
    return WorkspaceOut.model_validate(workspace)
