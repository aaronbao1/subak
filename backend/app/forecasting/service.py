"""Application API over frozen inputs, durable refresh jobs and immutable runs."""
from __future__ import annotations

from copy import deepcopy
from functools import wraps
import hashlib
import logging
from pathlib import Path
from datetime import datetime, timedelta, timezone
import uuid

from .persistence import ForecastStore, ImmutableConflict, encode, identity, iso

log = logging.getLogger(__name__)


def utc_now():
    return iso(datetime.now(timezone.utc))


def procedure_dependency_manifest():
    """Explicit upstream numerical adapters; answer-only tooling is excluded."""
    root = Path(__file__).parent
    return {
        'evidence_extraction': {'version': 'native-envelope-v1',
                                'sha256': hashlib.sha256((root / 'evidence.py').read_bytes()).hexdigest()},
        'repository_adapter': {'version': 'repository-snapshot-v1',
                               'sha256': hashlib.sha256((root / 'repository.py').read_bytes()).hexdigest()},
        'native_evidence_adapter': {'version': 'native-corpus-signals-v1',
                                    'sha256': hashlib.sha256((root / 'native_evidence.py').read_bytes()).hexdigest()},
        'outcome_ingestion': {'version': 'observed-target-outcome-v1',
                              'sha256': hashlib.sha256((root / 'outcomes.py').read_bytes()).hexdigest()},
        'repository_archive': {'version': 'repository-row-archive-v2',
                               'sha256': hashlib.sha256((root / 'archive.py').read_bytes()).hexdigest()},
    }


def empty_snapshot(*, now, tenant_id):
    """An unconfigured repository has unknown inputs, never invented demo history."""
    day = datetime.fromisoformat(iso(now).replace('Z', '+00:00')).date()
    quarter_month = ((day.month - 1) // 3) * 3 + 1
    period_start = day.replace(month=quarter_month, day=1)
    period_end = day.replace(year=day.year + 1, month=1, day=1) if quarter_month == 10 else day.replace(month=quarter_month + 3, day=1)
    return {'schema_version': 1, 'tenant_id': tenant_id, 'information_cutoff': now,
            'history_complete_through': (day - timedelta(days=1)).isoformat(),
            'forecast_start': day.isoformat(), 'period_start': period_start.isoformat(), 'period_end': period_end.isoformat(),
            'target': {'unit': 'USD', 'quantity': 'spend', 'basis': 'planning', 'timezone': 'UTC'},
            'people': [], 'memberships': [], 'projects': [], 'configurations': [], 'pricing': [],
            'required_sources': ['repository:usage'], 'coverage': [], 'observations': [], 'drivers': [],
            'limitations': ['Repository forecast inputs have not been configured.']}


def coordinated_operation(method):
    @wraps(method)
    def guarded(self, *args, **kwargs):
        with self.store.operation():
            return method(self, *args, **kwargs)
    return guarded


class ForecastService:
    def __init__(self, store: ForecastStore, *, snapshot_factory=None, builder=None, now=None):
        self.store = store
        if snapshot_factory is None:
            snapshot_factory = empty_snapshot
        if builder is None:
            from forecasting.planning import build_forecast
            builder = build_forecast
        self.snapshot_factory = snapshot_factory
        self.builder = builder
        self.now = now or utc_now

    @coordinated_operation
    def current_snapshot(self, *, tenant_id='northstar', cutoff=None, as_of=None, include_learning=True):
        """Assemble current inputs; directory readers may omit learning archives.

        Forecast issuance keeps the complete history by default. Excluding it at
        the SQL boundary avoids decoding large archived targets for membership.
        """
        now = iso(cutoff or self.now())
        factory_args = {'now': now, 'tenant_id': tenant_id}
        if getattr(self.snapshot_factory, 'supports_as_of', False):
            factory_args['as_of'] = (cutoff is not None) if as_of is None else as_of
        snapshot = deepcopy(self.snapshot_factory(**factory_args))
        snapshot['tenant_id'] = tenant_id
        snapshot['information_cutoff'] = now
        snapshot['generated_at'] = iso(self.now())
        snapshot['procedure_dependencies'] = procedure_dependency_manifest()
        learning_kinds = ('issued_targets', 'truth_revisions', 'forecast_errors')
        rows = self.store.input_records(now, tenant_id, latest=True,
                                        exclude_kinds=() if include_learning else learning_kinds)
        base_revisions = snapshot.get('source_revisions', [])
        revisions = ([{'kind': 'fixture_source', 'source_id': str(k), 'revision': str(v)} for k, v in base_revisions.items()] if isinstance(base_revisions, dict) else deepcopy(base_revisions))
        collections = {}
        for row in rows:
            kind, payload = row['kind'], row['payload']
            revisions.append({k: row[k] for k in ('id', 'kind', 'source_id', 'revision', 'available_at', 'received_at')})
            if kind == 'model_registry':
                snapshot['model_registry'] = deepcopy(payload)
                snapshot['procedure'] = deepcopy(payload['serving'])
            elif kind == 'evidence':
                snapshot['drivers'] = [d for d in snapshot.get('drivers', []) if d.get('source_id') != row['source_id']]
                snapshot['drivers'].extend(deepcopy(payload.get('drivers', [])))
            elif kind not in ('issued_targets', 'truth_revisions', 'forecast_errors'):
                collections.setdefault(kind, []).extend(deepcopy(payload if isinstance(payload, list) else [payload]))
        for kind, records in collections.items():
            snapshot[kind] = records
        # Calibration uses all issued records and truth revisions, never latest-only corrections.
        if include_learning:
            all_rows = self.store.input_records(now, tenant_id, kinds=learning_kinds)
            for kind in learning_kinds:
                records = [r['payload'] for r in all_rows if r['kind'] == kind]
                if records:
                    snapshot[kind] = records
        else:
            for kind in learning_kinds:
                snapshot.pop(kind, None)
        # Input payload provenance cannot make post-cutoff observations usable.
        for kind in ('observations', 'coverage', 'pricing'):
            snapshot[kind] = [r for r in snapshot.get(kind, []) if not r.get('available_at', r.get('known_at')) or iso(r.get('available_at', r.get('known_at'))) <= now]
        snapshot['source_revisions'] = revisions
        snapshot['id'] = 'snapshot_' + identity({k: v for k, v in snapshot.items() if k != 'id'})[:32]
        return snapshot

    @coordinated_operation
    def material_revision(self, *, tenant_id='northstar'):
        snapshot = self.current_snapshot(tenant_id=tenant_id)
        excluded = {'id', 'information_cutoff', 'generated_at', 'issued_targets', 'truth_revisions', 'forecast_errors', 'source_revisions', 'model_registry'}
        material = {k: v for k, v in snapshot.items() if k not in excluded}
        material['source_revisions'] = [r for r in snapshot.get('source_revisions', []) if r['kind'] not in ('issued_targets', 'truth_revisions', 'forecast_errors', 'model_registry')]
        return identity(material)

    @coordinated_operation
    def refresh(self, idempotency_key, *, tenant_id='northstar', scheduled_for=None):
        if not isinstance(idempotency_key, str) or not idempotency_key.strip() or len(idempotency_key) > 200:
            raise ValueError('Idempotency-Key must contain 1–200 characters')
        old = self.store.find_job(tenant_id, idempotency_key)
        if old:
            return old
        now = iso(self.now())
        capture = getattr(self.snapshot_factory, 'capture_inputs', None)
        if capture is not None:
            capture(now=now, tenant_id=tenant_id)
            now = iso(self.now())
        snapshot = self.current_snapshot(tenant_id=tenant_id, cutoff=scheduled_for or now, as_of=scheduled_for is not None or capture is not None)
        origin = datetime.fromisoformat(iso(scheduled_for or now).replace('Z', '+00:00'))
        # At midnight today is a whole future UTC day; otherwise start tomorrow.
        snapshot['forecast_start'] = (origin.date() + timedelta(days=0 if scheduled_for or origin.time().isoformat() == '00:00:00' else 1)).isoformat()
        from forecasting.learning import score_error_receipts, update_model_registry
        receipts = score_error_receipts(snapshot, cutoff=snapshot['information_cutoff'])
        for receipt in receipts:
            record = self.store.append_input('forecast_errors', receipt['receipt_id'], '1', receipt,
                                             available_at=receipt['effective_at'], received_at=now, tenant_id=tenant_id)
            snapshot.setdefault('source_revisions', []).append({k: record[k] for k in ('id', 'kind', 'source_id', 'revision', 'available_at', 'received_at')})
        snapshot.setdefault('forecast_errors', []).extend(receipts)
        registry = update_model_registry(snapshot, generated_at=now)
        self.store.append_input('model_registry', 'registry', registry['registry_id'], registry, available_at=registry['evaluated_at'], received_at=now, tenant_id=tenant_id)
        snapshot['model_registry'] = registry
        snapshot['procedure'] = deepcopy(registry['serving'])
        snapshot['id'] = 'snapshot_' + identity({k: v for k, v in snapshot.items() if k != 'id'})[:32]
        snapshot = self.store.save_snapshot(snapshot)
        return self.store.enqueue(tenant_id, idempotency_key, snapshot['id'], now, scheduled_for=scheduled_for)

    def schedule_due(self, *, tenant_id='northstar'):
        # Reconstruct the current Monday origin using only records received by that
        # cutoff. Publication generation remains now; ingestion is never backdated.
        now = datetime.fromisoformat(iso(self.now()).replace('Z', '+00:00'))
        monday = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
        return self.refresh('weekly:' + monday.date().isoformat(), tenant_id=tenant_id, scheduled_for=iso(monday))

    @coordinated_operation
    def current_actuals(self, tenant_id='northstar'):
        # Learning archives do not contribute to actuals or their content identity.
        snapshot = self.current_snapshot(tenant_id=tenant_id, include_learning=False)
        actuals = {'history_complete_through': snapshot.get('history_complete_through'),
                   'observations': snapshot.get('observations', []), 'coverage': snapshot.get('coverage', []),
                   'required_sources': snapshot.get('required_sources', [])}
        # A fresh read timestamp is not a correction to the observed dataset.
        # Current actuals have their own content identity, separate from the run.
        return {**actuals, 'as_of': snapshot['information_cutoff'],
                'revision': 'actuals_' + identity(actuals)}

    @staticmethod
    def _filter(bundle, scope_type=None, scope_id=None):
        result = deepcopy(bundle)
        def matches(scope):
            return (scope_type is None or scope.get('type') == scope_type) and (scope_id is None or scope.get('id') == scope_id)
        result['views'] = [v for v in result.get('views', []) if matches(v.get('scope', {}))]
        if scope_type is not None or scope_id is not None:
            effects = ([e for view in result['views'] for e in view.get('driver_effects', [])]
                       if any('driver_effects' in view for view in result['views']) else result.get('driver_effects', []))
            result['driver_effects'] = [e for e in effects if matches(e.get('scope', {'type': 'company'}))]
            result['calculations'] = [c for c in result.get('calculations', []) if
                (not str(c.get('id', '')).startswith('driver:') and 'scope' not in c) or matches(c.get('scope', {'type': 'company'}))]
            existing = {(c.get('id'), str(c.get('scope'))) for c in result['calculations']}
            for effect in result['driver_effects']:
                calculation = dict(effect, id='driver:' + effect['driver_id'])
                if (calculation['id'], str(calculation.get('scope'))) not in existing:
                    result['calculations'].append(calculation)
        return result

    @coordinated_operation
    def views(self, scope_type=None, scope_id=None, run_id=None, *, tenant_id='northstar', include_current_actuals=True):
        publication = self.store.publication(tenant_id)
        chosen = run_id or (publication or {}).get('run_id')
        # get_run decodes a new caller-owned object. An unfiltered read need not
        # deepcopy the entire immutable publication before attaching live actuals.
        bundle = self.store.get_run(chosen)['bundle'] if chosen else {'views': []}
        result = self._filter(bundle, scope_type, scope_id) if scope_type is not None or scope_id is not None else bundle
        if include_current_actuals:
            try:
                result['current_actuals'] = self.current_actuals(tenant_id)
            except Exception:
                # The latest actuals are separate from the immutable issuance.
                # No empty observations or false freshness timestamp may imply
                # that failed acquisition established zero current usage.
                log.exception('current forecast actuals could not be loaded')
                result['current_actuals'] = {'status': 'unavailable',
                    'reason': 'Current actuals could not be loaded. The issued forecast is unchanged.'}
        result['publication'] = publication if publication and publication['run_id'] == chosen else None
        return result

    @coordinated_operation
    def explain(self, run_id, scope_type=None, scope_id=None, driver_id=None):
        run = self.store.get_run(run_id)
        bundle = self._filter(run['bundle'], scope_type, scope_id)
        if (scope_type is not None or scope_id is not None) and not bundle.get('views'):
            raise KeyError('scope not found in issued run')
        if driver_id:
            snapshot = self.store.get_snapshot(run['snapshot_id'])
            if driver_id not in {d.get('id') for d in snapshot.get('drivers', [])}:
                raise KeyError('driver not found in issued snapshot')
            bundle['driver_effects'] = [d for d in bundle.get('driver_effects', []) if d.get('driver_id') == driver_id]
            bundle['calculations'] = [c for c in bundle.get('calculations', []) if c.get('driver_id') == driver_id]
        return {**bundle, 'snapshot': self.store.get_snapshot(run['snapshot_id']), 'generated_at': run['generated_at']}

    @coordinated_operation
    def compare(self, run_ids, scope_type='company', scope_id=None):
        return {'runs': [self.explain(run_id, scope_type, scope_id) for run_id in run_ids]}

    @coordinated_operation
    def scenario(self, run_id, drivers, scope_type=None, scope_id=None):
        if not isinstance(drivers, list) or any(not isinstance(d, dict) for d in drivers):
            raise ValueError('drivers must be an array of driver objects')
        parent = self.store.get_run(run_id)
        if (scope_type is not None or scope_id is not None) and not self._filter(parent['bundle'], scope_type, scope_id).get('views'):
            raise KeyError('scope not found in issued run')
        snapshot = self.store.get_snapshot(parent['snapshot_id'])
        self.validate_drivers(drivers)
        now = iso(self.now())
        job = self.store.enqueue(snapshot['tenant_id'], 'scenario:' + uuid.uuid4().hex, parent['snapshot_id'], now,
                                 job_type='scenario', parent_run_id=run_id, job_payload={'drivers': deepcopy(drivers)})
        from .worker import ForecastWorker
        ForecastWorker(self).process_one(job_id=job['id'])
        return self._filter(self.get_scenario(job['run_id']), scope_type, scope_id)

    @coordinated_operation
    def get_scenario(self, scenario_id):
        try:
            return self.store.get_scenario(scenario_id)['bundle']
        except KeyError:
            job = self.store.find_run_job(scenario_id)
            if not job or job['job_type'] != 'scenario':
                raise KeyError(scenario_id)
            return {'scenario_id': scenario_id, 'parent_run_id': job['parent_run_id'], 'job_id': job['id'],
                    'is_scenario': True, 'status': job['status'], 'last_error': job['last_error'], 'views': []}

    @staticmethod
    def validate_drivers(drivers):
        if not isinstance(drivers, list):
            raise ValueError('drivers must be an array')
        for driver in drivers:
            if not isinstance(driver, dict) or not isinstance(driver.get('id'), str):
                raise ValueError('driver ID must be a string')
            if driver.get('supersedes') is not None and not isinstance(driver['supersedes'], str):
                raise ValueError('driver supersedes must be an ID string')
            if not isinstance(driver.get('scope', {}), dict) or not isinstance(driver.get('parameters', {}), dict):
                raise ValueError('driver scope and parameters must be objects')
            for key in ('effective_from', 'effective_to'):
                if driver.get(key) is not None:
                    try:
                        datetime.strptime(driver[key], '%Y-%m-%d')
                    except (ValueError, TypeError) as exc:
                        raise ValueError(f'driver {key} must be an ISO date') from exc
            try:
                encode(driver)
            except (TypeError, ValueError) as exc:
                raise ValueError('driver must contain finite JSON values') from exc

    @coordinated_operation
    def ingest_outcome(self, envelope, *, tenant_id='northstar'):
        from .outcomes import ingest_outcome
        return ingest_outcome(self, envelope, tenant_id=tenant_id)

    @coordinated_operation
    def ingest_evidence(self, envelope, *, tenant_id='northstar'):
        if not isinstance(envelope, dict):
            raise ValueError('evidence envelope must be an object')
        if envelope.get('source') not in {'slack', 'asana', 'monday', 'model_release'}:
            raise ValueError('unsupported evidence source')
        if not isinstance(envelope.get('source_id'), str) or not envelope['source_id'].strip():
            raise ValueError('source_id must be a nonempty string')
        revision = envelope.get('revision')
        if isinstance(revision, bool) or not isinstance(revision, (str, int)) or str(revision).strip() == '':
            raise ValueError('revision must be a nonempty string or integer')
        for key in ('available_at', 'occurred_at'):
            if key in envelope or key == 'available_at':
                if not isinstance(envelope.get(key), str):
                    raise ValueError(f'{key} must be an ISO timestamp string')
                iso(envelope[key])
        if 'text' in envelope and not isinstance(envelope['text'], str):
            raise ValueError('text must be a string')
        native = envelope.get('payload', {})
        if not isinstance(native, dict):
            raise ValueError('payload must be an object')
        if native.get('supersedes') is not None and not isinstance(native['supersedes'], str):
            raise ValueError('payload.supersedes must be a driver ID string')
        try:
            encode(envelope)
        except (TypeError, ValueError) as exc:
            raise ValueError('evidence must contain finite JSON values') from exc
        existing = self.store.find_input('evidence', envelope['source_id'], revision, tenant_id=tenant_id)
        if existing:
            if encode(existing['payload']['envelope']) != encode(envelope):
                raise ImmutableConflict('source revision already exists with different envelope')
            return {**deepcopy(existing['payload']), 'id': existing['id'], 'available_at': existing['available_at'],
                    'received_at': existing['received_at'], 'queue_status': 'queued', 'status': 'succeeded',
                    'interpretation_job_id': (self.store.find_job(tenant_id, 'interpretation:' + identity([envelope['source_id'], str(envelope['revision'])])) or {}).get('id')}
        now = iso(self.now())
        key = 'interpretation:' + identity([envelope['source_id'], str(envelope['revision'])])
        job = self.store.find_job(tenant_id, key)
        if job and encode(job['job_payload']['envelope']) != encode(envelope):
            raise ImmutableConflict('source revision already queued with different envelope')
        if not job:
            snapshot = self.store.save_snapshot(self.current_snapshot(tenant_id=tenant_id))
            job = self.store.enqueue(tenant_id, key, snapshot['id'], now, job_type='interpretation', job_payload={'envelope': deepcopy(envelope)})
        # A competing request can win enqueue after the initial lookup.
        if encode(job['job_payload']['envelope']) != encode(envelope):
            raise ImmutableConflict('source revision already queued with different envelope')
        from .worker import ForecastWorker
        ForecastWorker(self).process_one(job_id=job['id'])
        job = self.store.get_job(job['id'])
        row = self.store.find_input('evidence', envelope['source_id'], envelope['revision'], tenant_id=tenant_id)
        if row:
            return {**deepcopy(row['payload']), 'id': row['id'], 'available_at': row['available_at'], 'received_at': row['received_at'],
                    'queue_status': 'queued', 'interpretation_job_id': job['id'], 'status': 'succeeded'}
        return {'id': job['id'], 'envelope': deepcopy(envelope), 'drivers': [], 'available_at': envelope['available_at'],
                'received_at': job['created_at'], 'interpretation_job_id': job['id'], 'status': job['status'],
                'last_error': job['last_error'], 'queue_status': 'interpreting'}

    @coordinated_operation
    def evidence(self, *, tenant_id='northstar'):
        now = iso(self.now())
        publication = self.store.publication(tenant_id)
        included = set()
        if publication:
            bundle = self.store.get_run(publication['run_id'])['bundle']
            included = {d['id'] for v in bundle.get('views', []) for d in v.get('included_drivers', []) if isinstance(d, dict) and 'id' in d}
        items = []
        for row in self.store.input_records(now, tenant_id, latest=True):
            if row['kind'] != 'evidence':
                continue
            payload = deepcopy(row['payload'])
            for driver in payload.get('drivers', []):
                driver['queue_status'] = 'included' if driver.get('id') in included else ('context_only' if driver.get('status') == 'context_only' else 'queued')
            items.append({**payload, 'id': row['id'], 'available_at': row['available_at'], 'received_at': row['received_at'], 'queue_status': 'included' if any(d.get('id') in included for d in payload.get('drivers', [])) else 'queued'})
        for job in self.store.list_jobs(job_type='interpretation', tenant_id=tenant_id):
            if job['status'] == 'succeeded':
                continue
            envelope = deepcopy(job['job_payload']['envelope'])
            items.append({'id': job['id'], 'envelope': envelope, 'drivers': [], 'available_at': envelope['available_at'],
                          'received_at': job['created_at'], 'interpretation_job_id': job['id'], 'status': job['status'],
                          'last_error': job['last_error'], 'queue_status': 'interpreting' if job['status'] != 'failed' else 'interpretation_failed'})
        return {'items': items}
