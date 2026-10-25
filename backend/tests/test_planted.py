"""Planted-error pack (backend/seed/planted/) is caught exactly as backend/seed/answer_key.md says."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.seed import __main__ as seed_cli
from app.seed import planted
from app.seed.northstar import SPEND_FILE

EXPECTED_IDS = ["P0", "P1", "P1b", "P1c", "P2", "P2b", "P3", "P3b", "P4", "P5", "P5b", "P6"]


@pytest.fixture(scope="module")
def checks():
    return planted.run_planted_checks()


def test_every_planted_check_matches_the_answer_key(checks):
    assert [c.id for c in checks] == EXPECTED_IDS
    failed = [(c.id, c.expected, c.actual) for c in checks if not c.passed]
    assert failed == []


def test_answer_key_documents_every_check_and_file():
    key = planted.ANSWER_KEY.read_text(encoding="utf-8")
    for cid in EXPECTED_IDS:
        assert f"| {cid} |" in key, cid
    files = [p.name for p in planted.PLANTED_DIR.iterdir() if p.is_file()]
    files += [f"corpus/{p.name}" for p in planted.PLANTED_CORPUS_DIR.iterdir()]
    for name in files:
        assert name in key, name


def test_duplicate_file_is_byte_identical_to_seed_export_and_reexport_is_not():
    dup = planted.planted_path(planted.DUPLICATE_FILE).read_bytes()
    reexport = planted.planted_path(planted.REEXPORT_FILE).read_bytes()
    seed_bytes = SPEND_FILE.read_bytes()
    assert dup == seed_bytes
    assert reexport != seed_bytes and b"\r\n" in reexport


def test_outdated_proposal_file_is_a_valid_v1_transfer():
    body = json.loads(planted.planted_path(planted.OUTDATED_PROPOSAL_FILE).read_text())
    assert body["request"]["action_type"] == "transfer" and body["request"]["base_version"] == 1
    assert body["drafted_by"]["X-Actor-Role"] == "finance_analyst"


def test_planted_files_are_labeled_simulated():
    for p in planted.PLANTED_CORPUS_DIR.glob("*.md"):
        assert "is_simulated: true" in p.read_text()
    for item in planted.PLANTED_IMPORTS:
        text = planted.planted_path(item.filename).read_text()
        if item.source_kind == "northstar_billing":
            assert "simulated" in text
        else:
            assert item.form["value_kind_default"] == "simulated"


def test_with_planted_cli_is_idempotent_and_shows_incomplete_coverage(tmp_path, monkeypatch, capsys):
    db = tmp_path / "planted.db"
    monkeypatch.setenv("BACKEND_DB_PATH", str(db))
    assert seed_cli.main(["--with-planted"]) == 0
    assert seed_cli.main(["--with-planted"]) == 0
    out = capsys.readouterr().out
    second = out.split("already seeded")[1]
    assert "records_added=1" not in second and "records_added=3" not in second and "status=created" not in second

    app = create_app(Settings(db_path=db))
    try:
        with TestClient(app) as client:
            s = client.get("/api/spend/summary").json()
            assert s["attributed_total"] == "95000.00" and s["company_total"] == "96800.00"
            assert s["unattributed"]["recorded_spend"] == "1800.00" and s["coverage"]["status"] == "partial"
            assert len(client.get("/api/documents").json()["items"]) == 15
            budget = client.get("/api/budget").json()
            assert budget["state_version"] == 1 and budget["envelope_total"] == "200000.00"
            assert client.get("/api/proposals").json() == []  # the pack never drafts or decides by itself
    finally:
        app.state.engine.dispose()


def test_check_planted_cli_exit_code(capsys):
    assert seed_cli.main(["--check-planted"]) == 0
    assert f"{len(EXPECTED_IDS)}/{len(EXPECTED_IDS)} planted checks match" in capsys.readouterr().out


def test_edge_case_doc_references_only_existing_tests():
    import re
    from pathlib import Path

    tests_dir = Path(__file__).resolve().parent
    doc = (tests_dir.parent / "docs" / "edge-cases.md").read_text(encoding="utf-8")
    defined = set()
    for f in tests_dir.glob("test_*.py"):
        defined |= set(re.findall(r"^def (test_\w+)", f.read_text(encoding="utf-8"), re.MULTILINE))
    referenced = set(re.findall(r"`(test_\w+)`", doc))
    assert referenced and referenced <= defined, sorted(referenced - defined)
