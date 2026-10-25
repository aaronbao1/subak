"""Launch the repository backend with server-only local environment configuration.

Run ``python -m app.launch --check-runtime`` for an offline Factory prerequisite
check. The check creates no database, server, or Droid session.
"""
from __future__ import annotations

import argparse
from dataclasses import replace
import json
from pathlib import Path
from typing import Sequence

from app.config import Settings, SettingsError
from app.runtime import BackendEnvError, check_droid_runtime, load_backend_env


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env-file', type=Path, help='Backend-only env file (default: repository .env.local).')
    parser.add_argument('--check-runtime', action='store_true', help='Check local Factory prerequisites without a live request.')
    parser.add_argument('--runner', choices=('fake', 'sdk'), help='Override DROID_RUNNER independently of data mode.')
    parser.add_argument('--port', type=int, help='Override BACKEND_PORT.')
    args = parser.parse_args(argv)
    try:
        load_backend_env(args.env_file)
    except BackendEnvError as exc:
        parser.exit(2, f'{exc}\n')
    if args.check_runtime:
        report = check_droid_runtime()
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0 if report['ready'] else 1
    try:
        settings = Settings.from_env()
    except SettingsError:
        parser.exit(2, 'Invalid backend configuration; check the server environment settings.\n')
    if args.port is not None:
        if not 1 <= args.port <= 65535:
            parser.exit(2, 'The backend port must be between 1 and 65535.\n')
        settings = replace(settings, port=args.port)
    if args.runner is not None:
        settings = replace(settings, droid_runner=args.runner)
    import uvicorn
    from app.main import create_app

    uvicorn.run(create_app(settings), host='127.0.0.1', port=settings.port)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
