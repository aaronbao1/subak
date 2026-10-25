"""Read-only adapter from immutable ForecastViews to the legacy quarter contract."""
from __future__ import annotations
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP

from app.schemas.forecasts import ForecastResult, TeamProjection
from app.services.forecast_freshness import revision_from_snapshot


class EngineForecastProvider:
    name = 'engine'

    def __init__(self, service, session_factory):
        self.service, self.session_factory = service, session_factory

    def get_forecast(self, period_id, team_ids):
        def unavailable(reason):
            return ForecastResult(provider=self.name, availability='unavailable', reason=reason,
                                  target_period=period_id, projections=[], missing_teams=sorted(team_ids),
                                  method_label='evidence-bound numerical engine; no issued compatible quarter')
        if self.service is None or self.session_factory is None:
            return unavailable('forecast persistence is not configured')
        from app.db.models import PlanningPeriod
        with self.session_factory() as session:
            period = session.get(PlanningPeriod, period_id)
            if period is None:
                return unavailable('unknown planning period')
            start, end = period.starts_on.isoformat(), (period.ends_on + timedelta(days=1)).isoformat()
        bundle = self.service.views(scope_type='team')
        run_id = bundle.get('run_id')
        if not run_id:
            return unavailable('no published forecast; request a refresh')
        run = self.service.store.get_run(run_id)
        snapshot = self.service.store.get_snapshot(run['snapshot_id'])
        projections = []
        for view in bundle.get('views', []):
            team = view['scope']['id']
            quarter = view.get('quarter_outlook') or {}
            if team not in team_ids or quarter.get('start') != start or quarter.get('end') != end:
                continue
            amount = quarter.get('base')
            if amount is None or not quarter.get('complete', False):
                continue
            amount = Decimal(str(amount))
            if not amount.is_finite() or amount < 0:
                continue
            projections.append(TeamProjection(team=team, amount=amount.quantize(Decimal('.01'), rounding=ROUND_HALF_UP),
                assumptions=list(quarter.get('assumptions', [])),
                uncertainty='Conditional quarter continuation. Scenario bounds are descriptive and are not historical-error intervals.'))
        missing = sorted(set(team_ids)-{p.team for p in projections})
        return ForecastResult(provider=self.name, availability='available' if not missing else ('partial' if projections else 'unavailable'),
            reason='Some full-quarter amounts are incomplete or unavailable.' if missing else None,
            target_period=period_id, basis='full_period_total', projections=projections, missing_teams=missing,
            value_kind='simulated' if snapshot.get('is_synthetic', True) else 'estimated',
            method_label=bundle.get('procedure_version', 'structured weekday rate')+'; conditional quarter continuation',
            generated_at=run['generated_at'], forecast_run_id=run_id, input_snapshot_id=run['snapshot_id'],
            input_revision=revision_from_snapshot(snapshot), repository_revision=snapshot.get('repository_revision'), tenant_id=snapshot['tenant_id'],
            information_cutoff=snapshot['information_cutoff'], procedure_version=bundle.get('procedure_version'))
