"""Shared route dependencies: clock and id factory from app state."""

from __future__ import annotations

from fastapi import Request

from app.core.clock import Clock, IdFactory


def get_clock(request: Request) -> Clock:
    return request.app.state.clock


def get_ids(request: Request) -> IdFactory:
    return request.app.state.id_factory


def get_forecast_provider(request: Request):
    return request.app.state.forecast_provider
