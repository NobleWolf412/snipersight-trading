"""Run selected audit verification in a fresh, guarded Python process.

Usage: python -B backend/diagnostics/offline_verify.py backend|contracts|smoke|inputs
This prevents accidental transport/credential/store use by these trusted checks;
it is not a security sandbox for arbitrary or hostile Python extensions.
"""
import argparse
import json
import logging
import os
from pathlib import Path
import runpy
import sys
import tempfile
from urllib.parse import unquote, urlsplit
from urllib.request import url2pathname


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('backend', 'contracts', 'smoke', 'inputs'))
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[2]
    essentials = {k: v for k, v in os.environ.items() if k.upper() in {
        'SYSTEMROOT', 'WINDIR', 'TEMP', 'TMP', 'PATH', 'PATHEXT', 'COMSPEC',
    }}
    os.environ.clear()
    os.environ.update(essentials)
    os.environ.update(PYTHON_DOTENV_DISABLED='1', PYTEST_DISABLE_PLUGIN_AUTOLOAD='1')
    sys.dont_write_bytecode = True
    sys.path[:0] = [str(repo), str(repo/'backend')]
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')
    manifest = json.loads(Path(__file__).with_name('offline_checks.json').read_text(encoding='utf-8'))
    original_cwd = Path.cwd()
    with tempfile.TemporaryDirectory(prefix='snipersight-offline-') as directory:
        scratch = Path(directory).resolve()
        tempfile.tempdir = str(scratch)
        if args.mode == 'backend':
            # Older source-contract tests use cwd-relative paths. Copy only the
            # source they inspect; all imported production modules stay in repo.
            for relative in manifest['source_fixtures']:
                target = scratch/relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes((repo/relative).read_bytes())
        os.chdir(scratch)
        blocked = set()
        null_path = Path(os.devnull).resolve()

        def contained(path):
            if isinstance(path, int):
                return False
            try:
                return Path(os.fsdecode(path)).resolve().is_relative_to(scratch)
            except (TypeError, ValueError, OSError):
                return False

        def deny(event):
            blocked.add(event)
            raise PermissionError('offline verification denied '+event)

        def guard(event, values):
            if event in ('subprocess.Popen', 'os.system'):
                deny(event)
            if event in ('socket.connect', 'socket.bind'):
                address = values[1]
                if args.mode != 'backend' or not isinstance(address, tuple) or address[0] not in ('127.0.0.1', '::1'):
                    deny(event)
            if event == 'socket.getaddrinfo':
                if args.mode != 'backend' or values[0] not in ('127.0.0.1', '::1', 'localhost', None):
                    deny(event)
            if event == 'open':
                path, mode, flags = values
                if isinstance(path, (str, bytes, os.PathLike)):
                    name = Path(os.fsdecode(path)).name.lower()
                    if name == '.env' or name.startswith('.env.'):
                        deny('credential-file read')
                writing = flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND)
                is_null = isinstance(path, (str, bytes, os.PathLike)) and Path(os.fsdecode(path)).resolve() == null_path
                # fdopen wraps a descriptor whose named creation already passed
                # this guard (tempfile.mkstemp is used by the atomic journal).
                if writing and not isinstance(path, int) and not contained(path) and not is_null:
                    deny('write outside fixture directory')
            if event == 'sqlite3.connect':
                database = os.fsdecode(values[0])
                if database.startswith('file:'):
                    uri = urlsplit(database)
                    if uri.netloc:
                        deny('remote sqlite URI')
                    database = url2pathname(unquote(uri.path))
                if database != ':memory:' and not contained(database):
                    deny('sqlite outside fixture directory')
            if event in ('os.mkdir', 'os.remove', 'os.rmdir', 'os.chmod', 'os.utime', 'os.truncate'):
                if not contained(values[0]):
                    deny(event+' outside fixture directory')
            if event in ('os.rename', 'os.link', 'os.symlink'):
                if not contained(values[0]) or not contained(values[1]):
                    deny(event+' outside fixture directory')

        sys.addaudithook(guard)
        # Exercise denial events without performing the external operations.
        checks = [
            ('open', (str(repo/'.env.offline-probe'), 'r', 0)),
            ('open', (str(repo/'offline-write-probe'), 'w', os.O_WRONLY | os.O_CREAT)),
            ('sqlite3.connect', (str(repo/'backend/cache/telemetry.db'),)),
            ('sqlite3.connect', ((repo/'backend/cache/telemetry.db').as_uri()+'?mode=ro',)),
            ('socket.connect', (None, ('192.0.2.1', 443))),
            ('subprocess.Popen', ('offline-probe', [], None, None)),
            ('os.rename', (str(scratch/'source'), str(repo/'offline-write-probe'))),
        ]
        for event, values in checks:
            try:
                sys.audit(event, *values)
            except PermissionError:
                continue
            raise AssertionError('offline guard did not deny '+event)
        blocked.clear()
        print('[offline] seven guard-denial checks passed')
        print('[offline] environment cleared; external transport and child processes denied; fixture writes only')
        # Redirect default telemetry before importing any application consumers.
        # Explicit test database paths remain explicit and must pass the guard.
        from backend.bot.telemetry.storage import TelemetryStorage
        original_init = TelemetryStorage.__init__
        def fixture_storage(self, db_path=None):
            return original_init(self, db_path=db_path or str(scratch/'telemetry.db'))
        TelemetryStorage.__init__ = fixture_storage
        result = 0
        try:
            if args.mode == 'backend':
                import pytest
                result = pytest.main([str(repo/p) for p in manifest['tests']] + [
                    '-o', 'addopts=', '-p', 'no:cacheprovider', '-q', '--tb=short',
                ])
            elif args.mode == 'inputs':
                from backend.diagnostics.decision_inputs_diagnostic import inspect_inputs
                print(json.dumps(inspect_inputs(), indent=2))
            else:
                module = 'backend.diagnostics.' + ('capture_contracts' if args.mode == 'contracts' else 'pipeline_smoke')
                sys.argv = [module, 'diff' if args.mode == 'contracts' else 'verify']
                runpy.run_module(module, run_name='__main__')
        except SystemExit as error:
            result = error.code if isinstance(error.code, int) else 1
        finally:
            print('[offline] blocked operations:', sorted(blocked))
            logging.shutdown()
            os.chdir(original_cwd)
    return result


if __name__ == '__main__':
    raise SystemExit(main())
