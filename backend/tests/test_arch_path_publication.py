"""Coverage corrections pass through real capture, persistence and publication."""
from app.forecasting.fixtures import build_northstar_snapshot
from app.forecasting.persistence import ForecastStore
from app.forecasting.service import ForecastService
from app.forecasting.worker import ForecastWorker


def test_corrected_coverage_revokes_complete_quarter_without_rebasing_prior_run(tmp_path):
    now = '2026-10-26T00:00:00Z'
    service = ForecastService(ForecastStore(tmp_path/'coverage.db'),
        snapshot_factory=build_northstar_snapshot, now=lambda: now)
    old_job = service.refresh('before')
    assert ForecastWorker(service).process_one()
    prior = service.views(run_id=old_job['run_id'])['views'][0]
    assert prior['quarter_outlook']['complete'] is True

    coverage = build_northstar_snapshot(now=now)['coverage']
    old = next(r for r in coverage if r['date']=='2026-10-20' and r['source_id']=='usage:vendor-main')
    coverage.append(dict(old, revision=2, complete=False, available_at='2026-10-25T23:59:00Z'))
    service.store.append_input('coverage', 'source-ledger', '2', coverage,
        available_at=now, received_at=now)
    corrected_job = service.refresh('correction')
    assert ForecastWorker(service).process_one()
    current = service.views()['views'][0]
    assert current['quarter_outlook']['complete'] is False
    assert current['quarter_outlook']['base'] is None
    assert current['components']['late'] is None
    assert current['components']['recorded'] > 0
    assert current['daily'][0]['base'] is not None
    frozen = service.store.get_snapshot(corrected_job['snapshot_id'])
    assert any(r.get('revision')==2 and not r['complete'] for r in frozen['coverage'])
    assert service.views(run_id=old_job['run_id'])['views'][0] == prior
