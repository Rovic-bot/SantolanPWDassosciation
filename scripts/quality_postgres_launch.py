"""Fresh loopback PostgreSQL audit; no saved credentials or operational data."""
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import tempfile

import psycopg


def main():
    root = Path(__file__).resolve().parents[1]
    binary = Path(os.environ.get('QA_POSTGRES_BIN', 'C:/Program Files/PostgreSQL/18/bin'))
    folder = Path(tempfile.mkdtemp(prefix='santolan-pg-tests-'))
    password = secrets.token_urlsafe(32)
    password_file = folder / 'password'
    password_file.write_text(password)
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        port = probe.getsockname()[1]
    flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
    with (folder / 'setup.log').open('wb') as log:
        subprocess.run([str(binary / 'initdb.exe'), '-D', str(folder / 'data'), '-U', 'postgres',
                        '--auth=scram-sha-256', '--encoding=UTF8', '--locale=C', '--pwfile=' + str(password_file)],
                       stdout=log, stderr=log, creationflags=flags, check=True)
        password_file.unlink()
        subprocess.run([str(binary / 'pg_ctl.exe'), '-D', str(folder / 'data'), '-l', str(folder / 'postgres.log'),
                        '-o', f'-h 127.0.0.1 -p {port}', '-w', 'start'],
                       stdout=log, stderr=log, creationflags=flags, check=True)
    print('Disposable PostgreSQL artifacts:', folder, flush=True)
    try:
        with psycopg.connect(host='127.0.0.1', port=port, user='postgres', password=password,
                             dbname='postgres', autocommit=True) as db:
            assert Path(db.execute('SHOW data_directory').fetchone()[0]).resolve() == folder / 'data'
            db.execute('CREATE DATABASE pg_empty')
        env = {k: v for k, v in os.environ.items() if k.upper() in {
            'SYSTEMROOT', 'WINDIR', 'PATH', 'PATHEXT', 'TEMP', 'TMP', 'COMSPEC', 'LOCALAPPDATA', 'APPDATA', 'USERPROFILE',
            'PLAYWRIGHT_MODULE', 'CHROME_EXECUTABLE', 'CERTIFICATE_OFFICE_EXECUTABLE', 'QA_AXE_PATH'}}
        env.update(PYTHON_DOTENV_DISABLED='1', SECRET_KEY=secrets.token_urlsafe(60), DEBUG='1',
                   ALLOWED_HOSTS='localhost,127.0.0.1,testserver', DB_HOST='127.0.0.1', DB_PORT=str(port),
                   DB_USER='postgres', DB_PASSWORD=password, DB_ENGINE='postgresql', DB_NAME='pg_empty',
                   DB_TEST_NAME='test_pg_disposable', DJANGO_SETTINGS_MODULE='config.settings',
                   PG_TEST_ARTIFACT_DIR=str(folder), G12_ARTIFACT_DIR=str(folder), PYTHONUNBUFFERED='1')
        command = [sys.executable, 'manage.py', 'test', *sys.argv[1:], '--noinput']
        if not any(arg == '--testrunner' or arg.startswith('--testrunner=') for arg in sys.argv[1:]):
            command.append('--testrunner=scripts.quality_audit_runner.QualityPostgresAuditRunner')
        with (folder / 'django.log').open('wb') as log:
            result = subprocess.run(command,
                                    cwd=root, env=env, stdout=log, stderr=log, creationflags=flags)
        print('PostgreSQL test exit:', result.returncode, flush=True)
        return result.returncode
    finally:
        subprocess.run([str(binary / 'pg_ctl.exe'), '-D', str(folder / 'data'), '-m', 'fast', '-w', 'stop'],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=flags, check=True)


if __name__ == '__main__':
    sys.exit(main())
