"""Server-only local configuration and offline Factory runtime checks.

This module never starts a Droid session. Reports contain credential presence only;
the CLI version subprocess receives no API key and its raw output is never reported.
"""
from __future__ import annotations

import importlib
from importlib import metadata
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
from collections.abc import Mapping, MutableMapping
from typing import Any

DEFAULT_ENV_FILE = Path(__file__).resolve().parents[2] / '.env.local'
SERVER_ENV_KEYS = frozenset({
    'FACTORY_API_KEY', 'DROID_RUNNER', 'DROID_EXECUTABLE', 'DROID_MODEL', 'DROID_TIMEOUT_S',
    'DROID_CHAT_MODEL', 'DROID_CHAT_REASONING_EFFORT', 'BACKEND_DB_PATH', 'BACKEND_PORT',
    'BACKEND_CORS_ORIGIN_REGEX', 'BACKEND_ALLOW_RESET', 'BACKEND_COMPAT',
    'FORECAST_PROVIDER', 'FORECAST_DEMO', 'FORECAST_WORKER',
})
_ASSIGNMENT = re.compile(r'^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$')
_VERSION = re.compile(r'\b(\d+\.\d+\.\d+(?:-[A-Za-z0-9.]+)?)\b')
_SDK_SYMBOLS = ('Session', 'SessionConfig', 'SessionTag', 'Autonomy', 'InteractionHandlers',
                'Runtime', 'ToolConfirmationOutcome')


class BackendEnvError(ValueError):
    """An invalid local backend configuration; messages never include values."""


def load_backend_env(path: str | Path | None = None, *,
                     env: MutableMapping[str, str] | None = None) -> tuple[str, ...]:
    """Load allowlisted server assignments, preserving process environment values.

    Supports single-line shell-style values, quotes, comments, and optional ``export``.
    No variable interpolation, command substitution, or shell execution occurs. Unknown
    keys (including every NEXT_PUBLIC_* key) are ignored. Parsing is atomic on errors.
    An absent default file is optional; an explicitly requested file must exist.
    """
    target = os.environ if env is None else env
    source = DEFAULT_ENV_FILE if path is None else Path(path).expanduser()
    if path is None and not source.exists():
        return ()
    try:
        lines = source.read_text(encoding='utf-8').splitlines()
    except (OSError, UnicodeError):
        raise BackendEnvError('The backend environment file could not be read.') from None
    pending: dict[str, str] = {}
    for line_number, line in enumerate(lines, start=1):
        match = _ASSIGNMENT.match(line)
        if match is None or match[1] not in SERVER_ENV_KEYS:
            continue
        key, raw = match.groups()
        try:
            values = shlex.split(raw, comments=True, posix=True)
        except ValueError:
            raise BackendEnvError(f'Invalid {key} assignment on line {line_number}.') from None
        if len(values) > 1:
            raise BackendEnvError(f'Quote the {key} value on line {line_number}.')
        pending[key] = values[0] if values else ''
    loaded = []
    for key, value in pending.items():
        if key not in target:
            target[key] = value
            loaded.append(key)
    return tuple(loaded)


def _droid_executable(env: Mapping[str, str]) -> str | None:
    configured = (env.get('DROID_EXECUTABLE') or '').strip()
    if configured:
        return shutil.which(str(Path(configured).expanduser()), path=env.get('PATH'))
    executable = shutil.which('droid', path=env.get('PATH'))
    if executable:
        return executable
    # The official installer uses this location even when the current shell's PATH
    # was initialized before installation.
    return shutil.which(str(Path.home() / '.local' / 'bin' / 'droid'))


def check_droid_runtime(env: Mapping[str, str] | None = None) -> dict[str, Any]:
    """Check installed SDK APIs and ``droid --version`` without a model request.

    Readiness confirms local prerequisites only. It does not authenticate the key,
    validate account credits, or prove that a live Factory session will succeed.
    """
    env = os.environ if env is None else env
    issues: list[str] = []
    credential_present = bool((env.get('FACTORY_API_KEY') or '').strip())
    if not credential_present:
        issues.append('missing_api_key')
    sdk_report: dict[str, Any] = {'installed': False, 'version': None,
                                  'api_compatible': False, 'mcp_available': False}
    try:
        sdk_report['version'] = metadata.version('droid-sdk')
        sdk = importlib.import_module('droid_sdk')
        sdk_report['installed'] = True
    except (metadata.PackageNotFoundError, ImportError):
        issues.append('sdk_not_installed')
    else:
        sdk_report['api_compatible'] = all(hasattr(sdk, name) for name in _SDK_SYMBOLS)
        if not sdk_report['api_compatible']:
            issues.append('sdk_api_mismatch')
        if sdk_report['version'] != '0.5.0':
            issues.append('sdk_version_mismatch')
        try:
            mcp = importlib.import_module('droid_sdk.mcp')
            sdk_report['mcp_available'] = all(hasattr(mcp, name) for name in
                                             ('tool', 'create_sdk_mcp_server', 'ToolResponse'))
        except ImportError:
            pass
        if not sdk_report['mcp_available']:
            issues.append('sdk_mcp_missing')
    executable = _droid_executable(env)
    cli_report: dict[str, Any] = {'available': bool(executable), 'executable': executable,
                                  'version': None}
    if not executable:
        issues.append('droid_cli_missing')
    else:
        # Keep only non-credential OS prerequisites. No local env-file values are
        # inherited by this offline version check, including FACTORY_API_KEY.
        child_env = {name: value for name, value in os.environ.items()
                     if name in {'PATH', 'HOME', 'TMPDIR', 'SYSTEMROOT'}}
        try:
            result = subprocess.run([executable, '--version'], capture_output=True, text=True,
                                    timeout=10, env=child_env, check=False)
            version = _VERSION.search(result.stdout) if result.returncode == 0 else None
            cli_report['version'] = version[1] if version else None
        except (OSError, subprocess.SubprocessError):
            pass
        if cli_report['version'] is None:
            issues.append('droid_cli_version_unavailable')
    return {'ready': not issues, 'credential_present': credential_present,
            'sdk': sdk_report, 'cli': cli_report, 'issues': issues,
            'live_request_performed': False}
