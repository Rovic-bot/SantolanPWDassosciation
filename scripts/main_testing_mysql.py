"""Own MySQL instance for large fictional snapshots; never reconfigure port 3307."""
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import time
import MySQLdb
from scripts.local_mysql import MYSQL, ROOT

LOCAL = ROOT / '.local/main-testing'
DATA = LOCAL / 'mysql-data'
CONFIG = LOCAL / 'mysql.ini'
CREDENTIALS = LOCAL / 'mysql.json'
PORT = 3308
FLAGS = getattr(subprocess, 'CREATE_NO_WINDOW', 0)


def credentials():
    return json.loads(CREDENTIALS.read_text(encoding='utf-8'))


def connect():
    db = MySQLdb.connect(host='127.0.0.1', port=PORT, user='root', passwd=credentials()['password'], connect_timeout=5)
    with db.cursor() as cursor:
        cursor.execute('SELECT @@datadir, @@port, @@max_allowed_packet')
        datadir, port, packet = cursor.fetchone()
    assert Path(datadir).resolve() == DATA.resolve() and port == PORT and packet >= 256 * 1024 * 1024
    db.autocommit(True)
    return db


def start():
    with socket.socket() as probe:
        listening = probe.connect_ex(('127.0.0.1', PORT)) == 0
    if listening:
        connect().close()
        return
    initialize = not CREDENTIALS.exists()
    if initialize:
        assert not DATA.exists(), 'Do not overwrite an existing MySQL datadir'
        LOCAL.mkdir(parents=True, exist_ok=True)
        CONFIG.write_text('[mysqld]\n' + f'basedir="{MYSQL.as_posix()}"\ndatadir="{DATA.as_posix()}"\n'
            + f'port={PORT}\nbind-address=127.0.0.1\nmysqlx=OFF\n'
            + 'character-set-server=utf8mb4\ncollation-server=utf8mb4_0900_ai_ci\n'
            + 'max_allowed_packet=512M\nnet_read_timeout=180\nnet_write_timeout=180\n'
            + f'log-error="{(LOCAL / "mysql-error.log").as_posix()}"\n', encoding='utf-8')
        with (LOCAL / 'mysql-init.log').open('wb') as log:
            subprocess.run([str(MYSQL / 'bin/mysqld.exe'), f'--defaults-file={CONFIG}', '--initialize-insecure'],
                           stdout=log, stderr=log, check=True, creationflags=FLAGS)
    with (LOCAL / 'mysql-process.log').open('ab') as log:
        process = subprocess.Popen([str(MYSQL / 'bin/mysqld.exe'), f'--defaults-file={CONFIG}'],
            stdout=log, stderr=log, stdin=subprocess.DEVNULL, creationflags=FLAGS)
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        try:
            if initialize:
                db = MySQLdb.connect(host='127.0.0.1', port=PORT, user='root', connect_timeout=1)
                with db.cursor() as cursor:
                    cursor.execute('SELECT @@datadir')
                    assert Path(cursor.fetchone()[0]).resolve() == DATA.resolve()
                    password = secrets.token_urlsafe(36)
                    cursor.execute("ALTER USER 'root'@'localhost' IDENTIFIED BY %s", (password,))
                CREDENTIALS.write_text(json.dumps({'password': password}), encoding='utf-8')
                db.close()
            connect().close()
            print('Dedicated fictional MySQL ready on 127.0.0.1:3308; port 3307 unchanged.', flush=True)
            return
        except MySQLdb.Error:
            if process.poll() is not None:
                raise RuntimeError('Dedicated MySQL exited; inspect its private log.')
            time.sleep(.25)
    raise RuntimeError('Dedicated MySQL startup timed out')
