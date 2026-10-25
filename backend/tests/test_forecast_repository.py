"""Repository imports remain actual spend, never invented complete history."""
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from app.db.base import create_all, make_engine, make_session_factory
from app.db.models import ImportBatch, Person, PlanningPeriod, Team, UsageRecord
from app.forecasting.persistence import ForecastStore


NOW = '2026-10-24T12:00:00Z'


def instant(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00'))


@pytest.fixture
def repository(tmp_path):
    engine = make_engine(tmp_path / 'repository.sqlite')
    create_all(engine)
    factory = make_session_factory(engine)
    with factory() as session:
        session.add(PlanningPeriod(id='2026-q4', label='Q4', starts_on=date(2026, 10, 1),
                                   ends_on=date(2026, 12, 31), created_at=instant('2026-09-01T00:00:00Z')))
        session.add(Team(id='engineering', name='Engineering', created_at=instant('2026-09-01T00:00:00Z')))
        session.commit()
    yield factory
    engine.dispose()


def add_record(factory, key, *, imported_at='2026-10-23T00:00:00Z', occurred_at='2026-10-22T01:00:00Z',
               amount='12.34', category='direct_api', unit='USD', team='engineering', person=None):
    with factory() as session:
        batch = ImportBatch(id='batch-' + key, created_at=instant(imported_at), source_kind='billing',
                            content_hash=key, status='imported', record_count=1, imported_by='test',
                            value_kind_default='measured')
        session.add(batch)
        session.flush()
        session.add(UsageRecord(id=key, created_at=instant(imported_at), import_batch_id=batch.id,
                                source_kind='billing', source_record_key=key, source_account='shared-account',
                                team_id=team, person_id=person, period_id='2026-q4', occurred_at=instant(occurred_at),
                                amount=None if amount is None else Decimal(amount), unit=unit,
                                input_tokens=900, value_kind='measured', cost_category=category,
                                counts_toward_spend=UsageRecord.derive_counts_toward_spend(category)))
        session.commit()


def builder(repository, **kwargs):
    from app.forecasting.repository import repository_snapshot_factory
    return repository_snapshot_factory(repository, clock=lambda: NOW, **kwargs)


def test_imported_spend_preserves_identity_units_and_unknown_coverage(repository):
    add_record(repository, 'a')
    snapshot = builder(repository)(now=NOW, tenant_id='northstar')
    row, = snapshot['observations']
    assert row['quantity'] == '12.34'
    assert row['meter'] == 'usd'
    assert row['person_id'] is None and row['project_id'] is None
    assert row['team_id'] == 'engineering'
    assert row.get('exposure') is None and row['complete'] is False and row['mature'] is False
    assert row['observation_id'] == 'repository:usage:a'
    assert row['available_at'] == '2026-10-23T00:00:00.000000Z'
    assert row['provenance']['source_record_key'] == 'a'
    assert row['provenance']['input_tokens'] == 900
    assert snapshot['coverage'] == []
    assert snapshot['period_start'] == '2026-10-01' and snapshot['period_end'] == '2027-01-01'
    assert snapshot['pricing'][0]['rate'] == '1'
    assert snapshot['pricing'][0]['unit'] == 'usd'


def test_as_of_filters_late_import_future_usage_and_nonspend_records(repository):
    add_record(repository, 'known')
    add_record(repository, 'late', imported_at='2026-10-25T00:00:00Z')
    add_record(repository, 'future', occurred_at='2026-10-25T00:00:00Z')
    add_record(repository, 'included', category='included_usage', amount='900')
    add_record(repository, 'tokens', category='unpriced_usage', amount=None)
    add_record(repository, 'foreign', unit='EUR')
    snapshot = builder(repository)(now=NOW, tenant_id='northstar')
    assert [r['provenance']['source_record_key'] for r in snapshot['observations']] == ['known']
    assert any('unpriced' in x.lower() for x in snapshot['limitations'])
    assert any('currency' in x.lower() for x in snapshot['limitations'])


def test_material_revisions_change_with_new_import_and_mapping(repository, tmp_path):
    from app.forecasting.service import ForecastService
    add_record(repository, 'a')
    service = ForecastService(ForecastStore(tmp_path / 'forecast.sqlite'), snapshot_factory=builder(repository), now=lambda: NOW)
    before = service.material_revision()
    add_record(repository, 'b')
    after = service.material_revision()
    assert before != after
    with repository() as session:
        session.get(UsageRecord, 'a').team_id = None
        session.commit()
    assert service.material_revision() != after


def test_historical_snapshot_does_not_project_current_mutable_attribution_backwards(repository):
    add_record(repository, 'a', imported_at='2026-10-18T00:00:00Z', occurred_at='2026-10-17T00:00:00Z')
    snapshot = builder(repository)(now='2026-10-19T00:00:00Z', tenant_id='northstar')
    assert snapshot['observations'][0]['team_id'] is None
    assert any('attribution' in x.lower() for x in snapshot['limitations'])


def test_explicit_sync_appends_versions_and_old_snapshot_stays_immutable(repository, tmp_path):
    from app.forecasting.repository import synchronize_repository_inputs
    add_record(repository, 'a')
    store = ForecastStore(tmp_path / 'forecast.sqlite')
    factory = builder(repository)
    first = synchronize_repository_inputs(store, factory, now=NOW)
    again = synchronize_repository_inputs(store, factory, now=NOW)
    assert first['id'] == again['id']
    with repository() as session:
        session.get(UsageRecord, 'a').team_id = None
        session.commit()
    newer = synchronize_repository_inputs(store, factory, now=NOW)
    assert newer['revision'] != first['revision']
    rows = store.input_records(NOW)
    assert len(rows) == 2
    assert rows[0]['payload']['observations'][0]['team_id'] == 'engineering'
    assert rows[1]['payload']['observations'][0]['team_id'] is None


def test_archive_records_reversion_as_new_revision(repository, tmp_path):
    from app.forecasting.repository import synchronize_repository_inputs
    add_record(repository, 'a')
    store = ForecastStore(tmp_path / 'forecast.sqlite')
    factory = builder(repository)
    first = synchronize_repository_inputs(store, factory, now=NOW)
    with repository() as session:
        session.get(UsageRecord, 'a').team_id = None
        session.commit()
    synchronize_repository_inputs(store, factory, now=NOW)
    with repository() as session:
        session.get(UsageRecord, 'a').team_id = 'engineering'
        session.commit()
    restored = synchronize_repository_inputs(store, factory, now=NOW)
    assert restored['id'] != first['id']
    assert len(store.input_records(NOW)) == 3


def test_unknown_daily_coverage_preserves_actual_money_and_blocks_forecast(repository):
    from forecasting.planning import build_forecast
    add_record(repository, 'a')
    snapshot = builder(repository)(now=NOW, tenant_id='northstar')
    bundle = build_forecast(snapshot, run_id='repository-run', generated_at=NOW)
    company = bundle['views'][0]
    assert company['components']['recorded'] == 12.34
    assert company['components']['late'] is None
    assert company['quarter_outlook']['base'] is None
    assert all(point['base'] is None for point in company['daily'])
    assert any('daily source completeness' in note for note in company['limitations'])


def test_revision_matches_factory_and_does_not_hash_the_clock(repository):
    from app.forecasting.repository import repository_revision
    add_record(repository, 'a')
    snapshot = builder(repository)(now=NOW, tenant_id='northstar')
    with repository() as session:
        expected = repository_revision(session, NOW)
        assert expected == repository_revision(session, '2026-10-24T13:00:00Z')
    assert snapshot['repository_revision'] == expected


def test_explicit_current_read_preserves_attribution_despite_clock_drift(repository):
    from app.forecasting.repository import repository_snapshot_factory
    add_record(repository, 'a')
    factory = repository_snapshot_factory(repository, clock=lambda: '2026-10-24T12:00:00.001Z')
    assert factory.supports_as_of is True
    assert factory(now=NOW, as_of=False)['observations'][0]['team_id'] == 'engineering'


def test_cutoff_500ms_ago_never_reveals_current_mapping(repository):
    add_record(repository, 'a')
    with repository() as session:
        session.add(Team(id='research', name='Research', created_at=instant('2026-09-01T00:00:00Z')))
        session.flush()
        session.get(UsageRecord, 'a').team_id = 'research'
        session.commit()
    factory = builder(repository)
    cutoff = '2026-10-24T11:59:59.500Z'
    assert factory(now=cutoff)['observations'][0]['team_id'] is None
    assert factory(now=cutoff)['observations'][0]['provenance']['team_id'] is None
    assert factory(now=cutoff, as_of=True)['observations'][0]['team_id'] is None
    assert factory(now=NOW, as_of=False)['observations'][0]['team_id'] == 'research'


def test_exact_archived_cutoff_replays_prior_attribution_read_only(repository, tmp_path):
    from app.forecasting.repository import synchronize_repository_inputs
    add_record(repository, 'a')
    store = ForecastStore(tmp_path / 'forecast.sqlite')
    factory = builder(repository, store=store)
    archive = synchronize_repository_inputs(store, factory, now=NOW)
    with repository() as session:
        session.get(UsageRecord, 'a').team_id = None
        session.commit()
    archived = factory(now=NOW, as_of=True)
    assert archived['observations'][0]['team_id'] == 'engineering'
    assert archived['repository_archive']['id'] == archive['id']
    assert len(store.input_records(NOW)) == 1
    assert factory(now='2026-10-24T12:00:00.500Z', as_of=True)['observations'][0]['team_id'] == 'engineering'


def test_transaction_capture_rolls_back_with_repository_change(repository, tmp_path):
    from app.forecasting.repository import capture_repository_inputs
    store = ForecastStore(repository.kw['bind'].url.database)
    repository.configure(info={'forecast_store': store})
    add_record(repository, 'a')
    with repository() as session:
        session.get(UsageRecord, 'a').team_id = None
        receipt = capture_repository_inputs(session, now=NOW)
        assert receipt['kind'] == 'repository_state'
        session.rollback()
    assert store.input_records(NOW) == []
    with repository() as session:
        assert session.get(UsageRecord, 'a').team_id == 'engineering'


def test_versioned_capture_replays_between_mutations_and_excludes_later_inputs(repository):
    from app.forecasting.repository import capture_repository_inputs
    store = ForecastStore(repository.kw['bind'].url.database)
    repository.configure(info={'forecast_store': store})
    add_record(repository, 'a')
    with repository() as session:
        capture_repository_inputs(session, now=NOW)
        session.commit()
    later = '2026-10-27T12:00:00Z'
    with repository() as session:
        session.get(UsageRecord, 'a').team_id = None
        capture_repository_inputs(session, now=later)
        session.commit()
    add_record(repository, 'late', imported_at=later)
    factory = builder(repository, store=store)
    old = factory(now='2026-10-26T00:00:00Z', as_of=True)
    assert [row['provenance']['source_record_key'] for row in old['observations']] == ['a']
    assert old['observations'][0]['team_id'] == 'engineering'
    assert old['coverage'] == []
    assert factory(now=later, as_of=True)['observations'][0]['team_id'] is None


def test_import_and_mapping_services_capture_committed_versions(app, clock, id_factory):
    from app.seed.northstar import seed_reference, SPEND_FILE
    from app.services.imports import run_import
    from app.services.teams import upsert_mapping
    with app.state.session_factory() as session:
        seed_reference(session, clock=clock, ids=id_factory)
        session.commit()
        run_import(session, source_kind='northstar_billing', raw=SPEND_FILE.read_bytes(), filename='spend.csv',
                   actor_id='test', clock=clock, ids=id_factory)
        session.commit()
    clock.advance(days=3)
    with app.state.session_factory() as session:
        upsert_mapping(session, source_kind='northstar_billing', source_account='ws-research',
                       team_id='engineering', effective_from=date(2026, 1, 1), actor_id='test', clock=clock, ids=id_factory)
        session.commit()
    service = app.state.forecast_service
    old = service.current_snapshot(cutoff='2026-10-26T00:00:00Z')
    research = [row for row in old['observations'] if row['provenance']['source_account'] == 'ws-research']
    assert research and all(row['team_id'] == 'research' for row in research)
    assert all(row['team_id'] == 'engineering' for row in service.current_snapshot()['observations']
               if row['provenance']['source_account'] == 'ws-research')
    assert old['repository_archive']['received_at'] == '2026-10-24T12:00:00.000000Z'


def test_capture_preserves_known_future_event_without_revealing_it_early(repository):
    from app.forecasting.repository import capture_repository_inputs
    store = ForecastStore(repository.kw['bind'].url.database)
    repository.configure(info={'forecast_store': store})
    add_record(repository, 'future', occurred_at='2026-10-26T00:00:00Z')
    with repository() as session:
        capture_repository_inputs(session, now=NOW)
        session.commit()
    factory = builder(repository, store=store)
    assert factory(now=NOW, as_of=True)['observations'] == []
    assert factory(now='2026-10-26T00:00:00Z', as_of=True)['observations'][0]['quantity'] == '12.34'


def test_startup_captures_once_and_reads_never_append(app, clock):
    service = app.state.forecast_service
    before = service.store.input_records(clock.now())
    assert [row['kind'] for row in before] == ['repository_state']
    service.current_snapshot()
    service.current_actuals()
    assert service.store.input_records(clock.now()) == before


def test_publication_capture_hook_commits_current_state(repository):
    from app.forecasting.repository import repository_snapshot_factory
    store = ForecastStore(repository.kw['bind'].url.database)
    repository.configure(info={'forecast_store': store})
    add_record(repository, 'a')
    factory = repository_snapshot_factory(repository, clock=lambda: NOW, store=store)
    receipt = factory.capture_inputs(now=NOW, tenant_id='northstar')
    assert receipt['kind'] == 'repository_state'
    assert len(store.input_records(NOW)) == 1


def add_person(factory, *, name='Ada Example', team='engineering', active=True,
               created_at='2026-09-01T00:00:00Z'):
    with factory() as session:
        session.add(Person(id='ada', name=name, team_id=team, active=active,
                           is_simulated=False, integrations=['slack'], created_at=instant(created_at)))
        session.commit()


def test_directory_identity_flows_to_real_person_actuals_without_exposure(repository):
    from forecasting.planning import build_forecast
    add_person(repository)
    add_record(repository, 'personal', person='ada')
    snapshot = builder(repository)(now=NOW, as_of=False)
    assert snapshot['people'] == [{'id': 'ada', 'name': 'Ada Example', 'team_id': 'engineering',
                                   'active': True, 'is_simulated': False}]
    row, = snapshot['observations']
    assert row['person_id'] == 'ada'
    assert snapshot['memberships'] == []
    assert row['exposure'] is None and snapshot['coverage'] == []
    bundle = build_forecast(snapshot, run_id='personal', generated_at=NOW)
    personal, = [v for v in bundle['views'] if v['scope']['type'] == 'person']
    assert personal['scope']['id'] == 'ada'
    assert personal['components']['recorded'] == 12.34
    assert personal['quarter_outlook']['base'] is None


def test_uncaptured_history_does_not_leak_mutable_person_or_directory(repository):
    add_person(repository, name='Current Name')
    add_record(repository, 'personal', person='ada', imported_at='2026-10-18T00:00:00Z',
               occurred_at='2026-10-17T00:00:00Z')
    snapshot = builder(repository)(now='2026-10-19T00:00:00Z', as_of=True)
    assert snapshot['observations'][0]['person_id'] is None
    assert snapshot['observations'][0]['provenance']['person_id'] is None
    assert snapshot['people'] == [{'id': 'ada', 'name': 'ada', 'team_id': None,
                                   'active': None, 'is_simulated': None}]


def test_person_directory_changes_stale_revision_and_archive_freezes_identity(repository, tmp_path):
    from app.forecasting.repository import synchronize_repository_inputs
    add_person(repository)
    add_record(repository, 'personal', person='ada')
    store = ForecastStore(tmp_path / 'people-archive.sqlite')
    factory = builder(repository, store=store)
    first = synchronize_repository_inputs(store, factory, now=NOW)
    with repository() as session:
        session.add(Team(id='research', name='Research', created_at=instant('2026-09-01T00:00:00Z')))
        session.flush()
        person = session.get(Person, 'ada')
        person.name, person.team_id, person.active = 'New Name', 'research', False
        session.commit()
    current = factory(now=NOW, as_of=False)
    old = factory(now=NOW, as_of=True)
    assert current['repository_revision'] != old['repository_revision']
    assert current['people'][0]['name'] == 'New Name'
    assert old['people'][0]['name'] == 'Ada Example'
    assert old['people'][0]['team_id'] == 'engineering'
    assert old['people'][0]['active'] is True
    # Native import-time attribution survives a later directory move/deactivation.
    assert current['observations'][0]['person_id'] == old['observations'][0]['person_id'] == 'ada'
    assert current['observations'][0]['team_id'] == old['observations'][0]['team_id'] == 'engineering'
    assert old['repository_archive']['id'] == first['id']


def test_future_directory_entries_do_not_appear_before_receipt_cutoff(repository):
    add_person(repository, created_at='2026-10-25T00:00:00Z')
    snapshot = builder(repository)(now=NOW, as_of=False)
    assert snapshot['people'] == []


def test_native_daily_seed_and_live_person_import_replay_without_false_coverage(seeded, client, clock):
    from reference_data import upload
    service = seeded.state.forecast_service
    before = service.current_snapshot()
    assert len(before['people']) == 15
    assert sum(Decimal(r['quantity']) for r in before['observations']) == Decimal('95000.00')
    assert all(r['person_id'] is not None for r in before['observations'])
    assert before['coverage'] == [] and before['memberships'] == []
    clock.advance(days=1)
    raw = ('record_id,occurred_at,source_account,user_email,provider,cost_category,amount,unit\n'
           'live-person,2026-10-21T00:00:00Z,ws-research,ava.chen@northstar.example,anthropic,direct_api,11.00,USD\n'
           'live-future,2026-10-26T00:00:00Z,ws-research,ava.chen@northstar.example,anthropic,direct_api,7.00,USD\n')
    first = upload(client, raw, filename='live-people.csv')
    assert first.status_code == 201, first.text
    assert first.json()['stats']['person_resolved'] == 2
    duplicate = upload(client, raw, filename='live-people-again.csv')
    assert duplicate.status_code == 200 and duplicate.json()['status'] == 'duplicate'
    current = service.current_snapshot()
    live, = [r for r in current['observations'] if r['provenance']['source_record_key'] == 'live-person']
    assert live['person_id'] == 'research-ava-chen' and live['quantity'] == '11.00'
    assert sum(Decimal(r['quantity']) for r in current['observations']) == Decimal('95011.00')
    assert current['coverage'] == [] and not any(r['complete'] or r['mature'] for r in current['observations'])
    old = service.current_snapshot(cutoff=NOW)
    assert sum(Decimal(r['quantity']) for r in old['observations']) == Decimal('95000.00')
    replay = service.current_snapshot(cutoff='2026-10-26T00:00:00Z')
    future, = [r for r in replay['observations'] if r['provenance']['source_record_key'] == 'live-future']
    assert future['person_id'] == 'research-ava-chen' and future['quantity'] == '7.00'
    job = service.refresh('native-live-person')
    assert seeded.state.forecast_worker.process_one()
    issued = service.views(run_id=job['run_id'], scope_type='person', scope_id='research-ava-chen')['views']
    assert issued and issued[0]['components']['recorded'] > 11
    assert issued[0]['quarter_outlook']['base'] is None
