"""Provision and launch a persistent, isolated native-MySQL twelve-member demo."""
import argparse
import json
import os
from pathlib import Path
import secrets
import signal
import socket
import subprocess
import sys
import time
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parent.parent
LOCAL = ROOT / '.local/ewaf-twelve-demo'
MANIFEST = LOCAL / 'connection.json'
ADMIN = LOCAL / 'mysql-admin.json'
DATA = LOCAL / 'mysql-data'
CONFIG = LOCAL / 'mysql.ini'
MYSQL = ROOT / '.local/mysql-8.4.11-winx64'
PURPOSE = 'EWAF_TWELVE_PERSISTENT_DEMO'
DATABASE = 'santolan_ewaf_twelve_demo'
FLAGS = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
sys.path.insert(0, str(ROOT))


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write(path, value):
    path.write_text(json.dumps(value, indent=2), encoding='utf-8')


def busy(port):
    with socket.socket() as probe:
        probe.settimeout(.3)
        return probe.connect_ex(('127.0.0.1', port)) == 0


def free_port(start):
    for port in range(start, start + 20):
        if not busy(port):
            return port
    raise RuntimeError('No free dedicated local port is available.')


def environment():
    # No inheritance of DB credentials or ordinary .env. Real mail requires
    # an explicit local opt-in; ordinary development remains an outbox only.
    result = {key: value for key, value in os.environ.items() if key.upper() in {
        'SYSTEMROOT', 'WINDIR', 'PATH', 'PATHEXT', 'TEMP', 'TMP', 'COMSPEC',
        'LOCALAPPDATA', 'APPDATA', 'USERPROFILE', 'PLAYWRIGHT_MODULE', 'CHROME_EXECUTABLE'}}
    result.update(PYTHON_DOTENV_DISABLED='1', PYTHONUNBUFFERED='1', PYTHONIOENCODING='utf-8',
        DJANGO_SETTINGS_MODULE='config.current_development_settings')
    if os.environ.get('SANTOLAN_DIRECT_EMAIL') == '1':
        for key in ('EMAIL_HOST', 'EMAIL_PORT', 'EMAIL_HOST_USER', 'EMAIL_HOST_PASSWORD',
                    'EMAIL_USE_TLS', 'EMAIL_USE_SSL', 'EMAIL_TIMEOUT'):
            if key in os.environ:
                result[key] = os.environ[key]
        result['EMAIL_BACKEND'] = 'django.core.mail.backends.smtp.EmailBackend'
    if os.environ.get('CERTIFICATE_RESEND_ENABLED', '').lower() in ('1', 'true'):
        for key in ('CERTIFICATE_RESEND_ENABLED', 'RESEND_API_KEY', 'RESEND_FROM_EMAIL',
                    'CERTIFICATE_EMAIL_BACKGROUND'):
            if key in os.environ:
                result[key] = os.environ[key]
    return result


def checked_manifest():
    item = read(MANIFEST)
    if (item.get('purpose') != PURPOSE or item['database'] != DATABASE
            or Path(item['datadir']).resolve() != DATA.resolve()
            or Path(item['media']).resolve() != (LOCAL / 'private-media').resolve()):
        raise RuntimeError('Refusing a manifest outside the dedicated EWAF demo.')
    return item


def admin_connection():
    import MySQLdb
    credentials = read(ADMIN)
    db = MySQLdb.connect(host='127.0.0.1', port=credentials['port'], user='root',
        passwd=credentials['password'], connect_timeout=3)
    with db.cursor() as cursor:
        cursor.execute('SELECT @@datadir, @@port, @@server_uuid')
        datadir, port, server_uuid = cursor.fetchone()
    if (Path(datadir).resolve() != DATA.resolve() or port != credentials['port']
            or server_uuid != credentials['server_uuid']):
        db.close()
        raise RuntimeError('Refusing MySQL instance identity mismatch.')
    db.autocommit(True)
    return db


def start_mysql():
    credentials = read(ADMIN)
    if busy(credentials['port']):
        admin_connection().close()
        return
    with (LOCAL / 'mysql-process.log').open('ab') as log:
        process = subprocess.Popen([str(MYSQL / 'bin/mysqld.exe'), f'--defaults-file={CONFIG}'],
            cwd=ROOT, stdin=subprocess.DEVNULL, stdout=log, stderr=log, creationflags=FLAGS)
    for _ in range(120):
        try:
            admin_connection().close()
            return
        except Exception:
            if process.poll() is not None:
                raise RuntimeError('Demo MySQL stopped; inspect its dedicated logs.')
            time.sleep(.25)
    raise RuntimeError('Demo MySQL startup timed out.')


def application(command):
    with (LOCAL / (command + '.log')).open('ab') as log:
        result = subprocess.run([sys.executable, '-B', str(Path(__file__).resolve()), '_' + command],
            cwd=ROOT, env=environment(), stdout=log, stderr=log, creationflags=FLAGS)
    if result.returncode:
        raise RuntimeError('Demo ' + command + ' failed; inspect ' + str(LOCAL / (command + '.log')))


def create():
    if MANIFEST.exists():
        item = checked_manifest()
        if item.get('state') != 'ready':
            raise RuntimeError('An incomplete demo is retained. Inspect its bootstrap log; no automatic overwrite.')
        print('Existing EWAF demo retained; no records changed.')
        return
    if DATA.exists() or ADMIN.exists():
        raise RuntimeError('Refusing to overwrite an existing demo MySQL directory.')
    LOCAL.mkdir(parents=True, exist_ok=True)
    port, http_port = free_port(3309), free_port(8013)
    CONFIG.write_text('[mysqld]\n' + f'basedir="{MYSQL.as_posix()}"\ndatadir="{DATA.as_posix()}"\n'
        + f'port={port}\nbind-address=127.0.0.1\nmysqlx=OFF\n'
        + 'character-set-server=utf8mb4\ncollation-server=utf8mb4_0900_ai_ci\n'
        + f'log-error="{(LOCAL / "mysql-error.log").as_posix()}"\n', encoding='utf-8')
    with (LOCAL / 'initialize.log').open('wb') as log:
        subprocess.run([str(MYSQL / 'bin/mysqld.exe'), f'--defaults-file={CONFIG}', '--initialize-insecure'],
            stdout=log, stderr=log, check=True, creationflags=FLAGS)
    with (LOCAL / 'mysql-process.log').open('ab') as log:
        process = subprocess.Popen([str(MYSQL / 'bin/mysqld.exe'), f'--defaults-file={CONFIG}'],
            stdin=subprocess.DEVNULL, stdout=log, stderr=log, creationflags=FLAGS)
    import MySQLdb
    db = None
    for _ in range(120):
        try:
            db = MySQLdb.connect(host='127.0.0.1', port=port, user='root', connect_timeout=1)
            break
        except MySQLdb.Error:
            if process.poll() is not None:
                raise RuntimeError('Fresh demo MySQL failed to initialize.')
            time.sleep(.25)
    if db is None:
        raise RuntimeError('Fresh demo MySQL startup timed out.')
    with db.cursor() as cursor:
        cursor.execute('SELECT @@datadir, @@port, @@server_uuid')
        datadir, actual_port, server_uuid = cursor.fetchone()
        if Path(datadir).resolve() != DATA.resolve() or actual_port != port:
            raise RuntimeError('Refusing a foreign MySQL instance.')
        cursor.execute('SHOW DATABASES')
        if set(row[0] for row in cursor.fetchall()) - {'mysql', 'sys', 'information_schema', 'performance_schema'}:
            raise RuntimeError('Fresh instance is not empty.')
        admin_password = secrets.token_urlsafe(36)
        cursor.execute("ALTER USER 'root'@'localhost' IDENTIFIED BY %s", (admin_password,))
        write(ADMIN, {'port': port, 'server_uuid': server_uuid, 'password': admin_password})
        cursor.execute(f'CREATE DATABASE `{DATABASE}` CHARACTER SET utf8mb4')
        password = secrets.token_urlsafe(32)
        cursor.execute("CREATE USER 'ewaf_twelve'@'localhost' IDENTIFIED BY %s", (password,))
        escaped = DATABASE.replace('_', '\\_')
        cursor.execute(f"GRANT ALL ON `{escaped}`.* TO 'ewaf_twelve'@'localhost'")
    db.close()
    item = {'purpose': PURPOSE, 'state': 'created', 'database': DATABASE, 'user': 'ewaf_twelve',
        'password': password, 'secret': secrets.token_urlsafe(60), 'server_uuid': server_uuid,
        'instance_id': secrets.token_hex(24), 'mysql_port': port, 'http_port': http_port,
        'datadir': str(DATA.resolve()), 'media': str((LOCAL / 'private-media').resolve()),
        'admin_username': 'ewaf_demo', 'admin_password': 'EwafDemo-' + secrets.token_urlsafe(12)}
    write(MANIFEST, item)
    print('Verified fresh, separate MySQL. Preparing schema and synthetic fixtures...', flush=True)
    application('bootstrap')
    item['state'] = 'ready'
    write(MANIFEST, item)
    (LOCAL / 'LOGIN.txt').write_text(
        f'EWAF DEMO - FICTIONAL DATA ONLY\n\nURL: http://127.0.0.1:{http_port}/ewaf-demo/\n'
        + f'Username: {item["admin_username"]}\nPassword: {item["admin_password"]}\n\n'
        + 'Start with Start EWAF Demo.cmd. Stop with Stop EWAF Demo.cmd.\n'
        + 'Closing/restarting preserves this database. Normal Start System.cmd is unchanged.\n', encoding='utf-8')
    print('Created 12 members, 27 confirmed releases, and five ready EWAF programs.', flush=True)


def health(item):
    try:
        with urlopen(f'http://127.0.0.1:{item["http_port"]}/ewaf-demo/health/', timeout=1) as response:
            result = json.load(response)
        if result.get('purpose') == PURPOSE and result.get('instance_id') == item['instance_id']:
            return result
    except Exception:
        pass
    return None


def start():
    if not MANIFEST.exists():
        create()
    item = checked_manifest()
    if item.get('state') != 'ready':
        raise RuntimeError('The retained demo is incomplete; inspect bootstrap.log.')
    start_mysql()
    if not health(item):
        if busy(item['http_port']):
            raise RuntimeError('The demo HTTP port is used by another process; no process was stopped.')
        with (LOCAL / 'server.log').open('ab') as log:
            process = subprocess.Popen([sys.executable, '-B', str(Path(__file__).resolve()), '_serve'],
                cwd=ROOT, env=environment(), stdin=subprocess.DEVNULL, stdout=log, stderr=log, creationflags=FLAGS)
        for _ in range(100):
            active = health(item)
            if active:
                # Windows venv python.exe can delegate to a child interpreter.
                # Record the server that answered our own instance challenge.
                write(LOCAL / 'server.json', {'pid': active['pid'], 'launcher_pid': process.pid,
                    'instance_id': item['instance_id']})
                break
            if process.poll() is not None:
                raise RuntimeError('Demo web server failed; inspect its server.log.')
            time.sleep(.2)
        else:
            raise RuntimeError('Demo web server startup timed out.')
    print(f'Main development system is running: http://127.0.0.1:{item["http_port"]}/')
    print(f'Admin login: http://127.0.0.1:{item["http_port"]}/accounts/login/')
    print('Username:', item['admin_username'])
    print('Password is saved locally in:', LOCAL / 'LOGIN.txt')
    print('Your database and uploads remain saved after closing. Use Stop System.cmd to stop.')


def stop():
    item = checked_manifest()
    active = health(item)
    if active:
        recorded = read(LOCAL / 'server.json')
        if recorded['pid'] != active['pid'] or recorded['instance_id'] != item['instance_id']:
            raise RuntimeError('Refusing to stop an unrecognized server process.')
        os.kill(active['pid'], signal.SIGTERM)
        for _ in range(50):
            if not busy(item['http_port']):
                break
            time.sleep(.1)
    if busy(item['mysql_port']):
        db = admin_connection()
        try:
            with db.cursor() as cursor:
                cursor.execute('SELECT @@pid_file')
                pid_file = Path(cursor.fetchone()[0]).resolve()
                if pid_file.parent != DATA.resolve():
                    raise RuntimeError('Refusing an unexpected MySQL process file.')
                cursor.execute('SHUTDOWN')
        finally:
            db.close()
        for _ in range(120):
            if not pid_file.exists() and not busy(item['mysql_port']):
                break
            time.sleep(.25)
        else:
            raise RuntimeError('Demo shutdown is still pending; inspect its MySQL log.')
    print('Development system stopped. Its database, uploads and changes remain saved.')


def internal(command):
    os.environ.update(environment())
    import django
    django.setup()
    from django.core.management import call_command
    from django.db import connection
    from scripts.ewaf_twelve_demo_web import verify_connection
    verify_connection(connection=connection)
    if command == '_bootstrap':
        if connection.introspection.table_names():
            raise RuntimeError('Bootstrap requires a verified empty demo schema.')
        call_command('migrate', run_syncdb=True, interactive=False, verbosity=1)
        from scripts.ewaf_twelve_demo_seed import seed
        seed()
        call_command('check', databases=['default'])
    elif command == '_serve':
        item = checked_manifest()
        policy = LOCAL / 'registration-policy.json'
        if policy.exists():
            from django.conf import settings
            settings.ASSOCIATION_REGISTRATION_POLICY = read(policy)
        call_command('runlocal', f'127.0.0.1:{item["http_port"]}', use_reloader=False)
    else:
        raise RuntimeError('Unknown internal action.')


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['create', 'start', 'stop', '_bootstrap', '_serve'])
    args = parser.parse_args()
    if args.command.startswith('_'):
        internal(args.command)
    else:
        {'create': create, 'start': start, 'stop': stop}[args.command]()
