"""Server-only configuration and offline readiness must never expose credentials."""
from __future__ import annotations

import importlib
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest


def test_env_file_loads_server_values_without_overriding_process_or_loading_frontend(tmp_path):
    from app.runtime import load_backend_env

    path = tmp_path / '.env.local'
    path.write_text('export FACTORY_API_KEY="fixture-secret"\nDROID_RUNNER=sdk\n'
                    'DROID_MODEL="model with spaces" # comment\n'
                    'NEXT_PUBLIC_FACTORY_API_KEY=never-load\nPATH=/unsafe\n')
    env = {'DROID_RUNNER': 'fake'}
    loaded = load_backend_env(path, env=env)
    assert env == {'DROID_RUNNER': 'fake', 'FACTORY_API_KEY': 'fixture-secret',
                   'DROID_MODEL': 'model with spaces'}
    assert set(loaded) == {'FACTORY_API_KEY', 'DROID_MODEL'}


def test_env_loading_never_interpolates_or_executes_values(tmp_path):
    from app.runtime import load_backend_env

    marker = tmp_path / 'executed'
    path = tmp_path / '.env.local'
    path.write_text('FACTORY_API_KEY="${OTHER_SECRET}"\n'
                    f'DROID_MODEL="$(touch {marker})"\n')
    env = {'OTHER_SECRET': 'not-copied'}
    load_backend_env(path, env=env)
    assert env['FACTORY_API_KEY'] == '${OTHER_SECRET}'
    assert env['DROID_MODEL'] == f'$(touch {marker})'
    assert not marker.exists()


def test_malformed_env_is_atomic_and_does_not_echo_values(tmp_path):
    from app.runtime import BackendEnvError, load_backend_env

    path = tmp_path / '.env.local'
    path.write_text('DROID_RUNNER=sdk\nFACTORY_API_KEY="private-unclosed\n')
    env = {}
    with pytest.raises(BackendEnvError) as caught:
        load_backend_env(path, env=env)
    assert 'private-unclosed' not in str(caught.value)
    assert env == {}


def test_default_missing_env_is_optional_but_explicit_missing_file_errors(tmp_path, monkeypatch):
    from app import runtime

    monkeypatch.setattr(runtime, 'DEFAULT_ENV_FILE', tmp_path / 'missing')
    assert runtime.load_backend_env(env={}) == ()
    with pytest.raises(runtime.BackendEnvError):
        runtime.load_backend_env(tmp_path / 'explicitly-requested', env={})


def _sdk_imports(monkeypatch):
    from app import runtime

    def no_session(*args, **kwargs):
        pytest.fail('Readiness must not create a Factory session')

    sdk = SimpleNamespace(**{name: no_session for name in (
        'Session', 'SessionConfig', 'SessionTag', 'Autonomy', 'InteractionHandlers',
        'Runtime', 'ToolConfirmationOutcome')})
    mcp = SimpleNamespace(tool=no_session, create_sdk_mcp_server=no_session, ToolResponse=no_session)
    real_import = importlib.import_module
    monkeypatch.setattr(runtime.importlib, 'import_module',
                        lambda name: sdk if name == 'droid_sdk' else mcp if name == 'droid_sdk.mcp'
                        else real_import(name))
    monkeypatch.setattr(runtime.metadata, 'version', lambda name: '0.5.0')
    return sdk


def _version_cli(tmp_path: Path, output='0.249.0', exit_code=0):
    path = tmp_path / 'droid'
    path.write_text('#!/bin/sh\n'
                    'test "$1" = "--version" || exit 42\n'
                    'test -z "$FACTORY_API_KEY" || exit 43\n'
                    f'echo "{output}"\nexit {exit_code}\n')
    path.chmod(0o700)
    return path


def test_readiness_checks_sdk_and_cli_without_sessions_or_passing_key(tmp_path, monkeypatch):
    from app.runtime import check_droid_runtime

    _sdk_imports(monkeypatch)
    cli = _version_cli(tmp_path)
    monkeypatch.setenv('FACTORY_API_KEY', 'fixture-process-secret')
    report = check_droid_runtime({'FACTORY_API_KEY': 'fixture-request-secret', 'DROID_EXECUTABLE': str(cli)})
    assert report['ready'] is True
    assert report['credential_present'] is True
    assert report['sdk']['version'] == '0.5.0'
    assert report['cli']['version'] == '0.249.0'
    assert report['live_request_performed'] is False
    assert 'fixture-' not in json.dumps(report)


def test_blank_credential_is_unavailable_even_when_sdk_and_cli_exist(tmp_path, monkeypatch):
    from app.runtime import check_droid_runtime

    _sdk_imports(monkeypatch)
    report = check_droid_runtime({'FACTORY_API_KEY': '  ', 'DROID_EXECUTABLE': str(_version_cli(tmp_path))})
    assert report['ready'] is False
    assert report['issues'] == ['missing_api_key']


def test_sdk_api_mismatch_and_cli_diagnostics_do_not_escape(tmp_path, monkeypatch):
    from app.runtime import check_droid_runtime

    sdk = _sdk_imports(monkeypatch)
    del sdk.Session
    cli = _version_cli(tmp_path, output='private-cli-diagnostic', exit_code=1)
    report = check_droid_runtime({'FACTORY_API_KEY': 'fixture-secret', 'DROID_EXECUTABLE': str(cli)})
    assert report['ready'] is False
    assert 'sdk_api_mismatch' in report['issues']
    assert 'droid_cli_version_unavailable' in report['issues']
    assert report['cli']['version'] is None
    assert 'private-cli-diagnostic' not in json.dumps(report)


def test_check_command_reports_missing_credentials_without_creating_database(tmp_path):
    from app.runtime import SERVER_ENV_KEYS

    db = tmp_path / 'must-not-exist.db'
    env = tmp_path / '.env.local'
    env.write_text(f'BACKEND_DB_PATH="{db}"\nFACTORY_API_KEY=\nDROID_RUNNER=sdk\n')
    process_env = {key: value for key, value in os.environ.items() if key not in SERVER_ENV_KEYS}
    result = subprocess.run([sys.executable, '-m', 'app.launch', '--env-file', str(env), '--check-runtime'],
                            capture_output=True, text=True, check=False, env=process_env)
    assert result.returncode == 1
    report = json.loads(result.stdout)
    assert report['credential_present'] is False
    assert report['live_request_performed'] is False
    assert not db.exists()


def test_launcher_selects_sdk_independently_of_fixture_data(tmp_path, monkeypatch):
    from app.launch import main
    from app import runtime
    from fastapi.testclient import TestClient
    import uvicorn

    env = tmp_path / '.env.local'
    env.write_text(f'BACKEND_DB_PATH="{tmp_path / "app.db"}"\nFORECAST_DEMO=1\nFORECAST_WORKER=0\n')
    monkeypatch.setattr(runtime.os, 'environ', {})
    responses = []

    def serve(application, *, host, port):
        with TestClient(application) as client:
            responses.append(client.get('/api/meta').json())
        assert host == '127.0.0.1'
        assert port == 9999

    monkeypatch.setattr(uvicorn, 'run', serve)
    assert main(['--env-file', str(env), '--runner', 'sdk', '--port', '9999']) == 0
    assert responses[0]['runner_kind'] == 'sdk'
    assert next(row for row in responses[0]['real_vs_simulated'] if row['component'] == 'projections')['status'] == 'simulated'
