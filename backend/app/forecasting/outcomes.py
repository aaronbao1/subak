"""Validated ingress for independently observed outcomes of issued targets.

This boundary accepts source attestations, not forecasts or inferred token costs.
Authentication and source verification belong to the integrating application.
"""
from copy import deepcopy
from datetime import date, datetime, timezone
import math

from .persistence import encode, iso

DIMENSIONS = ('quantity', 'unit', 'basis', 'timezone', 'scope_type', 'scope_id', 'start', 'end')
FIELDS = frozenset(DIMENSIONS + ('target_id', 'revision', 'available_at', 'mature_at',
                               'status', 'value', 'source_id', 'is_synthetic', 'complete', 'provenance'))


def ingest_outcome(service, envelope, *, tenant_id='northstar'):
    """Append a validated immutable truth revision with actual server receipt time.

    ``mature_at`` may be in the future; scoring continues to withhold that outcome
    until it matures. Pending/disputed corrections withdraw previous scores.
    """
    if not isinstance(envelope, dict):
        raise ValueError('observed outcome must be an object')
    missing = FIELDS - envelope.keys()
    extra = envelope.keys() - FIELDS
    if missing or extra:
        raise ValueError('observed outcome fields differ: missing=' + ','.join(sorted(missing))
                         + '; unsupported=' + ','.join(sorted(extra)))
    value = deepcopy(envelope)
    for key in ('target_id', 'source_id'):
        if not isinstance(value[key], str) or not value[key].strip():
            raise ValueError(key + ' must be a nonempty string')
    if type(value['revision']) is not int or value['revision'] < 1:
        raise ValueError('outcome revision must be a positive integer')
    if type(value['is_synthetic']) is not bool or type(value['complete']) is not bool:
        raise ValueError('outcome completeness and synthetic provenance must be explicit booleans')
    if value['status'] not in ('mature', 'pending', 'disputed'):
        raise ValueError('outcome status must be mature, pending or disputed')
    if value['status'] == 'mature' and not value['complete']:
        raise ValueError('mature observed outcomes require complete target coverage')
    amount = value['value']
    try:
        finite_amount = not isinstance(amount, bool) and isinstance(amount, (int, float)) and math.isfinite(amount)
    except OverflowError:
        finite_amount = False
    if not finite_amount:
        raise ValueError('outcome value must be finite and numerical')
    provenance = value['provenance']
    if (not isinstance(provenance, dict) or provenance.get('kind') != 'observed'
            or not isinstance(provenance.get('reference'), str) or not provenance['reference'].strip()):
        raise ValueError('observed provenance requires kind=observed and a nonempty source reference')
    try:
        encode(value)
    except (TypeError, ValueError) as exc:
        raise ValueError('outcome must contain finite JSON values') from exc

    now = iso(service.now())
    value['available_at'] = iso(value['available_at'])
    value['mature_at'] = iso(value['mature_at'])
    if value['available_at'] > now:
        raise ValueError('outcome cannot be available after server receipt time')
    if value['mature_at'] < value['available_at']:
        raise ValueError('outcome maturity cannot precede availability')
    record = service.store.find_input('issued_targets', value['target_id'], '1', tenant_id=tenant_id)
    if record is None:
        raise KeyError(value['target_id'])
    target = record['payload']
    if iso(target['issued_at']) > now:
        raise ValueError('outcome target has not been issued at server receipt time')
    quantity = target.get('quantity')
    if quantity is None and target.get('snapshot_id'):
        # Archives written before quantity became explicit retain their frozen
        # snapshot contract. Never infer a quantity from its currency or unit.
        try:
            quantity = service.store.get_snapshot(target['snapshot_id']).get('target', {}).get('quantity')
        except KeyError:
            pass
    expected = dict(target, quantity=quantity)
    for key in DIMENSIONS:
        if expected.get(key) is None or value[key] != expected[key]:
            raise ValueError('outcome ' + key + ' differs from exact issued target')
    if type(target.get('is_synthetic')) is not bool or value['is_synthetic'] != target['is_synthetic']:
        raise ValueError('outcome synthetic provenance differs from exact issued target')
    end = datetime.combine(date.fromisoformat(target['end']), datetime.min.time(), tzinfo=timezone.utc)
    if value['mature_at'] < iso(end):
        raise ValueError('outcome cannot mature before issued target period ends')
    stored = service.store.append_input('truth_revisions', value['target_id'], str(value['revision']), value,
                                        available_at=value['available_at'], received_at=now, tenant_id=tenant_id)
    return {'id': stored['id'], 'received_at': stored['received_at'], 'outcome': deepcopy(stored['payload'])}
