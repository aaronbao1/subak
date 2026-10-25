from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

from app.db.models import Team


def test_company_updates_preserve_sources_are_idempotent_and_never_fund(seeded, client):
    path = Path(__file__).resolve().parents[2] / 'datagen/seed_company_updates.py'
    assert path.is_file(), 'The source-backed update seeder must exist'
    spec = spec_from_file_location('company_updates', path)
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    with seeded.state.session_factory() as session:
        for team in ('ai-labs', 'freight', 'payments-risk'):
            session.add(Team(id=team, name=team, created_at=seeded.state.clock.now()))
        session.commit()
    for key, team, project in module.UPDATES:
        result = client.post('/api/documents', headers=module.ANALYST, json={
            'doc_key': key, 'title': f'{project} update', 'doc_type': 'update',
            'authored_at': '2026-10-20T00:00:00Z', 'team_tags': [team],
            'content': f'Exact source narrative for {project}; no amount specified.', 'is_simulated': True})
        assert result.status_code == 201
    before = module.protected_state(seeded.state.settings.db_path)
    first = module.seed_requests(seeded, client)
    second = module.seed_requests(seeded, client)
    assert [row['id'] for row in first] == [row['id'] for row in second]
    assert module.protected_state(seeded.state.settings.db_path) == before
    for row in first:
        assert row['requested_amount'] is None
        assert row['status'] == 'submitted'
        assert row['linked_proposal_ids'] == [] and row['decision_ids'] == []
        assert row['narrative'] == f'Exact source narrative for {row["project_name"]}; no amount specified.'
        assert row['evidence_refs'][0]['kind'] == 'document'
        assert row['evidence_refs'][0]['id'] in row['source_ref']
