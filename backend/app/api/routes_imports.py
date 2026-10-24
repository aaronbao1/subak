"""Spend imports (multipart upload) and coverage."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.deps import get_clock, get_ids
from app.core.actors import FINANCE_ROLES, Actor, require_role
from app.core.clock import Clock, IdFactory
from app.core.errors import DomainError, error_body
from app.db.session import get_session
from app.schemas.imports import CoverageReport, ImportResult
from app.services import coverage as coverage_svc
from app.services import imports as svc

router = APIRouter(prefix="/api", tags=["imports"])


@router.post("/imports", response_model=ImportResult, status_code=201)
async def create_import(
    file: UploadFile = File(...),
    source_kind: str = Form(...),
    source_label: str | None = Form(default=None),
    source_account: str | None = Form(default=None),
    value_kind_default: str | None = Form(default=None),
    session: Session = Depends(get_session),
    actor: Actor = Depends(require_role("importer", *FINANCE_ROLES)),
    clock: Clock = Depends(get_clock),
    ids: IdFactory = Depends(get_ids),
):
    raw = await file.read(svc.MAX_IMPORT_BYTES + 1)
    if len(raw) > svc.MAX_IMPORT_BYTES:
        raise DomainError("file_too_large", 413, f"import files are limited to {svc.MAX_IMPORT_BYTES} bytes")
    outcome = svc.import_and_commit(
        session,
        source_kind=source_kind,
        raw=raw,
        filename=file.filename,
        actor_id=actor.id,
        clock=clock,
        ids=ids,
        source_label=source_label,
        source_account=source_account,
        value_kind_default=value_kind_default,
    )
    result = ImportResult.from_batch(outcome.batch)
    if result.status == "failed":
        return JSONResponse(
            status_code=422,
            content=error_body("import_failed", "import rejected; nothing was added",
                               {"batch": result.model_dump(mode="json")}),
        )
    if result.status == "duplicate":
        return JSONResponse(status_code=200, content=result.model_dump(mode="json"))
    return result


@router.get("/imports", response_model=list[ImportResult])
def list_imports(session: Session = Depends(get_session)):
    return [ImportResult.from_batch(b) for b in svc.list_batches(session)]


@router.get("/imports/{batch_id}", response_model=ImportResult)
def get_import(batch_id: str, session: Session = Depends(get_session)):
    return ImportResult.from_batch(svc.get_batch(session, batch_id))


@router.get("/coverage", response_model=CoverageReport)
def get_coverage(
    period: str | None = Query(default=None),
    session: Session = Depends(get_session),
    clock: Clock = Depends(get_clock),
):
    now = clock.now()
    p = coverage_svc.resolve_period(session, period, now)
    return coverage_svc.coverage_report(session, p, now)
