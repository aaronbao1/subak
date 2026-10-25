"""Directory changes use the same receipt transaction as other repository inputs."""
from app.services.people import create_people
from app.forecasting.archive import resolve_material


def test_bound_directory_creation_is_archived_at_actual_write_cutoff(seeded, clock):
    svc=seeded.state.forecast_service
    before=clock.now().isoformat()
    clock.advance(minutes=1)
    with seeded.state.session_factory() as session:
        create_people(session,[{'id':'new-researcher','team':'research','name':'New Researcher','email':'new@northstar.example'}],clock=clock)
        session.commit()
    rows=[r for r in svc.store.input_records(clock.now().isoformat()) if r['kind']=='repository_state']
    with svc.store.transaction() as connection:
        latest=resolve_material(connection,rows[-1]['payload'],tenant_id='northstar')
    assert 'new-researcher' in {p['id'] for p in latest['people']}
    earlier_receipt=[r for r in svc.store.input_records(before) if r['kind']=='repository_state'][-1]
    with svc.store.transaction() as connection:
        earlier=resolve_material(connection,earlier_receipt['payload'],tenant_id='northstar')
    assert 'new-researcher' not in {p['id'] for p in earlier['people']}
    snapshot=svc.snapshot_factory(now=clock.now().isoformat(),as_of=True)
    assert 'new-researcher' in {p['id'] for p in snapshot['people']}
    assert snapshot['memberships']==[]
    assert snapshot['coverage']==[]


def test_directory_creation_and_receipt_roll_back_together(seeded, clock):
    from app.db.models import Person
    svc=seeded.state.forecast_service
    before=[r['id'] for r in svc.store.input_records(clock.now().isoformat())]
    with seeded.state.session_factory() as session:
        create_people(session,[{'id':'rollback-person','team':'research','name':'Rollback Person'}],clock=clock)
        session.rollback()
    assert [r['id'] for r in svc.store.input_records(clock.now().isoformat())]==before
    with seeded.state.session_factory() as session:
        assert session.get(Person,'rollback-person') is None
