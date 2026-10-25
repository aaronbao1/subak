#!/usr/bin/env python3
"""Prepare or serve the full repository company with immutable weekly forecasts.

Preparation only accepts a new directory. It imports the original generated CSV
rows through native services at successive frozen receipt clocks. No holdout or
live Droid calls are used. Serving selects the runner independently of the data.
"""
from __future__ import annotations
import argparse
import csv
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import hashlib
import io
import json
from functools import partial
from pathlib import Path
import sys
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'backend'), str(ROOT / 'src'), str(ROOT / 'agent')]
from sqlalchemy import select, func
from app.config import Settings
from app.core.clock import FrozenClock
from app.db import models as m
from app.db.base import make_session_factory
from app.main import create_app
from app.schemas.documents import DocumentIn
from app.services import budget, company, corpus, imports, people
from app.forecasting.persistence import iso
from app.runtime import load_backend_env, check_droid_runtime

FIRST = datetime(2026, 9, 21, tzinfo=timezone.utc)
FINAL = datetime(2026, 10, 25, tzinfo=timezone.utc)
ISSUANCES = [FIRST + timedelta(days=7*i) for i in range(5)] + [FINAL]
DIMENSIONS = ('quantity', 'unit', 'basis', 'timezone', 'scope_type', 'scope_id', 'start', 'end')


def save(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True, default=str, allow_nan=False) + '\n')


def make_app(directory, source, clock, *, settings=None, worker=False):
    from app.forecasting.company_fixture import company_fixture_snapshot_factory
    settings = replace(settings or Settings(), db_path=directory/'app.db', forecast_provider='engine',
                       forecast_demo=False, forecast_worker=worker, allow_reset=False)
    app = create_app(settings, clock=clock)
    # The generated source manifest is an explicit fixture adapter. Normal app
    # imports retain their existing unknown-completeness semantics.
    app.state.forecast_service.snapshot_factory = company_fixture_snapshot_factory(
        app.state.session_factory, source, clock=clock)
    if worker:
        # This fixture has a frozen clock and already-issued chronological
        # vintages. Process explicit refresh/scenario work without creating a
        # second historical Monday issuance merely because the server starts.
        app.state.forecast_worker.run_forever = partial(
            app.state.forecast_worker.run_forever, schedule=False)
    return app


def initialize(app, reference, clock):
    detached = make_session_factory(app.state.engine)
    with detached() as session:
        for row in reference['periods']:
            session.add(m.PlanningPeriod(id=row['id'], label=row['label'], starts_on=date.fromisoformat(row['starts_on']),
                ends_on=date.fromisoformat(row['ends_on']), created_at=clock.now()))
        session.add_all(m.Team(id=row['id'], name=row['name'], created_at=clock.now()) for row in reference['teams'])
        session.flush()
        for kind, mappings in reference['team_mappings'].items():
            for account, team in mappings.items():
                session.add(m.TeamMapping(id=app.state.id_factory.new_id('map_'), created_at=clock.now(),
                    source_kind=kind, source_account=account, team_id=team, effective_from=date(2026, 1, 1),
                    created_by='company-fixture-loader'))
        session.flush()
        people.create_people(session, reference['people'], clock=clock)
        for period, allocations in reference['budgets'].items():
            budget.create_envelope(session, period_id=period, unit='USD', allocations=allocations,
                clock=clock, ids=app.state.id_factory)
        company.set_profile(session, company_id='northstar', name='Uber', is_simulated=True,
                            as_of=date.fromisoformat(reference['company']['as_of']), clock=clock)
        session.commit()
    return detached


def import_stage(app, detached, source, clock, previous):
    cutoff = clock.now()
    count, batches = 0, []
    # Detached importer sessions deliberately avoid expensive repository captures
    # after each CSV chunk. Every issued forecast freezes its complete canonical
    # snapshot, and native record receipt clocks remain recorded individually.
    for path in sorted((source/'backend/billing').glob('*.csv')):
        with path.open(newline='') as handle:
            reader = csv.DictReader(handle)
            chunk = []
            def flush():
                nonlocal count
                if not chunk: return
                buffer = io.StringIO()
                writer = csv.DictWriter(buffer, fieldnames=reader.fieldnames)
                writer.writeheader(); writer.writerows(chunk)
                with detached() as session:
                    result = imports.run_import(session, source_kind='northstar_billing', raw=buffer.getvalue().encode(),
                        filename=f'{cutoff.date()}-{path.stem}-{len(batches)}.csv', actor_id='company-fixture-loader',
                        clock=clock, ids=app.state.id_factory, source_label='Provider billing export')
                    assert result.batch.status in ('imported', 'duplicate'), result.batch.error_details
                    assert result.batch.unmapped_record_count == 0
                    batches.append({'id': result.batch.id, 'record_count': result.batch.record_count,
                                    'received_at': iso(cutoff), 'source_file': path.name})
                    count += result.batch.record_count
                    session.commit()
                chunk.clear()
            for row in reader:
                occurred = datetime.fromisoformat(row['occurred_at'].replace('Z', '+00:00'))
                if (previous is None or previous <= occurred) and occurred < cutoff:
                    chunk.append(row)
                    if len(chunk) == 10_000: flush()
            flush()
    docs = 0
    with detached() as session:
        for path in sorted((source/'backend/corpus').glob('*.md')):
            data = DocumentIn(**corpus.parse_markdown_document(path.read_text()))
            authored = datetime.combine(data.authored_at, datetime.min.time(), timezone.utc)
            if (previous is None or previous <= authored) and authored < cutoff:
                result = corpus.ingest_document(session, data, clock=clock, ids=app.state.id_factory)
                docs += int(result.created)
        session.commit()
    # Explicit native source capture happens at this actual stage clock, never
    # with a past authored timestamp used as receipt time.
    from app.forecasting.native_evidence import capture_native_documents
    with app.state.session_factory() as session:
        capture_native_documents(session, list(session.scalars(select(m.CorpusDocument))), now=cutoff)
        session.commit()
    return {'received_at': iso(cutoff), 'new_records': count, 'new_documents': docs, 'batches': batches}


def mature_outcomes(service, snapshot, publications):
    records = service.store.input_records(service.now(), kinds=('issued_targets', 'truth_revisions'))
    known = {row['source_id'] for row in records if row['kind'] == 'truth_revisions'}
    allowed = {row['run_id'] for row in publications}
    complete = {row['date'] for row in snapshot['coverage'] if row.get('complete') is True}
    # Exact posted-cent scope/day sums. No forecast values enter these amounts.
    daily = {}
    for row in snapshot['observations']:
        amount = Decimal(str(row['recorded_amount']))
        scopes = [('company', 'northstar')]
        if row.get('team_id'): scopes.append(('team', row['team_id']))
        if row.get('person_id'): scopes.append(('person', row['person_id']))
        if row.get('team_id') is None and row.get('person_id') is None: scopes.append(('shared', 'shared'))
        if row.get('team_id') is not None and row.get('person_id') is None: scopes.append(('shared', 'people_unallocated'))
        if row.get('team_id') is None and row.get('person_id') is not None: scopes.append(('shared', 'teams_unallocated'))
        for scope in scopes:
            key = (*scope, row['date'])
            daily[key] = daily.get(key, Decimal('0.00')) + amount
    receipts = []
    for record in records:
        if record['kind'] != 'issued_targets': continue
        target = record['payload']
        if target['run_id'] not in allowed or target['target_id'] in known: continue
        if target['aggregation'] != 'weekly' or target['duration_days'] != 7: continue
        start = date.fromisoformat(target['start'])
        days = [(start+timedelta(days=i)).isoformat() for i in range(7)]
        if not set(days) <= complete or target['end'] > service.now()[:10]: continue
        amount = sum((daily.get((target['scope_type'], target['scope_id'], day), Decimal('0.00')) for day in days), Decimal('0.00'))
        receipt = service.ingest_outcome({**{key: target[key] for key in DIMENSIONS}, 'target_id': target['target_id'],
            'revision': 1, 'available_at': service.now(), 'mature_at': service.now(), 'status': 'mature',
            'value': float(amount), 'source_id': 'company-posted-ledger:' + target['start'], 'is_synthetic': True, 'complete': True,
            'provenance': {'kind': 'observed', 'reference': 'generated-company-complete-source-manifest:' + target['start'],
                'accounting': 'Sum native posted USD cents; subscription charge dates retained; included usage excluded.'}})
        receipts.append(receipt)
    return receipts


def prepare(directory, source, *, stop_after_first=False, resume=False):
    directory.mkdir(parents=True, exist_ok=True)
    exists = (directory/'app.db').exists()
    if exists and not resume: raise ValueError('Use a new directory; existing company databases are never replaced.')
    if resume and not exists: raise ValueError('Resume requires the existing isolated preparation database.')
    reference = json.loads((source/'backend/reference.json').read_text())
    clock = FrozenClock(FIRST if resume else datetime(2026, 1, 1, tzinfo=timezone.utc))
    app = make_app(directory, source, clock, settings=Settings(droid_runner='fake'))
    if resume:
        detached = make_session_factory(app.state.engine)
        with detached() as session:
            profile = company.get_profile(session)
            assert profile and profile.company_id == 'northstar' and profile.name == 'Uber'
            assert session.scalar(select(func.count()).select_from(m.Person)) == len(reference['people'])
            assert session.scalar(select(func.count()).select_from(m.UsageRecord).where(m.UsageRecord.created_at > FIRST)) == 0
        check = app.state.forecast_service.snapshot_factory(now=iso(FIRST))
        assert all(not day['mismatched_record_count'] and not day['unexpected_record_count']
                   for day in check['company_fixture_manifest']['days'])
    else:
        detached = initialize(app, reference, clock)
    service = app.state.forecast_service
    stages, publications, outcomes = [], [], []
    previous = None
    for index, cutoff in enumerate(ISSUANCES):
        clock.advance(seconds=(cutoff-clock.now()).total_seconds())
        began = perf_counter()
        print(f"Importing through {cutoff.date()} (exclusive)", flush=True)
        stages.append(import_stage(app, detached, source, clock, previous))
        imported = perf_counter()
        if cutoff == FINAL:
            # Normal startup captures native source state. Freeze that exact
            # final receipt before publication, so reopening this same database
            # does not immediately stale its assessed forecast.
            from app.forecasting.repository import capture_repository_inputs
            with app.state.session_factory() as session:
                capture_repository_inputs(session, now=cutoff)
                session.commit()
        snapshot = service.current_snapshot()
        outcomes.extend(mature_outcomes(service, snapshot, publications))
        prepared = perf_counter()
        print(f"Building {cutoff.date()}: import {imported-began:.1f}s, snapshot/truth {prepared-imported:.1f}s", flush=True)
        job = service.refresh('company-vintage-v3:' + cutoff.date().isoformat())
        assert app.state.forecast_worker.process_one(job_id=job['id'])
        finished = service.store.get_job(job['id'])
        assert finished['status'] == 'succeeded', finished
        run = service.store.get_run(job['run_id'])
        frozen = service.store.get_snapshot(run['snapshot_id'])
        view = next(view for view in run['bundle']['views'] if view['scope']['type'] == 'company')
        assert view['scope']['id'] == 'northstar'
        assert all(row['available_at'] <= iso(cutoff) for row in frozen['observations'])
        assert all(row['date'] < frozen['forecast_start'] for row in frozen['observations'])
        assert all(point['base'] is not None for point in view['weekly'])
        publications.append({'run_id': run['id'], 'snapshot_id': run['snapshot_id'],
            'issued_at': view['publication']['issued_at'], 'information_cutoff': view['publication']['information_cutoff'],
            'snapshot_hash': hashlib.sha256(json.dumps(frozen, sort_keys=True).encode()).hexdigest(),
            'weekly': view['weekly'], 'quarter': view['quarter_outlook'], 'scope_count': len(run['bundle']['views']),
            'import_seconds': imported-began, 'snapshot_truth_seconds': prepared-imported,
            'build_seconds': perf_counter()-prepared,
            'elapsed_seconds': perf_counter()-began})
        save(directory/'publications.json', publications); save(directory/'import-stages.json', stages)
        save(directory/'outcome-receipts.json', outcomes)
        print(f"Published {cutoff.date()}: {stages[-1]['new_records']} new records, {len(run['bundle']['views'])} scopes, "
              f"{len(outcomes)} settled receipts, {publications[-1]['elapsed_seconds']:.1f}s", flush=True)
        previous = cutoff
        if stop_after_first: break
    with detached() as session:
        summary = {'records': session.scalar(select(func.count()).select_from(m.UsageRecord)),
                   'people': session.scalar(select(func.count()).select_from(m.Person)),
                   'teams': session.scalar(select(func.count()).select_from(m.Team)),
                   'documents': session.scalar(select(func.count()).select_from(m.CorpusDocument)),
                   'charged_total': str(sum((row.amount for row in session.scalars(select(m.UsageRecord).where(m.UsageRecord.counts_toward_spend.is_(True)))), Decimal('0.00')))}
    report = {'source_directory': str(source.resolve()), 'database': str((directory/'app.db').resolve()),
        'clock': iso(clock.now()), 'synthetic': True, 'company_id': 'northstar', 'source_company_id': reference['company']['id'],
        'company_name': 'Uber', 'source_as_of': reference['company']['as_of'],
        'source_complete_through': reference['company'].get('complete_through'),
        'partial_source_day': (None if reference['company'].get('complete_through') == reference['company']['as_of']
                               else reference['company']['as_of']),
        'runner_used_for_preparation': 'fake', 'live_request_performed': False, 'publication': service.store.publication(),
        'published_vintages': len(publications), 'mature_receipts': len(outcomes), **summary}
    save(directory/'runtime.json', report)
    app.state.engine.dispose()
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['prepare', 'serve', 'check-runtime'])
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--env-file', type=Path)
    parser.add_argument('--runner', choices=['fake', 'sdk'])
    parser.add_argument('--port', type=int, default=8789)
    parser.add_argument('--stop-after-first', action='store_true')
    parser.add_argument('--resume', action='store_true', help='Resume only a validated isolated first-cutoff preparation; never reset it.')
    args = parser.parse_args()
    if args.mode == 'prepare':
        print(json.dumps(prepare(args.directory, args.source, stop_after_first=args.stop_after_first, resume=args.resume), indent=2))
        return
    load_backend_env(args.env_file)
    if args.mode == 'check-runtime':
        report = check_droid_runtime()
        print(json.dumps(report, indent=2))
        raise SystemExit(0 if report['ready'] else 1)
    if not (args.directory/'app.db').exists(): raise ValueError('Prepare the new company database before serving.')
    runtime = json.loads((args.directory/'runtime.json').read_text())
    settings = Settings.from_env()
    if args.runner: settings = replace(settings, droid_runner=args.runner)
    clock = FrozenClock(datetime.fromisoformat(runtime['clock'].replace('Z', '+00:00')))
    import uvicorn
    uvicorn.run(make_app(args.directory, args.source, clock, settings=settings, worker=True), host='127.0.0.1', port=args.port)


if __name__ == '__main__': main()
