"""`python -m app.demo` journey against the in-process app with the fake runner (never Factory)."""

from __future__ import annotations

from app.demo import run_journey


def test_demo_journey_completes_on_seeded_app(seeded, client):
    lines: list[str] = []
    assert run_journey(client, out=lines.append), "\n".join(lines)
    text = "\n".join(lines)
    assert "runner: fake" in text
    assert "no apply / approve / decide / reject tool" in text
    assert "droid_agent approve -> 403 role_forbidden" in text
    assert "409 stale_proposal" in text
    assert lines[-1] == "journey complete"
    budget = client.get("/api/budget").json()
    assert budget["state_version"] == 3
    assert {a["team"]: a["amount"] for a in budget["allocations"]} == {
        "research": "120000.00", "product": "50000.00", "engineering": "80000.00"}
    assert budget["envelope_total"] == "250000.00"


def test_demo_journey_skip_interpret_still_completes(seeded, client):
    lines: list[str] = []
    assert run_journey(client, skip_interpret=True, out=lines.append), "\n".join(lines)
    assert not any("interprets" in line for line in lines)


def test_demo_journey_reports_failure_on_unseeded_app(client):
    lines: list[str] = []
    assert run_journey(client, out=lines.append) is False
    assert any("FAILED" in line for line in lines)
