"""Read-only prospective weekly comparisons over immutable serving publications.

Recorded ledger subtotals are useful before settlement but are a different basis
from planning targets. Only an exact attested outcome can create forecast error.
"""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from .persistence import identity, iso

DIMENSIONS = ('quantity', 'unit', 'basis', 'timezone', 'scope_type', 'scope_id', 'start', 'end')


def amount(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        result = Decimal(str(value))
        return format(result.normalize(), 'f') if result.is_finite() else None
    except (ValueError, InvalidOperation):
        return None


def weekly_history(service, ledger, *, scope_type='company', scope_id=None,
                   start_date, end_date_exclusive, tenant_id='northstar'):
    if isinstance(start_date, str): start_date = date.fromisoformat(start_date)
    if isinstance(end_date_exclusive, str): end_date_exclusive = date.fromisoformat(end_date_exclusive)
    days = (end_date_exclusive - start_date).days
    if start_date.weekday() or end_date_exclusive.weekday() or not 7 <= days <= 182:
        raise ValueError('Choose Monday boundaries covering 1 to 26 full calendar weeks.')
    if scope_type not in ('company', 'team', 'person', 'shared'):
        raise ValueError('Unknown forecast scope.')
    if scope_type == 'company' and scope_id not in (None, tenant_id):
        raise ValueError('Company scope_id must match the current company.')
    scope_id = scope_id or (tenant_id if scope_type == 'company' else None)
    if scope_id is None:
        raise ValueError('A named scope is required.')
    now = iso(service.now())
    today = datetime.fromisoformat(now.replace('Z', '+00:00')).date()
    dataset = 'forecast-targets:' + tenant_id
    scoped = (service.store.weekly_history_inputs(now, tenant_id, scope_type=scope_type, scope_id=scope_id)
              if hasattr(service.store, 'weekly_history_inputs') else None)
    records = scoped['records'] if scoped is not None else service.store.input_records(
        now, tenant_id, kinds=('issued_targets', 'truth_revisions'))
    targets = [row['payload'] for row in records if row['kind'] == 'issued_targets']
    truths = {}
    for record in records:
        if record['kind'] != 'truth_revisions': continue
        row = record['payload']
        # Store receipt-time filtering is necessary, but validate payload time too.
        if not isinstance(row.get('revision'), int) or row['revision'] < 1 or iso(row['available_at']) > now: continue
        old = truths.get(row['target_id'])
        if old is None or row['revision'] > old['revision']:
            truths[row['target_id']] = row
    runs = {}
    metadata = (service.store.weekly_publication_metadata(
        [t['run_id'] for t in targets], scope_type, scope_id) if scoped is not None else None)
    def published(target):
        run_id = target['run_id']
        if metadata is not None:
            return metadata.get(run_id, {}).get('published_at')
        if run_id not in runs:
            try: runs[run_id] = service.store.get_run(run_id)
            except KeyError: runs[run_id] = None
        run = runs[run_id]
        if run is None: return None  # shadow/reference are never serving runs
        view = next((v for v in run['bundle'].get('views', []) if v['scope']['type'] == scope_type
                     and v['scope'].get('id') == scope_id), None)
        if not view: return None
        return view.get('publication', {}).get('published_at')
    sequences = {}
    def publication_order(target):
        run_id = target['run_id']
        if metadata is not None:
            return (iso(target['issued_at']), iso(published(target)), metadata[run_id]['sequence'], target['target_id'])
        if run_id not in sequences:
            run = runs[run_id]
            sequences[run_id] = service.store.get_job(run['job_id'])['sequence']
        return (iso(target['issued_at']), iso(published(target)), sequences[run_id], target['target_id'])
    def dimensions(row, begin, end):
        expected = dict(quantity='spend', unit='USD', basis='planning', timezone='UTC',
                        scope_type=scope_type, scope_id=scope_id, start=str(begin), end=str(end))
        return all(row.get(key) == value for key, value in expected.items())
    def prospective(target, begin, end):
        if (target.get('aggregation') != 'weekly' or target.get('duration_days') != 7
                or not dimensions(target, begin, end) or amount(target.get('prediction')) is None
                or type(target.get('is_synthetic')) is not bool):
            return False
        stamp = str(begin) + 'T00:00:00Z'
        served = published(target)
        return bool(served and iso(served) <= iso(stamp) and iso(target['issued_at']) <= iso(stamp)
                    and iso(target.get('information_cutoff', target['issued_at'])) <= iso(stamp))
    if scoped is not None:
        view = service.store.weekly_current_view(scope_type, scope_id, tenant_id)
    else:
        current = service.views(scope_type=scope_type, scope_id=scope_id, include_current_actuals=False)
        view = next((v for v in current.get('views', []) if v['scope']['type'] == scope_type
                     and v['scope'].get('id') == scope_id), None)
    weeks = []
    for offset in range(0, days, 7):
        begin = start_date + timedelta(days=offset); end = begin + timedelta(days=7)
        state = 'closed' if end <= today else 'current' if begin <= today else 'future'
        eligible = [t for t in targets if prospective(t, begin, end)]
        selected = max(eligible, key=publication_order) if eligible else None
        prior = None if selected is None else dict(amount=amount(selected['prediction']), run_id=selected['run_id'],
            target_id=selected['target_id'], issued_at=iso(selected['issued_at']),
            information_cutoff=selected.get('information_cutoff'), start=str(begin), end_exclusive=str(end), dataset_id=dataset)
        relevant = [r for r in ledger.get('buckets', []) if str(begin) <= str(r['date']) < str(end)
                    and str(r['date']) <= str(today) and amount(r.get('recorded_spend')) is not None]
        actual = dict(amount=amount(sum((Decimal(str(r['recorded_spend'])) for r in relevant), Decimal(0))) if relevant else None,
            status='partial' if relevant else 'missing', source='repository_ledger' if relevant else 'none',
            dataset_id='repository-ledger' if relevant else None, revision=ledger.get('dataset_revision') if relevant else None,
            corrected=False, source_refs=sorted({ref for r in relevant for ref in r.get('source_refs', [])}))
        if state == 'future': actual.update(amount=None, status='future', source='none', dataset_id=None, revision=None, source_refs=[])
        variance = dict(amount=None, status='unavailable', reason='No forecast was published before this full week began.' if prior is None
                        else 'The week is not closed.' if state != 'closed' else 'A complete observed outcome for this exact issued target is not available.')
        truth = truths.get(selected['target_id']) if selected else None
        if truth is not None and state == 'closed':
            compatible = (dimensions(truth, begin, end) and truth.get('is_synthetic') == selected.get('is_synthetic')
                          and type(truth.get('is_synthetic')) is bool and truth.get('provenance', {}).get('kind') == 'observed'
                          and bool(truth.get('provenance', {}).get('reference')) and amount(truth.get('value')) is not None)
            settled = (compatible and truth.get('status') == 'mature' and truth.get('complete') is True
                       and iso(str(end)+'T00:00:00Z') <= iso(truth['mature_at']) <= now)
            status = 'mature' if settled else truth.get('status') if truth.get('status') in ('pending', 'disputed') else 'pending'
            actual.update(amount=amount(truth['value']) if settled else None, status=status, source='observed_outcome',
                          dataset_id=dataset, revision=str(truth['revision']), corrected=truth['revision'] > 1,
                          source_refs=[truth['source_id'], truth['provenance']['reference']] if compatible else [])
            if settled:
                variance.update(amount=amount(Decimal(actual['amount']) - Decimal(prior['amount'])), status='available', reason=None)
            else:
                variance['reason'] = ('The latest observed outcome does not match this issued target.' if not compatible else
                                      'The latest outcome is disputed.' if status == 'disputed' else 'The latest observed outcome is not yet settled.')
        outlook = None
        if state != 'closed' and view and all(view.get('target', {}).get(key) == value
                for key, value in {'unit':'USD', 'basis':'planning', 'quantity':'spend', 'timezone':'UTC'}.items()):
            point = next((p for p in view.get('weekly', []) if str(begin) <= p.get('start', '') < str(end)
                          and p.get('end') == str(end) and p.get('complete', True) and amount(p.get('base')) is not None), None)
            publication = view.get('publication', {})
            issued = publication.get('issued_at') or publication.get('published_at')
            if point and issued and iso(issued) <= now:
                outlook = dict(amount=amount(point['base']), run_id=view['run_id'], issued_at=iso(issued),
                    information_cutoff=publication.get('information_cutoff'), start=point['start'], end_exclusive=point['end'],
                    partial=point['start'] != str(begin), dataset_id=dataset)
        weeks.append(dict(start=str(begin), end_exclusive=str(end), state=state, actual=actual,
                          prior_forecast=prior, outlook=outlook, variance=variance))
    revision = identity({'ledger': ledger.get('dataset_revision'), 'truths': sorted(truths.items())})
    return dict(scope={'type':scope_type, 'id':scope_id}, start_date=str(start_date), end_date_exclusive=str(end_date_exclusive),
        timezone='UTC', unit='USD', basis='planning', quantity='spend', dataset_id='forecast-weekly:'+tenant_id,
        as_of=now, synthetic=bool(ledger.get('synthetic')) or (scoped['synthetic'] if scoped is not None else any(t.get('is_synthetic') for t in targets)), actuals_revision=revision,
        selection_policy='latest_published_before_week_start', weeks=weeks,
        notes=['Monday–Sunday weeks use UTC; end dates are exclusive.',
               'Prior forecasts are the latest serving publication actually issued before each full week began. Later reruns never backfill history.',
               'Positive variance means settled observed spend exceeded that exact prior forecast; current or unsettled weeks have no final variance.',
               'Recorded repository subtotals are partial and never substituted for an observed planning-target outcome.',
               'A newer pending or disputed outcome withdraws the older comparison. Issued forecasts remain immutable.'])
