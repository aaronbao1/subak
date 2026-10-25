"""Canonical immutable forecasting REST endpoints."""
from typing import Any, Literal

from fastapi import APIRouter, Body, Header, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from .persistence import ImmutableConflict

router = APIRouter(prefix='/api', tags=['forecasting'])
Scope = Literal['company', 'team', 'person', 'shared']


def public_job(job):
    return {k: v for k, v in job.items() if k not in ('lease_token', 'lease_owner')}


def service(request: Request):
    return request.app.state.forecast_service


def call(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except KeyError as exc:
        raise HTTPException(404, detail='Forecast record not found') from exc
    except ImmutableConflict as exc:
        raise HTTPException(409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, detail=str(exc)) from exc


class ScenarioRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    drivers: list[dict[str, Any]] = Field(max_length=100)
    scope_type: Scope | None = None
    scope_id: str | None = None


@router.get('/forecast-views')
def views(request: Request, scope_type: Scope | None = None, scope_id: str | None = None, run_id: str | None = None):
    return call(service(request).views, scope_type, scope_id, run_id)


@router.post('/forecast-refreshes', status_code=202)
def refresh(request: Request, idempotency_key: str = Header(alias='Idempotency-Key')):
    return public_job(call(service(request).refresh, idempotency_key))


@router.get('/forecast-refreshes/{job_id}')
def refresh_status(request: Request, job_id: str):
    job = call(service(request).store.get_job, job_id)
    # Claim tokens are worker capabilities, not public job status.
    return public_job(job)


@router.get('/forecast-runs/{run_id}/explanation')
def explanation(request: Request, run_id: str, scope_type: Scope | None = None, scope_id: str | None = None, driver_id: str | None = None):
    return call(service(request).explain, run_id, scope_type, scope_id, driver_id)


@router.post('/forecast-runs/{run_id}/scenarios', status_code=201)
def scenario(request: Request, run_id: str, payload: ScenarioRequest):
    return call(service(request).scenario, run_id, payload.drivers, payload.scope_type, payload.scope_id)


@router.get('/forecast-scenarios/{scenario_id}')
def get_scenario(request: Request, scenario_id: str):
    return call(service(request).get_scenario, scenario_id)


@router.get('/forecast-evidence')
def evidence(request: Request):
    return call(service(request).evidence)


@router.post('/forecast-evidence', status_code=201)
def ingest_evidence(request: Request, envelope: dict[str, Any] = Body()):
    return call(service(request).ingest_evidence, envelope)
