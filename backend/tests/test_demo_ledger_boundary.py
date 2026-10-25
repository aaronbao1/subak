"""A synthetic forecast person's absent repository identity is never zero spend."""
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.config import Settings
from app.core.clock import FrozenClock, SequentialIdFactory
from app.main import create_app
from app.seed.northstar import seed


def test_demo_native_ledger_discloses_separate_source_and_rejects_person_zero(tmp_path):
    clock = FrozenClock(datetime(2026, 10, 24, 12, tzinfo=timezone.utc))
    app = create_app(Settings(db_path=tmp_path/'boundary.db', forecast_demo=True, forecast_worker=False),
                     clock=clock, id_factory=SequentialIdFactory())
    with app.state.session_factory() as session:
        seed(session, clock=clock, ids=app.state.id_factory)
    with TestClient(app) as client:
        assert client.get('/api/people/maya').status_code == 200
        records = client.get('/api/spend/records', params={'person': 'maya'})
        assert records.status_code == 422
        assert records.json()['error']['details']['reasons'][0]['code'] == 'person_not_in_repository_ledger'
        summary = client.get('/api/spend/summary').json()
        assert any('separate synthetic forecast fixture' in note for note in summary['notes'])
        compat = client.get('/compat/api/spending').json()
        assert sum(row['amount'] for row in compat if row.get('personId') == 'maya') > 0
