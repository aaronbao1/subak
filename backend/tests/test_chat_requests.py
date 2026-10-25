"""Durable acceptance, reconciliation and context across assistant requests."""
from concurrent.futures import ThreadPoolExecutor
from threading import Event

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.db.models import AgentRun

API = "/compat/api"


def post(client, content, key="client-1", **extra):
    return client.post(f"{API}/threads/main/messages", json={"content": content, "client_message_id": key, **extra})


def test_identical_request_replays_same_messages_and_proposal(seeded):
    with TestClient(seeded) as client:
        first = post(client, "add $50 for research")
        assert first.status_code == 200, first.text
        second = post(client, "add $50 for research")
        assert second.status_code == 200, second.text
        assert second.json() == first.json()
        assert first.json()[0]["clientMessageId"] == "client-1"
        assert len(client.get(f"{API}/threads/main").json()) == 2
        assert len(client.get(f"{API}/proposals").json()) == 1
        receipt = client.get(f"{API}/threads/main/messages/client-1")
        assert receipt.status_code == 200, receipt.text
        assert receipt.json() == {"status": "completed", "messages": first.json()}


def test_reuse_with_different_content_or_context_is_rejected(seeded):
    with TestClient(seeded) as client:
        assert post(client, "add $50 for research").status_code == 200
        for body in [{"content": "add $51 for research"},
                     {"content": "add $50 for research", "conversation_context": {"intent": "explain"}}]:
            result = client.post(f"{API}/threads/main/messages", json={"client_message_id": "client-1", **body})
            assert result.status_code == 409, result.text
            assert result.json()["code"] == "message_id_reused"
        assert len(client.get(f"{API}/proposals").json()) == 1


def test_request_identity_is_scoped_to_actor_and_thread(seeded):
    with TestClient(seeded) as client:
        first = post(client, "What is the budget?")
        assert first.status_code == 200
        other = {"X-Actor-Id": "other-analyst", "X-Actor-Role": "finance_analyst"}
        assert client.get(f"{API}/threads/main/messages/client-1", headers=other).status_code == 404
        assert client.get(f"{API}/threads/other/messages/client-1").status_code == 404
        result = client.post(f"{API}/threads/main/messages", headers=other,
                             json={"content": "What is the budget?", "client_message_id": "client-1"})
        assert result.status_code == 200 and result.json()[0]["id"] != first.json()[0]["id"]


def test_concurrent_retry_reconciles_without_duplicate_run(seeded):
    from app.agent.fake_runner import FakeDroidRunner

    entered, release = Event(), Event()
    delegate = FakeDroidRunner()

    class HeldRunner:
        kind = "fake"
        def run(self, task, tools):
            entered.set()
            assert release.wait(10)
            return delegate.run(task, tools)

    seeded.state.droid_runner = HeldRunner()
    with TestClient(seeded) as client, ThreadPoolExecutor(max_workers=2) as pool:
        future = pool.submit(post, client, "add $50 for research")
        try:
            assert entered.wait(5)
            pending = client.get(f"{API}/threads/main/messages/client-1")
            assert pending.status_code == 200, pending.text
            assert pending.json()["status"] == "pending"
            retry = post(client, "add $50 for research")
            assert retry.status_code == 409 and retry.json()["code"] == "message_pending", retry.text
        finally:
            release.set()
        first = future.result(timeout=10)
        assert first.status_code == 200, first.text
        assert post(client, "add $50 for research").json() == first.json()
        assert len(client.get(f"{API}/threads/main").json()) == 2
        with seeded.state.session_factory() as session:
            assert session.scalar(select(func.count()).select_from(AgentRun)) == 1


def test_pending_amount_survives_another_request_without_client_context(seeded):
    with TestClient(seeded) as client:
        question = post(client, "Add funding for research", "ask").json()[-1]
        assert question["conversationContext"]["pending_slot"] == "amount"
        response = post(client, "50k", "answer")
        assert response.status_code == 200, response.text
        pid = response.json()[-1]["proposalId"]
        proposal = client.get(f"{API}/proposals/{pid}").json()
        assert proposal["addedAmount"] == 50000


def test_selected_proposal_context_targets_revision_among_multiple(seeded):
    with TestClient(seeded) as client:
        first = post(client, "add $50 for research", "one").json()[-1]["proposalId"]
        other = post(client, "add $60 for product", "two").json()[-1]["proposalId"]
        revised = post(client, "Make it 40k instead", "revise", conversation_context={
            "intent": "allocation", "selected_proposal_id": first, "selected_proposal_version": 1})
        assert revised.status_code == 200, revised.text
        pid = revised.json()[-1]["proposalId"]
        proposal = client.get(f"{API}/proposals/{pid}").json()
        assert proposal["revisesProposalId"] == first and proposal["addedAmount"] == 40000
        assert client.get(f"{API}/proposals/{other}").json()["status"] == "proposed"


def test_reconnect_recovers_completed_run_after_response_interruption(seeded, monkeypatch):
    from app.compat import router

    complete = router._complete_request
    interrupted = False

    def lose_response(*args, **kwargs):
        nonlocal interrupted
        if not interrupted:
            interrupted = True
            raise RuntimeError("connection ended after agent completed")
        return complete(*args, **kwargs)

    monkeypatch.setattr(router, "_complete_request", lose_response)
    with TestClient(seeded, raise_server_exceptions=False) as client:
        assert post(client, "add $50 for research").status_code == 500
        with ThreadPoolExecutor(max_workers=2) as pool:
            calls = [pool.submit(client.get, f"{API}/threads/main/messages/client-1") for _ in range(2)]
            receipts = [call.result(timeout=10) for call in calls]
        assert all(receipt.status_code == 200 for receipt in receipts)
        assert receipts[0].json() == receipts[1].json()
        assert receipts[0].json()["status"] == "completed"
        assert post(client, "add $50 for research").json() == receipts[0].json()["messages"]
        assert len(client.get(f"{API}/threads/main").json()) == 2
        assert len(client.get(f"{API}/proposals").json()) == 1


def test_explicit_context_clear_does_not_restore_pending_amount(seeded):
    with TestClient(seeded) as client:
        assert post(client, "Add funding for research", "ask").json()[-1]["conversationContext"]["pending_slot"] == "amount"
        response = post(client, "50k", "answer", conversation_context={})
        assert response.status_code == 200, response.text
        assert "proposalId" not in response.json()[-1]
        assert client.get(f"{API}/proposals").json() == []


def test_explicit_allocation_is_not_swallowed_by_pinned_forecast(seeded):
    with TestClient(seeded) as client:
        response = post(client, "add $50 for research", conversation_context={"intent": "explain"},
            forecast_context={"run_id": "nonexistent-pinned-run", "scope_type": "company", "action": "explain"})
        assert response.status_code == 200, response.text
        proposal = client.get(f"{API}/proposals/{response.json()[-1]['proposalId']}").json()
        assert proposal["addedAmount"] == 50


def test_preparation_failure_leaves_identity_available_for_retry(seeded, monkeypatch):
    from app.compat import router

    prepare = router._intent_context
    def unavailable(*args, **kwargs):
        raise RuntimeError("temporary provider lookup failure")

    with TestClient(seeded, raise_server_exceptions=False) as client:
        monkeypatch.setattr(router, "_intent_context", unavailable)
        assert post(client, "add $50 for research").status_code == 500
        assert client.get(f"{API}/threads/main/messages/client-1").status_code == 404
        assert client.get(f"{API}/threads/main").json() == []
        monkeypatch.setattr(router, "_intent_context", prepare)
        assert post(client, "add $50 for research").status_code == 200
        assert len(client.get(f"{API}/proposals").json()) == 1


def test_accepted_request_recovers_if_interrupted_before_run_creation(seeded, monkeypatch):
    from app.compat import router

    start = router._start_request
    def interrupted(*args, **kwargs):
        raise RuntimeError("process interrupted before run creation")

    with TestClient(seeded, raise_server_exceptions=False) as client:
        monkeypatch.setattr(router, "_start_request", interrupted)
        assert post(client, "add $50 for research").status_code == 500
        monkeypatch.setattr(router, "_start_request", start)
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(client.get, f"{API}/threads/main/messages/client-1") for _ in range(2)]
            receipts = [future.result(timeout=10) for future in futures]
        assert all(response.status_code == 200 for response in receipts)
        completed = client.get(f"{API}/threads/main/messages/client-1")
        assert completed.json()["status"] == "completed", completed.text
        assert post(client, "add $50 for research").json() == completed.json()["messages"]
        assert len(client.get(f"{API}/proposals").json()) == 1
        with seeded.state.session_factory() as session:
            assert session.scalar(select(func.count()).select_from(AgentRun)) == 1


def test_explicit_transfer_after_applying_selected_draft_starts_a_new_proposal(seeded):
    with TestClient(seeded) as client:
        first = post(client, "add $50 for research", "first").json()[-1]["proposalId"]
        revision = post(client, "Make it $40 instead", "revise", conversation_context={
            "intent": "allocation", "selected_proposal_id": first, "selected_proposal_version": 1}).json()[-1]
        applied = revision["proposalId"]
        assert client.post(f"{API}/proposals/{applied}/apply", json={}).status_code == 200
        response = post(client, "Move $50 from Product to Research without adding funding", "transfer",
                        conversation_context=revision["conversationContext"])
        assert response.status_code == 200, response.text
        new_id = response.json()[-1]["proposalId"]
        proposal = client.get(f"{API}/proposals/{new_id}").json()
        assert proposal["kind"] == "redistribute" and proposal["totalAfter"] == proposal["totalBefore"]
        assert "revisesProposalId" not in proposal
        assert client.get(f"{API}/proposals/{applied}").json()["status"] == "applied"
