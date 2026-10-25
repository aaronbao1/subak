"""Conservative deterministic extraction of cited, absolute planning facts.

This deliberately bounded connector adapter is not an open-ended language model. Only
supported, unambiguous native fields or explicit prose grammars can change arithmetic.
Every rejected source remains visible as context; benchmark and release claims never
become adoption or token-reduction assumptions.
"""
from __future__ import annotations

import hashlib
import json
from copy import deepcopy
import math
import re
from datetime import date
from typing import Any

_DATE = r'(\d{4}-\d{2}-\d{2})'
_NUMBER = r'(\d+(?:\.\d+)?)'


def _entity(text: str, rows: list[dict], supplied: Any = None) -> str | None:
    mentioned = [r for r in rows if any(re.search(r'(?<!\w)' + re.escape(str(v)) + r'(?!\w)', text, re.I)
                                         for v in (r['id'], r.get('name', r['id'])))]
    if supplied is not None:
        matches = [r for r in rows if str(r['id']) == str(supplied)]
        if mentioned and (len(mentioned) != 1 or str(mentioned[0]['id']) != str(supplied)):
            return None
    else:
        matches = mentioned
    return str(matches[0]['id']) if len(matches) == 1 else None


def _finite(value: Any, *, minimum: float = 0) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= minimum


def _valid_date(value: Any) -> bool:
    try:
        date.fromisoformat(value)
        return True
    except (ValueError, TypeError):
        return False


def extract_event(envelope: dict, snapshot: dict) -> list[dict]:
    """Extract at most one supported absolute fact per connector envelope.

    Identities must resolve against the snapshot. Payload facts use provider fields,
    not externally supplied driver objects; text matches retain exact citation offsets.
    Dates ending a prose ``through`` range become exclusive the following day.
    """
    from datetime import timedelta

    text = str(envelope.get('text') or '')
    payload = envelope.get('payload') or {}
    if not isinstance(payload, dict):
        payload = {}
    source = envelope.get('source')
    revision = envelope.get('revision', 1)
    source_id = str(envelope.get('source_id', 'unknown'))
    scope: dict[str, Any] = {}
    parameters: dict[str, Any] = {'mode': 'absolute'}
    kind = 'workload'
    effective_from = None
    effective_to = None
    eligible = False
    reason = 'Unsupported or ambiguous statement; retained as context without numerical effect.'
    project = _entity(text, snapshot.get('projects', []), payload.get('project_id'))
    person = _entity(text, snapshot.get('people', []), payload.get('person_id'))
    configuration = _entity(text, snapshot.get('configurations', []), payload.get('configuration_id'))
    if project:
        scope['project_id'] = project

    # Provider-specific native schedule fields. A changed due date alone does not
    # identify the old workload interval, and is therefore insufficient.
    fields = payload.get('custom_fields', {}) if source == 'asana' else {}
    if source == 'monday':
        fields = payload.get('column_values', {})
    if isinstance(fields, list):
        fields = {str(f.get('name', f.get('id', ''))): f.get('text_value', f.get('text', f.get('value')))
                  for f in fields if isinstance(f, dict)}
    if not isinstance(fields, dict):
        fields = {}
    schedule = re.search(r'(?:move|shift)\s+.+?\s+from\s+' + _DATE + r'\s+(?:through|to)\s+' + _DATE
                         + r'\s+to\s+' + _DATE, text, re.I)
    adoption = re.search(r'will use\s+([\w.-]+)\s+for\s+' + _NUMBER + r'%\s+of\s+(?:requests|workloads)\s+from\s+'
                         + _DATE + r'(?:\s+through\s+' + _DATE + r')?', text, re.I)
    workload = re.search(r'workload\s+(?:is|will be|equals)\s+' + _NUMBER + r'\s+(work_units|requests)\s+(?:per day\s+)?from\s+'
                         + _DATE + r'(?:\s+through\s+' + _DATE + r')?', text, re.I)
    membership = re.search(r'(?:joins|moves to)\s+([\w.-]+)\s+(?:team\s+)?from\s+' + _DATE
                           + r'\s+at\s+' + _NUMBER + r'\s+exposure', text, re.I)
    pricing = re.search(r'([\w.-]+)\s+rate\s+is\s+USD\s+' + _NUMBER + r'\s+per\s+(tokens|requests)\s+from\s+' + _DATE, text, re.I)

    if source == 'model_release':
        kind = 'adoption'
        reason = 'Model release or benchmark only: no supported workload adoption, dates, or usage reduction.'
    elif project and all(k in fields for k in ('from_start', 'from_end', 'to_start')):
        kind = 'project_schedule'
        parameters.update({k: fields[k] for k in ('from_start', 'from_end', 'to_start')})
        eligible = all(_valid_date(fields[k]) for k in ('from_start','from_end','to_start'))
        if eligible:
            effective_from = min(fields['from_start'], fields['to_start'])
            if schedule:
                old_start, old_end, new_start = schedule.groups()
                if _valid_date(old_end):
                    old_end = (date.fromisoformat(old_end)+timedelta(days=1)).isoformat()
                if (old_start,old_end,new_start) != (fields['from_start'],fields['from_end'],fields['to_start']):
                    eligible = False
                    reason = 'Native schedule fields conflict with the cited prose.'
    elif schedule and project:
        kind = 'project_schedule'
        start, end, destination = schedule.groups()
        if _valid_date(end):
            end = (date.fromisoformat(end) + timedelta(days=1)).isoformat()
        parameters.update(from_start=start, from_end=end, to_start=destination)
        effective_from = min(start, destination)
        eligible = True
    elif adoption and project:
        kind = 'adoption'
        configuration = _entity(adoption.group(1), snapshot.get('configurations', []))
        parameters.update(configuration_id=configuration, share=float(adoption.group(2)) / 100)
        effective_from, effective_to = adoption.group(3), adoption.group(4)
        eligible = configuration is not None and parameters['share'] <= 1
    elif workload and project:
        kind = 'workload'
        unit = workload.group(2)
        # Requests are compatible only when observations explicitly declare that
        # exposure unit; no conversion from tokens, people or benchmark scores.
        compatible = snapshot.get('work_unit', 'work_units') == unit
        parameters.update(exposure=float(workload.group(1)), unit='work_units')
        effective_from, effective_to = workload.group(3), workload.group(4)
        eligible = compatible
        if not compatible:
            reason = 'Workload unit has no observed compatible rate; no conversion inferred.'
    elif membership and person:
        kind = 'membership'
        team = _entity(membership.group(1), snapshot.get('teams', []))
        scope = {'person_id': person}
        parameters.update(team_id=team, exposure=float(membership.group(3)))
        effective_from = membership.group(2)
        eligible = team is not None
    elif pricing:
        kind = 'pricing'
        pool, rate, unit, effective_from = pricing.groups()
        known = [p for p in snapshot.get('pricing', []) if p.get('billing_pool') == pool
                 and p.get('currency') == 'USD' and p.get('unit') == unit and p.get('complete_pool')]
        scope = {'billing_pool': pool}
        parameters.update(rate=float(rate), currency='USD', unit=unit)
        eligible = len(known) == 1 and known[0].get('mode') == 'linear'
        if not eligible:
            reason = 'Tariff replacement needs one compatible supported complete billing pool.'

    if effective_to and _valid_date(effective_to):
        effective_to = (date.fromisoformat(effective_to) + timedelta(days=1)).isoformat()
    if eligible and (not _valid_date(effective_from) or (effective_to and not _valid_date(effective_to))):
        eligible = False
        reason = 'Invalid or missing absolute effective dates.'
    if kind == 'project_schedule' and eligible:
        if not all(_valid_date(parameters[k]) for k in ('from_start', 'from_end', 'to_start')) or parameters['from_end'] <= parameters['from_start']:
            eligible = False
            reason = 'Project schedule must identify a nonempty old workload interval and new start.'
    if eligible and effective_to and effective_to <= effective_from:
        eligible = False
        reason = 'Effective range is reversed or empty.'
    assertion_count = sum(len(list(match.re.finditer(text)))
                          for match in (schedule,adoption,workload,membership,pricing) if match is not None)
    if assertion_count > 1:
        eligible = False
        reason = 'Multiple or conflicting fact assertions in one envelope require separate unambiguous source facts.'
    if eligible and kind in ('project_schedule', 'adoption', 'workload'):
        compatible_rows = [r for r in snapshot.get('observations', []) if r.get('project_id') == project
                           and _finite(r.get('exposure', r.get('work_units'))) and r.get('exposure', r.get('work_units')) > 0]
        if not compatible_rows:
            eligible = False
            reason = 'No observed compatible workload exposure; magnitude remains context only.'
    if eligible:
        reason = 'Explicit identified, effective-dated absolute state supported by compatible observed inputs.'
    if payload.get('conflicting') or payload.get('status') in ('conflicting', 'cancelled', 'informal') or re.search(r"\b(?:maybe|might|could|would|should|consider|proposed|proposal|hypothetical|cancelled|canceled|tentative|unconfirmed|if approved|do not|don't|not approved)\b", text, re.I):
        eligible = False
        reason = 'Conflicting, cancelled, informal or tentative evidence remains context only.'
    if source not in ('slack', 'asana', 'monday', 'model_release'):
        eligible = False
        reason = 'Unsupported connector source.'
    if not text or not envelope.get('source_id') or not envelope.get('revision') or not envelope.get('occurred_at') or not envelope.get('available_at'):
        eligible = False
        reason = 'Missing source timing/provenance.'
    key = f'{source}:{source_id}:{revision}:{kind}'
    driver = {'id': 'drv_' + hashlib.sha256(key.encode()).hexdigest()[:20], 'source_id': source_id,
              'source_revision': revision, 'source': source, 'occurred_at': envelope.get('occurred_at'),
              'available_at': envelope.get('available_at'), 'kind': kind, 'scope': scope,
              'effective_from': effective_from, 'effective_to': effective_to, 'parameters': parameters,
              'status': 'eligible' if eligible else 'context_only', 'reason': reason,
              'is_synthetic': bool(envelope.get('is_synthetic', False)),
              'citations': [{'source_id': source_id, 'source_revision': revision, 'quote': text,
                             'start': 0, 'end': len(text), 'url': payload.get('permalink')}]}
    if kind == 'project_schedule' and all(k in fields for k in ('from_start','from_end','to_start')):
        field_name = 'custom_fields' if source == 'asana' else 'column_values'
        value = deepcopy(payload.get(field_name))
        driver['citations'].append({'source_id':source_id,'source_revision':revision,
                                    'type':'structured_field','field_path':'payload.'+field_name,
                                    'value':value,'quote':json.dumps(value,sort_keys=True),
                                    'url':payload.get('permalink')})
    if payload.get('supersedes'):
        driver['supersedes'] = payload['supersedes']
    elif str(revision).isdigit():
        # A provider revision is replacement source state, never an incremental
        # multiplier. Link a higher numeric revision to the previously visible
        # fact even if the new version has become context-only.
        earlier = [d for d in snapshot.get('drivers', []) if d.get('source_id') == source_id
                   and d.get('source', source) == source and str(d.get('source_revision','')).isdigit()
                   and int(d['source_revision']) < int(revision)]
        if earlier:
            driver['supersedes'] = max(earlier,key=lambda d:int(d['source_revision']))['id']
    return [driver]
