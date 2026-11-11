"""Run a Django command against fresh synthetic MySQL; never load project .env.

Usage: .venv/Scripts/python.exe scripts/g12_test_runner.py test ewaf --noinput
Requires the existing local MySQL binary, but never opens its existing datadir.
Logs and the disposable datadir are retained in the printed temporary directory.
"""
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import tempfile
import time

import MySQLdb


def main():
    # Browser/template assertions may contain Unicode names and punctuation.
    # A Windows console encoding must not abort the run before its test summary.
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    root = Path(__file__).resolve().parent.parent
    binary = root / '.local/mysql-8.4.11-winx64/bin/mysqld.exe'
    if not binary.is_file():
        raise RuntimeError('Disposable test prerequisite: local MySQL binary missing.')
    directory = Path(tempfile.mkdtemp(prefix='santolan-g12-tests-'))
    print(f'Synthetic test artifacts: {directory}', flush=True)
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        port = probe.getsockname()[1]
    datadir = directory / 'data'
    config = directory / 'mysql.ini'
    config.write_text('[mysqld]\n' +
        f'basedir="{binary.parent.parent.as_posix()}"\ndatadir="{datadir.as_posix()}"\n' +
        f'port={port}\nbind-address=127.0.0.1\nmysqlx=OFF\n' +
        'character-set-server=utf8mb4\ncollation-server=utf8mb4_0900_ai_ci\n' +
        'innodb-buffer-pool-size=32M\nperformance-schema=OFF\nmax-connections=30\n' +
        'table-open-cache=256\ntemptable-max-ram=32M\ntemptable-max-mmap=64M\n' +
        f'log-error="{(directory / "mysql-error.log").as_posix()}"\n', encoding='utf-8')
    flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
    env = {key: value for key, value in os.environ.items() if key.upper() in {
        'SYSTEMROOT', 'WINDIR', 'PATH', 'PATHEXT', 'TEMP', 'TMP', 'COMSPEC',
        'LOCALAPPDATA', 'APPDATA', 'USERPROFILE', 'PLAYWRIGHT_MODULE', 'CHROME_EXECUTABLE'}}
    env.update(PYTHON_DOTENV_DISABLED='1', SECRET_KEY=secrets.token_urlsafe(60), DEBUG='1',
        ALLOWED_HOSTS='localhost,127.0.0.1,testserver', DB_HOST='127.0.0.1', DB_PORT=str(port),
        DB_USER='g12_synthetic', DB_PASSWORD=secrets.token_urlsafe(32),
        DB_NAME='g12_empty', DB_TEST_NAME='test_g12_disposable', PDAO_ENFORCEMENT_ENABLED='0',
        DJANGO_SETTINGS_MODULE='config.settings', PYTHONUNBUFFERED='1', G12_ARTIFACT_DIR=str(directory))
    with (directory / 'initialize.log').open('wb') as output:
        subprocess.run([str(binary), f'--defaults-file={config}', '--initialize-insecure'],
            stdout=output, stderr=subprocess.STDOUT, check=True, env=env, creationflags=flags)
    server = subprocess.Popen([str(binary), f'--defaults-file={config}'], env=env, creationflags=flags)
    db = None
    try:
        for _ in range(120):
            try:
                db = MySQLdb.connect(host='127.0.0.1', port=port, user='root', connect_timeout=1)
                break
            except MySQLdb.Error:
                if server.poll() is not None:
                    raise RuntimeError('Disposable MySQL startup failed; inspect retained log.')
                time.sleep(.25)
        if db is None:
            raise RuntimeError('Disposable MySQL startup timed out.')
        with db.cursor() as cursor:
            cursor.execute('SELECT @@datadir, @@port')
            actual, actual_port = cursor.fetchone()
            if Path(actual).resolve() != datadir.resolve() or actual_port != port:
                raise RuntimeError('Refusing database access: disposable instance identity mismatch.')
            cursor.execute('SHOW DATABASES')
            if set(row[0] for row in cursor.fetchall()) - {'mysql', 'information_schema', 'performance_schema', 'sys'}:
                raise RuntimeError('Refusing nonempty database instance.')
            cursor.execute('CREATE DATABASE g12_empty CHARACTER SET utf8mb4')
            cursor.execute("CREATE USER 'g12_synthetic'@'localhost' IDENTIFIED BY %s", (env['DB_PASSWORD'],))
            for name in ('g12_empty', 'test_g12_disposable'):
                escaped = name.replace('_', '\\_')
                cursor.execute(f"GRANT ALL ON `{escaped}`.* TO 'g12_synthetic'@'localhost'")
        print('Verified fresh loopback MySQL datadir; .env disabled; isolated database grants.', flush=True)
        command = sys.argv[1:] or ['test', '--noinput']
        with (directory / 'django.log').open('w', encoding='utf-8') as log:
            process = subprocess.Popen([sys.executable, 'manage.py', *command], cwd=root, env=env,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8',
                errors='replace', creationflags=flags)
            for line in process.stdout:
                print(line, end='', flush=True)
                log.write(line)
            return process.wait()
    finally:
        if db:
            try:
                with db.cursor() as cursor:
                    cursor.execute('SHUTDOWN')
            finally:
                db.close()
        try:
            server.wait(timeout=20)
        except subprocess.TimeoutExpired:
            server.terminate()
            server.wait(timeout=10)


if __name__ == '__main__':
    sys.exit(main())
