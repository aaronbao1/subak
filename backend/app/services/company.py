"""The company record: who the loaded dataset is about.

Resolution, per field: environment variable (BACKEND_COMPANY_ID / BACKEND_COMPANY_NAME) > the
`company_profile` row (written by the Northstar seed or `datagen/load_backend.py`) > the Northstar
default. The environment is read per call, so a server started with different variables needs no
code change, and tests can pass `env` explicitly.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.db.models import CompanyProfile

DEFAULT_ID = "northstar"
DEFAULT_NAME = "Northstar Software"
ENV_ID = "BACKEND_COMPANY_ID"
ENV_NAME = "BACKEND_COMPANY_NAME"


def get_profile(session: Session) -> CompanyProfile | None:
    return session.get(CompanyProfile, 1)


def set_profile(session: Session, *, company_id: str, name: str, is_simulated: bool, clock: Clock,
                as_of: date | None = None) -> CompanyProfile:
    """Create or replace the single company row (flushes; the caller commits)."""
    company_id, name = (company_id or "").strip(), (name or "").strip()
    if not company_id or not name:
        raise ValueError("company id and name are required")
    row = get_profile(session)
    if row is None:
        row = CompanyProfile(slot=1)
        session.add(row)
    row.company_id, row.name, row.as_of, row.is_simulated = company_id, name, as_of, bool(is_simulated)
    row.updated_at = clock.now()
    session.flush()
    return row


def resolve(session: Session, env: Mapping[str, str] | None = None) -> dict[str, Any]:
    """{id, name, as_of, is_simulated, source, detail}. `source` names where the name came from:
    "env", "db" or "default" (no row stored: the Northstar default, said so in `detail`)."""
    env = os.environ if env is None else env
    row = get_profile(session)
    env_id, env_name = (env.get(ENV_ID) or "").strip(), (env.get(ENV_NAME) or "").strip()
    company_id = env_id or (row.company_id if row else DEFAULT_ID)
    name = env_name or (row.name if row else DEFAULT_NAME)
    source = "env" if env_name else "db" if row else "default"
    if source == "env":
        detail = f"name from {ENV_NAME}" + (f"; id from {ENV_ID}" if env_id else "")
    elif source == "db":
        detail = "company_profile record written by the data loader" + (f"; id from {ENV_ID}" if env_id else "")
    else:
        detail = "no company_profile record in this database; showing the Northstar default"
    return {
        "id": company_id,
        "name": name,
        "as_of": row.as_of if row else None,
        # Unknown provenance (no row) is reported as simulated, never as real.
        "is_simulated": row.is_simulated if row else True,
        "source": source,
        "detail": detail,
    }
