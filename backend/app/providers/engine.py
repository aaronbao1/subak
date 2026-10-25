"""Read-only adapter from immutable ForecastViews to the legacy quarter contract."""
from __future__ import annotations
from datetime import timedelta
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP

from app.schemas.forecasts import ForecastResult, PersonProjection, TeamProjection
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
        # This adapter consumes only the issued quarter. Current actuals have
        # separate acquisition and availability and must not gate a stored run.
        with self.service.store.operation():
            publication = self.service.store.publication()
            if not publication:
                return unavailable('no published forecast; request a refresh')
            run, snapshot = self.service.store.get_issued_quarter_inputs(publication['run_id'])
        bundle = run['bundle']
        run_id = bundle.get('run_id')
        if not run_id:
            return unavailable('no published forecast; request a refresh')
        projections = []
        for view in bundle.get('views', []):
            team = view['scope']['id']
            quarter = view.get('quarter_outlook') or {}
            if view['scope']['type'] != 'team' or team not in team_ids or quarter.get('start') != start or quarter.get('end') != end:
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
        people = _person_quarters(bundle, snapshot, projections, start, end)
        missing = sorted(set(team_ids)-{p.team for p in projections})
        return ForecastResult(provider=self.name, availability='available' if not missing else ('partial' if projections else 'unavailable'),
            reason='Some full-quarter amounts are incomplete or unavailable.' if missing else None,
            target_period=period_id, basis='full_period_total', projections=projections,
            person_projections=people, missing_teams=missing,
            value_kind='simulated' if snapshot.get('is_synthetic', True) else 'estimated',
            method_label=bundle.get('procedure_version', 'structured weekday rate')+'; conditional quarter continuation',
            generated_at=run['generated_at'], forecast_run_id=run_id, input_snapshot_id=run['snapshot_id'],
            input_revision=revision_from_snapshot(snapshot), repository_revision=snapshot.get('repository_revision'), tenant_id=snapshot['tenant_id'],
            information_cutoff=snapshot['information_cutoff'], procedure_version=bundle.get('procedure_version'))


def _person_quarters(bundle, snapshot, projections, start, end):
    """Adapt only an exact issued person partition to the single-team native shape.

    Canonical person quarters may cross teams; those cannot be represented by a
    native PersonProjection. Shared usage and cent-rounding residuals also make
    a team split incompatible. Withhold such groups rather than invent shares,
    reallocating money, or expanding the canonical seven-day series to quarter end.
    """
    def overlaps(row):
        return row.get('effective_from', start) < end and (row.get('effective_to') is None or row['effective_to'] > start)

    teams = defaultdict(set)
    for row in snapshot.get('observations', []):
        if row.get('person_id') is not None and start <= row['date'] < end:
            teams[row['person_id']].add(row.get('team_id'))
    for row in snapshot.get('memberships', []):
        if row.get('person_id') is not None and overlaps(row):
            teams[row['person_id']].add(row.get('team_id'))
    # Included drivers, rather than raw proposed evidence, changed this issuance.
    for view in bundle.get('views', []):
        for driver in view.get('included_drivers', []):
            if driver.get('kind') == 'membership' and overlaps(driver):
                # Each person view already contains precisely its applicable
                # included drivers, including a broader team-scoped membership.
                person = view['scope']['id'] if view['scope']['type'] == 'person' else None
                if person is not None:
                    teams[person].add(driver.get('parameters', {}).get('team_id'))

    by_team = defaultdict(list)
    team_amounts = {p.team: p.amount for p in projections}
    for view in bundle.get('views', []):
        if view['scope']['type'] != 'person':
            continue
        person = view['scope']['id']
        owners = teams[person]
        if len(owners) != 1:
            continue
        team = next(iter(owners))
        quarter = view.get('quarter_outlook') or {}
        if team not in team_amounts or team_amounts[team] <= 0 or not quarter.get('complete'):
            continue
        if quarter.get('start') != start or quarter.get('end') != end:
            continue
        base, recorded = quarter.get('base'), quarter.get('recorded')
        if base is None or recorded is None:
            continue
        amount, spent = Decimal(str(base)), Decimal(str(recorded))
        if not amount.is_finite() or not spent.is_finite() or min(amount, spent) < 0:
            continue
        amount = amount.quantize(Decimal('.01'), rounding=ROUND_HALF_UP)
        spent = spent.quantize(Decimal('.01'), rounding=ROUND_HALF_UP)
        share = (amount * 100 / team_amounts[team]).quantize(Decimal('.1'), rounding=ROUND_HALF_UP)
        by_team[team].append(PersonProjection(
            person=person, team=team, amount=amount, spent_to_date=spent, share=format(share, 'f'),
            assumptions=list(quarter.get('assumptions', [])) + [
                'Issued person quarter total; includes recorded spend. Share is its percentage of the issued team total.'],
            uncertainty='Conditional person continuation from the same immutable run; descriptive scenario bounds are not historical-error intervals.'))
    return [person for team in sorted(by_team)
            if sum((p.amount for p in by_team[team]), Decimal(0)) == team_amounts[team]
            for person in sorted(by_team[team], key=lambda p: p.person)]
