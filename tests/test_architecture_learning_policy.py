"""Frozen-gate counterexamples using simulated archive attestations.

The reused fixture's genuine flag exercises policy mechanics only; these tests
are synthetic and do not establish production accuracy or promotion eligibility.
"""
import pytest

from forecasting import learning
from test_learning import genuine_archive


@pytest.mark.parametrize('week_index', [0, 19, 20, 31])
@pytest.mark.parametrize('broken_value', ['prediction', 'truth'])
def test_candidate_conservation_failure_in_any_frozen_phase_blocks_promotion(week_index, broken_value):
    snapshot = {'is_synthetic': False, 'issued_targets': [], 'truth_revisions': []}
    registry = learning.update_model_registry(snapshot, generated_at='2024-01-01T00:00:00+00:00')
    observed = genuine_archive(snapshot, registry)
    target = next(row for row in observed['issued_targets']
                  if row['run_id'] == f'{week_index}:shadow' and row['aggregation'] == 'daily')
    if broken_value == 'prediction':
        target['prediction'] = 0.
    else:
        next(row for row in observed['truth_revisions'] if row['target_id'] == target['target_id'])['value'] = 0.
    result = learning.update_model_registry(observed, generated_at='2025-01-01T00:00:00+00:00')
    assert any(row['invariant_failures'] for row in result['evaluation_rows']
               if row['procedure_id'] == registry['shadow']['id'])
    assert result['decision']['promote'] is False
    assert result['serving'] == registry['serving']
    assert any('invariant' in reason for reason in result['decision']['reasons'])


@pytest.mark.parametrize('role', ['serving', 'shadow', 'reference'])
@pytest.mark.parametrize('week_index', [0, 19])
def test_incomplete_calibration_opportunity_for_any_procedure_blocks_promotion(role, week_index):
    snapshot = {'is_synthetic': False, 'issued_targets': [], 'truth_revisions': []}
    registry = learning.update_model_registry(snapshot, generated_at='2024-01-01T00:00:00+00:00')
    observed = genuine_archive(snapshot, registry)
    removed = next(row for row in observed['issued_targets']
                   if row['run_id'] == f'{week_index}:{role}' and row['aggregation'] == 'daily')
    observed['issued_targets'].remove(removed)
    result = learning.update_model_registry(observed, generated_at='2025-01-01T00:00:00+00:00')
    assert result['decision']['promote'] is False
    assert result['serving'] == registry['serving']


def test_valid_reconstructible_frozen_archive_control_can_promote():
    snapshot = {'is_synthetic': False, 'issued_targets': [], 'truth_revisions': []}
    registry = learning.update_model_registry(snapshot, generated_at='2024-01-01T00:00:00+00:00')
    observed = genuine_archive(snapshot, registry)
    result = learning.update_model_registry(observed, generated_at='2025-01-01T00:00:00+00:00')
    assert result['decision']['promote'] is True
    assert result['serving'] == registry['shadow']
