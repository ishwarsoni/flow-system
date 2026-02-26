"""Domains router — expose domain definitions and per-domain quest panels."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional

from app.db.database import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.models.domain import Domain, DOMAIN_DEFINITIONS

router = APIRouter(prefix="/domains", tags=["domains"])


class DomainResponse(BaseModel):
    id:           int
    code:         str
    name:         str
    description:  Optional[str]
    stat_mapping: Optional[dict]
    color:        Optional[str]
    icon:         Optional[str]

    model_config = {"from_attributes": True}


@router.get(
    "",
    response_model=list[DomainResponse],
    summary="List all six power domains",
)
def list_domains(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[DomainResponse]:
    rows = db.query(Domain).order_by(Domain.id).all()
    if not rows:
        # Seed on-the-fly if somehow empty
        _seed_domains(db)
        rows = db.query(Domain).order_by(Domain.id).all()
    return [DomainResponse.model_validate(r) for r in rows]


@router.get(
    "/{code}",
    response_model=DomainResponse,
    summary="Get a single domain by code",
)
def get_domain(
    code: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> DomainResponse:
    row = db.query(Domain).filter(Domain.code == code.lower()).first()
    if not row:
        raise HTTPException(status_code=404, detail=f"Domain '{code}' not found.")
    return DomainResponse.model_validate(row)


def _seed_domains(db: Session) -> None:
    for d in DOMAIN_DEFINITIONS:
        exists = db.query(Domain).filter(Domain.code == d["code"]).first()
        if not exists:
            db.add(Domain(**d))
    db.commit()
