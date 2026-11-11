"""Manage only this project's native MySQL development instance (Windows).

No system service, XAMPP changes, Docker, or global database grants.
Credentials and data stay in ignored .local/; never use this for production.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import socket
import subprocess
import sys
import time
import zipfile

import MySQLdb
from dotenv import dotenv_values, set_key

ROOT = Path(__file__).resolve().parent.parent
LOCAL = ROOT / '.local'
VERSION = '8.4.11'
MYSQL = LOCAL / f'mysql-{VERSION}-winx64'
DATA = LOCAL / 'mysql-data'
CONFIG = LOCAL / 'mysql.ini'
CREDENTIALS = LOCAL / 'mysql-admin.json'
PORT = 3307
FLAGS = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0


def credentials():
    if not CREDENTIALS.exists():
        raise RuntimeError('Local MySQL is not initialized. Run scripts/local_mysql.py init; see README.md.')
    return json.loads(CREDENTIALS.read_text(encoding='utf-8'))


def connect():
    return MySQLdb.connect(host='127.0.0.1', port=PORT, user='root',
                           passwd=credentials()['password'], connect_timeout=2)


def check_instance(db):
    with db.cursor() as cursor:
        cursor.execute('SELECT @@datadir')
        location = Path(cursor.fetchone()[0]).resolve()
    if location != DATA.resolve():
        raise RuntimeError('Port 3307 belongs to another database; refusing to manage it.')


def port_open():
    with socket.socket() as sock:
        sock.settimeout(1)
        return sock.connect_ex(('127.0.0.1', PORT)) == 0


def start(init_file=None):
    credentials()
    if port_open():
        db = connect()
        try:
            check_instance(db)
        finally:
            db.close()
        print('Project MySQL is already running on 127.0.0.1:3307.')
        return
    if not CONFIG.exists() or not (DATA / 'mysql').exists():
        raise RuntimeError('MySQL setup is incomplete. See README.md and .local/mysql-error.log.')
    command = [str(MYSQL / 'bin/mysqld.exe'), f'--defaults-file={CONFIG}']
    if init_file:
        command.append(f'--init-file={init_file}')
    with (LOCAL / 'mysql-process.log').open('ab') as log:
        process = subprocess.Popen(command, cwd=ROOT, stdin=subprocess.DEVNULL,
                                   stdout=log, stderr=log, creationflags=FLAGS)
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError('MySQL exited. Inspect .local/mysql-error.log.')
        try:
            db = connect()
            check_instance(db)
            db.close()
            print('Project MySQL is ready on 127.0.0.1:3307.')
            return
        except MySQLdb.Error:
            time.sleep(.5)
    raise RuntimeError('MySQL startup timed out. Inspect .local/mysql-error.log.')


def initialize():
    if DATA.exists() or CREDENTIALS.exists():
        raise RuntimeError('Existing local database setup found; init will not overwrite it. Use start.')
    if port_open():
        raise RuntimeError('Port 3307 is occupied. Stop and resolve the conflict before initialization.')
    env_path = ROOT / '.env'
    env = dotenv_values(env_path)
    for name in ('DB_NAME', 'DB_TEST_NAME', 'DB_USER'):
        if not re.fullmatch(r'[a-zA-Z0-9_]+', env.get(name, '')):
            raise RuntimeError(f'{name} must contain only letters, digits, or underscores.')
    if not env['DB_TEST_NAME'].startswith('test_') or env['DB_TEST_NAME'].casefold() == env['DB_NAME'].casefold():
        raise RuntimeError('A separate test_ database name is required.')
    if env['DB_USER'].casefold() == 'root':
        raise RuntimeError('Use a dedicated DB_USER, not root.')
    if not env.get('DB_PASSWORD'):
        raise RuntimeError('Set a nonempty DB_PASSWORD in .env first.')
    # MD5 published with the HTTPS MySQL download; also check ZIP CRCs.
    archive = LOCAL / 'downloads/mysql.zip'
    expected = '2e833921898a9a030ea6bfe81bd811bc'
    with archive.open('rb') as source:
        digest = hashlib.file_digest(source, 'md5').hexdigest()
    if digest != expected:
        raise RuntimeError('MySQL archive checksum mismatch or incomplete download; do not extract.')
    if not MYSQL.exists():
        with zipfile.ZipFile(archive) as bundle:
            for entry in bundle.infolist():
                destination = (LOCAL / entry.filename).resolve()
                if not destination.is_relative_to(LOCAL.resolve()):
                    raise RuntimeError('Unsafe archive entry.')
            if bundle.testzip() is not None:
                raise RuntimeError('MySQL archive CRC validation failed.')
            bundle.extractall(LOCAL)
    LOCAL.mkdir(exist_ok=True)
    root_password = secrets.token_urlsafe(36)
    CREDENTIALS.write_text(json.dumps({'password': root_password}), encoding='utf-8')
    CONFIG.write_text(
        '[mysqld]\n'
        f'basedir="{MYSQL.as_posix()}"\n'
        f'datadir="{DATA.as_posix()}"\n'
        f'port={PORT}\nbind-address=127.0.0.1\nmysqlx=OFF\n'
        'character-set-server=utf8mb4\ncollation-server=utf8mb4_0900_ai_ci\n'
        'default-storage-engine=InnoDB\n'
        'sql-mode=STRICT_TRANS_TABLES,NO_ENGINE_SUBSTITUTION\n'
        f'log-error="{(LOCAL / "mysql-error.log").as_posix()}"\n', encoding='utf-8')
    with (LOCAL / 'mysql-initialize.log').open('ab') as log:
        subprocess.run([str(MYSQL / 'bin/mysqld.exe'), f'--defaults-file={CONFIG}',
                        '--initialize-insecure'], check=True, stdout=log, stderr=log,
                       creationflags=FLAGS)
    def literal(value):
        return "'" + value.replace('\\', '\\\\').replace("'", "''") + "'"
    account = f"{literal(env['DB_USER'])}@'localhost'"
    database = env['DB_NAME']
    test_database = env['DB_TEST_NAME']
    init_file = LOCAL / 'mysql-bootstrap.sql'
    init_file.write_text(
        f"ALTER USER 'root'@'localhost' IDENTIFIED BY {literal(root_password)};\n"
        f'CREATE DATABASE `{database}` CHARACTER SET utf8mb4;\n'
        f"CREATE USER {account} IDENTIFIED BY {literal(env['DB_PASSWORD'])};\n"
        # Escape underscores: MySQL database-level GRANT names are patterns.
        f"GRANT ALL PRIVILEGES ON `{database.replace('_', chr(92) + '_')}`.* TO {account};\n"
        f"GRANT ALL PRIVILEGES ON `{test_database.replace('_', chr(92) + '_')}`.* TO {account};\n",
        encoding='utf-8')
    start(init_file)
    # Verify the application account before discarding the bootstrap SQL.
    app = MySQLdb.connect(host='127.0.0.1', port=PORT, user=env['DB_USER'],
                          passwd=env['DB_PASSWORD'], db=database, connect_timeout=5)
    app.close()
    init_file.unlink()
    set_key(str(env_path), 'DB_HOST', '127.0.0.1')
    set_key(str(env_path), 'DB_PORT', str(PORT))
    print('Application database and isolated test-database grants configured. .env updated.')


def stop():
    if not port_open():
        print('Project MySQL is already stopped.')
        return
    db = connect()
    try:
        check_instance(db)
        with db.cursor() as cursor:
            cursor.execute('SHUTDOWN')
    finally:
        db.close()
    deadline = time.monotonic() + 30
    while port_open() and time.monotonic() < deadline:
        time.sleep(.5)
    if port_open():
        raise RuntimeError('MySQL is still shutting down; inspect .local/mysql-error.log.')
    print('Project MySQL stopped cleanly.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['init', 'start', 'stop'])
    action = parser.parse_args().action
    try:
        {'init': initialize, 'start': start, 'stop': stop}[action]()
    except (RuntimeError, OSError, MySQLdb.Error, subprocess.SubprocessError) as error:
        # Never print connection parameters or SQL containing credentials.
        print(f'Local MySQL {action} failed: {error}', file=sys.stderr)
        sys.exit(1)
