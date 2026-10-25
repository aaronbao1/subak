"""Public export guards reject private payloads and mismatched financial receipts."""
from copy import deepcopy
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest


@pytest.fixture
def exporter():
    path = Path(__file__).parents[2] / 'datagen' / 'export_interactive_demo.py'
    spec = spec_from_file_location('interactive_demo_export_under_test', path)
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def payloads(exporter):
    period = {'start': '2026-10-01', 'end': '2026-12-31'}
    teams = [{'id': f'team-{i}'} for i in range(16)]
    people = [{'id': f'person-{i}', 'teamId': teams[i % 16]['id']} for i in range(130)]
    company_view = {
        'scope': {'type': 'company', 'id': 'northstar'}, 'run_id': 'issued-run', 'snapshot_id': 'issued-snapshot',
        'target': {'unit': 'USD', 'quantity': 'spend', 'basis': 'planning', 'timezone': 'UTC'},
        'quarter_outlook': {'start': '2026-10-01', 'end': '2027-01-01', 'complete': True,
                            'base': 464485.19875, 'recorded': 123300.08},
    }
    scoped_views = []
    forecasts = []
    for kind, rows in [('team', teams), ('person', people)]:
        for index, row in enumerate(rows):
            view = deepcopy(company_view)
            view['scope'] = {'type': kind, 'id': row['id']}
            view['quarter_outlook']['base'] = 464485.19875 if index == 0 else 0
            view['quarter_outlook']['recorded'] = 123300.08 if index == 0 else 0
            scoped_views.append(view)
            forecast = {'id': f'{kind}:{row["id"]}', 'teamId': row['id'] if kind == 'team' else row['teamId'],
                        'period': deepcopy(period), 'status': 'available', 'basis': 'full_period',
                        'kind': 'forecast', 'origin': 'forecasting_service', 'unit': 'usd',
                        'projected': 464485.20 if index == 0 else 0}
            if kind == 'person':
                forecast['personId'] = row['id']
            forecasts.append(forecast)
    shared = deepcopy(company_view)
    shared['scope'] = {'type': 'shared', 'id': 'unallocated'}
    shared['quarter_outlook'].update(base=0, recorded=0)
    return {
        'company': {'id': 'northstar', 'budgetUnit': 'usd', 'currentPeriod': period},
        'teams': teams,
        'people': people,
        'documents': [{'id': f'doc-{i}'} for i in range(249)],
        'budgets': [{'teamId': team['id'], 'allocated': '26875.00', 'unit': 'usd', 'version': 1,
                    'period': deepcopy(period)} for team in teams],
        'forecasts': forecasts,
        'spending': [
            {'amount': '3650.00', 'component': 'subscription', 'provenance': 'observed', 'date': '2026-10-01', 'unit': 'usd'},
            {'amount': '9128.34', 'component': 'overage', 'provenance': 'observed', 'date': '2026-10-02', 'unit': 'usd'},
            {'amount': '110521.74', 'component': 'api', 'provenance': 'observed', 'date': '2026-10-03', 'unit': 'usd'},
            {'amount': '999999.00', 'component': 'included_usage', 'provenance': 'usage_only', 'date': '2026-10-03', 'unit': 'usd'},
        ],
        'allocation-state': {'envelope_total': '430000.00', 'unit': 'USD', 'state_version': 1,
                             'period': {'start_date': '2026-10-01', 'end_date_exclusive': '2027-01-01'},
                             'allocations': [{'team_id': team['id'], 'amount': '26875.00'} for team in teams]},
        'forecast-views': {'run_id': 'issued-run', 'views': [company_view, *scoped_views, shared]},
        'proposals': [], 'decisions': [],
        'budget-requests': {'items': [
            {'client_request_id': key, 'requested_amount': None, 'status': 'submitted',
             'linked_proposal_ids': [], 'decision_ids': [], 'approved_amount': '0.00',
             'assessment': {'budget_version': 1, 'envelope_total': '430000.00',
                            'forecast_status': 'available', 'forecast_run_id': 'issued-run'}}
            for key in sorted(exporter.REQUEST_KEYS)]},
    }


def test_exact_generated_financial_snapshot_is_accepted(exporter, payloads):
    report = exporter.validate_finances(payloads)
    assert report['companyForecast'] == '464485.19875'
    assert report['recordedSpend'] == '123300.08'
    assert report['budgetEnvelope'] == '430000.00'
    assert report['forecastRunId'] == 'issued-run'
    assert report['inputSnapshotId'] == 'issued-snapshot'
    assert (report['teamCount'], report['personCount'], report['documentCount'], report['requestCount']) == (16, 130, 249, 3)


@pytest.mark.parametrize('path,replacement', [
    (('company', 'currentPeriod', 'start'), '2026-07-01'),
    (('allocation-state', 'period', 'end_date_exclusive'), '2026-12-31'),
    (('forecasts', 0, 'period', 'end'), '2027-03-31'),
    (('forecast-views', 'views', 0, 'quarter_outlook', 'end'), '2026-12-31'),
    (('forecast-views', 'views', 0, 'quarter_outlook', 'base'), 464485.20875),
    (('forecast-views', 'views', 0, 'quarter_outlook', 'recorded'), 123300.09),
    (('forecast-views', 'views', 0, 'quarter_outlook', 'complete'), False),
    (('forecast-views', 'views', 0, 'quarter_outlook', 'partial'), True),
    (('forecast-views', 'views', 0, 'run_id'), 'different-issuance'),
    (('forecast-views', 'views', 0, 'target', 'basis'), 'invoiced'),
    (('allocation-state', 'envelope_total'), '430000.01'),
    (('budgets', 0, 'allocated'), '26875.01'),
    (('spending', 0, 'amount'), '3650.01'),
    (('proposals',), [{'id': 'old-live-proposal'}]),
    (('decisions',), [{'id': 'old-live-decision'}]),
    (('budget-requests', 'items', 0, 'status'), 'approved_applied'),
    (('budget-requests', 'items', 0, 'requested_amount'), '50.00'),
    (('budget-requests', 'items', 0, 'approved_amount'), '50.00'),
    (('budget-requests', 'items', 0, 'linked_proposal_ids'), ['old-live-proposal']),
    (('budget-requests', 'items', 0, 'decision_ids'), ['old-live-decision']),
    (('documents', 1, 'id'), 'doc-0'),
    (('forecasts',), []),
    (('forecasts', 0, 'projected'), 464485.19),
    (('forecasts', 0, 'status'), 'unavailable'),
    (('forecasts', 0, 'unit'), 'credits'),
    (('allocation-state', 'allocations', 0, 'amount'), '26874.99'),
    (('spending', 0, 'date'), '2026-09-30'),
    (('spending', 0, 'date'), '2026-10-25'),
    (('spending', 0, 'unit'), 'credits'),
    (('forecast-views', 'views', 1, 'run_id'), 'different-issuance'),
    (('forecast-views', 'views', 1, 'snapshot_id'), 'different-snapshot'),
    (('forecast-views', 'views', 1, 'target', 'basis'), 'invoiced'),
    (('forecast-views', 'views', 1, 'quarter_outlook', 'start'), '2026-09-01'),
    (('budget-requests', 'items', 0, 'assessment', 'budget_version'), 2),
], ids=['wrong-quarter', 'inclusive-end', 'wrong-team-period', 'wrong-issued-end', 'wrong-forecast',
        'wrong-recorded', 'incomplete', 'partial', 'mixed-issuance', 'wrong-basis', 'wrong-envelope',
        'wrong-team-budget', 'wrong-ledger', 'proposal-history', 'decision-history', 'approved-request',
        'inferred-request-amount', 'funded-request', 'linked-proposal-history', 'linked-decision-history',
        'duplicate-documents', 'missing-forecasts', 'wrong-rounded-forecast', 'unavailable-has-projected',
        'wrong-forecast-unit', 'native-allocation-mismatch', 'prior-quarter-spend', 'future-spend',
        'wrong-spend-unit', 'mixed-team-issuance', 'mixed-team-snapshot', 'mixed-team-target',
        'wrong-team-outlook-period', 'stale-request-budget'])
def test_financial_receipt_mismatch_or_runtime_history_is_rejected(exporter, payloads, path, replacement):
    target = payloads
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = replacement
    with pytest.raises(AssertionError):
        exporter.validate_finances(payloads)


@pytest.mark.parametrize('kind', ['provider', 'factory', 'github', 'slack', 'aws', 'bearer', 'private-key',
                                 'named-field', 'jwt', 'url-userinfo', 'local-path', 'local-url', 'history-field'])
def test_secret_scan_reports_location_without_disclosing_value(exporter, capsys, kind):
    # Deliberately fake markers; tests never load local credential files.
    marker = 'not_a_real_credential_' * 3
    secrets = {'provider': 'sk-' + marker, 'factory': 'fk-' + marker, 'github': 'ghp_' + marker,
               'slack': 'xoxb-' + marker, 'aws': 'AKIA' + 'A' * 16, 'bearer': 'Bearer ' + marker,
               'private-key': '-----BEGIN PRIVATE KEY-----\n' + marker,
               'named-field': marker, 'jwt': 'eyJ' + 'A' * 20 + '.' + 'B' * 20 + '.' + 'C' * 20,
               'url-userinfo': 'https://demo:' + marker + '@example.invalid/path',
               'local-path': '/Users/fictional/' + marker,
               'local-url': 'http://127.0.0.1:8789/' + marker,
               'history-field': marker}
    secret = secrets[kind]
    key = {'named-field': 'factory_api_key', 'history-field': 'threads'}.get(kind, 'body')
    with pytest.raises(ValueError) as caught:
        exporter.scan_public_payloads({'documents': [{'metadata': {key: secret}}]})
    message = str(caught.value)
    assert f'documents[0].metadata.{key}' in message
    assert secret not in message and marker not in message
    output = capsys.readouterr()
    assert secret not in output.out + output.err


def test_generated_token_counts_and_empty_credentials_are_not_secret_matches(exporter):
    exporter.scan_public_payloads({'people': [{'email': 'fictional.person@uber.example'}],
                                  'usage': {'input_tokens': 123, 'output_tokens': 456},
                                  'empty': {'api_key': None, 'authorization': '', 'provider_usage': []}})


def test_native_half_up_rounding_and_unavailable_forecasts_are_preserved(exporter, payloads):
    payloads['forecast-views']['views'][1]['quarter_outlook']['base'] = 1.005
    payloads['forecasts'][0]['projected'] = 1.01
    payloads['forecasts'][1]['status'] = 'unavailable'
    payloads['forecasts'][1].pop('projected')
    exporter.validate_finances(payloads)
