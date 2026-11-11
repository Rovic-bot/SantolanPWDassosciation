"""Start the verified local development site without creating or seeding data."""
import argparse
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from config.fresh_development import LOCAL, PURPOSE, load_manifest

FLAGS = getattr(subprocess, 'CREATE_NO_WINDOW', 0)


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def busy(port):
    with socket.socket() as probe:
        probe.settimeout(.3)
        return probe.connect_ex(('127.0.0.1', port)) == 0


def environment():
    result = dict(os.environ)
    result.update(DJANGO_SETTINGS_MODULE='config.current_development_settings',
        PYTHON_DOTENV_DISABLED='1', PYTHONUNBUFFERED='1', PYTHONIOENCODING='utf-8')
    return result


def verify_mysql(item):
    import MySQLdb
    db = MySQLdb.connect(host=item['host'], port=item['mysql_port'], user=item['user'],
        passwd=item['password'], db=item['database'], connect_timeout=3)
    try:
        with db.cursor() as cursor:
            cursor.execute('SELECT DATABASE(), @@port, @@datadir, @@server_uuid, @@bind_address')
            name, port, directory, identifier, bind = cursor.fetchone()
        if (name != item['database'] or port != item['mysql_port'] or identifier != item['server_uuid']
                or Path(directory).resolve() != Path(item['datadir']).resolve() or bind != '127.0.0.1'):
            raise RuntimeError('Unexpected MySQL identity. No alternate database will be used.')
    finally:
        db.close()


def start_mysql(item):
    if busy(item['mysql_port']):
        verify_mysql(item)
        return
    executable = ROOT / '.local/mysql-8.4.11-winx64/bin/mysqld.exe'
    configuration = ROOT / '.local/ewaf-twelve-demo/mysql.ini'
    with (LOCAL / 'mysql-process.log').open('ab') as log:
        process = subprocess.Popen([str(executable), f'--defaults-file={configuration}'],
            cwd=ROOT, stdin=subprocess.DEVNULL, stdout=log, stderr=log, creationflags=FLAGS)
    for _ in range(100):
        try:
            verify_mysql(item)
            return
        except Exception:
            if process.poll() is not None:
                raise RuntimeError('Local MySQL stopped. Inspect .local/development/mysql-process.log.')
            time.sleep(.25)
    raise RuntimeError('Local MySQL did not become available. No database was created or replaced.')


def health(item):
    try:
        with urllib.request.urlopen(f'http://127.0.0.1:{item["http_port"]}/__local__/health/', timeout=2) as response:
            result = json.load(response)
        if (result.get('purpose') == PURPOSE and result.get('instance_id') == item['instance_id']
                and result.get('database') == item['database']):
            return result
    except Exception:
        pass
    return None


def setup():
    item = load_manifest()
    start_mysql(item)
    os.environ.update(environment())
    import django
    django.setup()
    from django.db import connection
    from config.fresh_development import verify_connection
    verify_connection(connection=connection)
    return item


def require_migrations():
    from django.db import connection
    from django.db.migrations.executor import MigrationExecutor
    executor = MigrationExecutor(connection)
    executor.loader.check_consistent_history(connection)
    if executor.loader.detect_conflicts() or executor.migration_plan(executor.loader.graph.leaf_nodes()):
        raise RuntimeError('Required migrations are pending. Run manage.py migrate on the verified fresh database before startup.')


def start():
    item = setup()
    if item['state'] != 'ready':
        raise RuntimeError('Fresh database preparation has not completed. No older database will be used.')
    require_migrations()
    active = health(item)
    if not active:
        if busy(item['http_port']):
            raise RuntimeError('Port 8013 belongs to an unrecognized process; it was not stopped.')
        with (LOCAL / 'web.log').open('ab') as log:
            process = subprocess.Popen([sys.executable, '-B', str(Path(__file__).resolve()), '_serve'],
                cwd=ROOT, env=environment(), stdin=subprocess.DEVNULL, stdout=log,
                stderr=log, creationflags=FLAGS)
        for _ in range(120):
            active = health(item)
            if active:
                break
            if process.poll() is not None:
                raise RuntimeError('Development web server stopped. Inspect .local/development/web.log.')
            time.sleep(.25)
        if not active:
            raise RuntimeError('Development web server did not become available.')
    # Windows venv launchers may spawn the interpreter as a child process.
    # Retain the PID reported by the verified application, not the launcher PID.
    (LOCAL / 'server.json').write_text(json.dumps({'pid': active['pid'],
        'instance_id': item['instance_id']}, indent=2), encoding='utf-8')
    print(f'Local development: http://127.0.0.1:{item["http_port"]}/')
    print('Database:', item['database'])
    print('Admin login: http://127.0.0.1:8013/accounts/login/')
    print('Create your real administrator with: .venv\\Scripts\\python.exe manage.py createsuperuser')


def stop():
    item = load_manifest()
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
        if busy(item['http_port']):
            raise RuntimeError('Development server shutdown is still pending.')
    elif busy(item['http_port']):
        raise RuntimeError('The occupied web port could not be verified. No process was stopped.')
    print('Local website stopped. MySQL, both databases, and media remain saved.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('start', 'stop', 'restart', 'status', 'check', 'createsuperuser', '_serve'))
    action = parser.parse_args().action
    if action == 'start':
        start()
    elif action == 'stop':
        stop()
    elif action == 'restart':
        stop()
        start()
    elif action == 'status':
        item = load_manifest()
        print(f'Local development: http://127.0.0.1:{item["http_port"]}/')
        print('Database:', item['database'])
        print('Running:', bool(health(item)))
    else:
        item = setup()
        from django.core.management import call_command
        if action == '_serve':
            require_migrations()
            call_command('runserver', f'127.0.0.1:{item["http_port"]}', use_reloader=False)
        else:
            call_command(action, **({'databases': ['default']} if action == 'check' else {}))


if __name__ == '__main__':
    main()
