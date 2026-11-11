"""Provision/start/restore the isolated port-8000 fictional workspace, retaining old DBs."""
import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from scripts import local_mysql
from dotenv import dotenv_values

LOCAL = ROOT / '.local/main-testing'
MANIFEST = LOCAL / 'connection.json'
RUNTIME = LOCAL / 'runtime'
FLAGS = getattr(subprocess, 'CREATE_NO_WINDOW', 0)


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, default=str), encoding='utf-8')


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def admin(*, preserved=False):
    if not preserved and (LOCAL / 'mysql.json').exists():
        from scripts.main_testing_mysql import connect
        return connect()
    db = local_mysql.connect()
    local_mysql.check_instance(db)
    db.autocommit(True)
    return db


def fingerprint(db, name):
    result = {}
    with db.cursor() as cursor:
        cursor.execute('SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA=%s ORDER BY TABLE_NAME', (name,))
        tables = [row[0] for row in cursor.fetchall()]
        for table in tables:
            cursor.execute(f'SELECT * FROM `{name}`.`{table}`')
            columns = [row[0] for row in cursor.description]
            rows = sorted(hashlib.sha256(json.dumps(row, default=str).encode()).hexdigest() for row in cursor.fetchall())
            result[table] = {'columns': columns, 'rows': rows}
    return result


def client(binary, name, file, *, restore=False):
    env = os.environ.copy()
    dedicated = name.startswith('santolan_lab_') and (LOCAL / 'mysql.json').exists()
    from scripts import main_testing_mysql
    env['MYSQL_PWD'] = (main_testing_mysql.credentials() if dedicated else local_mysql.credentials())['password']
    command = [str(local_mysql.MYSQL / 'bin' / binary), '--no-defaults', '--host=127.0.0.1',
               '--port=' + ('3308' if dedicated else '3307'), '--user=root', '--default-character-set=utf8mb4', '--max-allowed-packet=512M']
    if not restore:
        command += ['--single-transaction', '--skip-lock-tables', '--no-tablespaces', '--set-gtid-purged=OFF',
                    '--hex-blob', '--routines', '--events', '--triggers', '--skip-add-drop-table']
    with file.open('rb' if restore else 'wb') as stream, (LOCAL / 'mysql-private.log').open('ab') as log:
        result = subprocess.run([*command, name], env=env,
            stdin=stream if restore else subprocess.DEVNULL, stdout=subprocess.DEVNULL if restore else stream,
            stderr=log, creationflags=FLAGS)
    if result.returncode:
        raise RuntimeError('MySQL backup/restore failed; inspect .local/main-testing/mysql-private.log')


def source_backup():
    env = dotenv_values(ROOT / '.env')
    assert env['DB_HOST'] == '127.0.0.1' and str(env['DB_PORT']) == '3307'
    db = admin(preserved=True)
    names = {env['DB_NAME']}
    demo = ROOT / '.local/demo/connection.json'
    if demo.exists():
        names.add(json.loads(demo.read_text())['database'])
    directory = LOCAL / 'preserved'
    directory.mkdir(parents=True, exist_ok=False)
    try:
        for name in sorted(names):
            assert name.replace('_', '').isalnum()
            before = fingerprint(db, name)
            dump = directory / (name + '.sql')
            client('mysqldump.exe', name, dump)
            assert dump.stat().st_size and before == fingerprint(db, name)
            write(directory / (name + '.json'), {'database': name, 'fingerprint': before, 'sha256': sha(dump)})
            print(f'Preserved {name}: {len(before)} tables; SQL backup checksum verified.', flush=True)
    finally:
        db.close()


def verify_preserved():
    db = admin(preserved=True)
    try:
        for path in (LOCAL / 'preserved').glob('*.json'):
            data = json.loads(path.read_text())
            assert data['sha256'] == sha(path.with_suffix('.sql'))
            assert data['fingerprint'] == fingerprint(db, data['database']), 'Preserved database changed: ' + data['database']
            print('UNCHANGED:', data['database'], flush=True)
    finally:
        db.close()


def snapshot_source():
    assert not RUNTIME.exists(), 'Keep the existing runtime snapshot'
    paths = subprocess.check_output(['git', 'ls-files', '-co', '--exclude-standard', '-z'], cwd=ROOT).decode().split('\0')
    hashes = {}
    for relative in sorted(set(paths) - {''}):
        source = ROOT / relative
        if not source.is_file() or relative.startswith(('.local/', '.env', '.git/')):
            continue
        target = RUNTIME / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        hashes[relative] = sha(source)
    write(LOCAL / 'source-baseline.json', hashes)
    # Add the environment strip only to the frozen runtime's base templates.
    for relative in ('templates/admin_portal/base.html', 'templates/base.html', 'templates/admin/base_site.html'):
        path = RUNTIME / relative
        if not path.exists():
            continue
        content = path.read_text(encoding='utf-8')
        strip = '<div style="background:#173e35;color:white;padding:.55rem 1rem;text-align:center;font-size:.85rem" role="note">DEVELOPMENT — FICTIONAL TEST DATA · <a href="/testing/" style="color:white;text-decoration:underline">Explore testing workspace</a></div>'
        if '<body' in content:
            pos = content.index('>', content.index('<body')) + 1
            content = content[:pos] + strip + content[pos:]
        elif '{% block branding %}' in content:
            content = content.replace('{% block branding %}', '{% block branding %}' + strip)
        content = content.replace('</body>', '<script src="/static/js/testing-progress.js" defer></script></body>')
        path.write_text(content, encoding='utf-8')


def provision():
    assert not MANIFEST.exists(), 'Workspace already exists; use restore for a new baseline copy.'
    LOCAL.mkdir(parents=True, exist_ok=True)
    source_backup()
    snapshot_source()
    from scripts.main_testing_mysql import start as start_mysql
    start_mysql()
    manifest = new_database()
    manifest.update(secret=secrets.token_urlsafe(60), admin_username='lab_admin', admin_password=secrets.token_urlsafe(18))
    write(MANIFEST, manifest)
    write(LOCAL / 'login.json', {'url': 'http://127.0.0.1:8000/accounts/login/',
                               'username': manifest['admin_username'], 'password': manifest['admin_password']})
    command(['migrate', '--noinput'])
    command(['shell', '-c', 'from main_testing.seed import seed; seed()'])
    command(['shell', '-c', 'from main_testing.scenarios import add_scenarios; add_scenarios()'])


def new_database():
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S') + '_' + secrets.token_hex(2)
    name, user, password = 'santolan_lab_' + stamp, 'lab_' + secrets.token_hex(8), secrets.token_urlsafe(32)
    db = admin()
    try:
        with db.cursor() as cursor:
            cursor.execute('SELECT @@server_uuid')
            uuid = cursor.fetchone()[0]
            cursor.execute(f'CREATE DATABASE `{name}` CHARACTER SET utf8mb4')
            cursor.execute('CREATE USER %s@%s IDENTIFIED BY %s', (user, 'localhost', password))
            grant = name.replace('_', '\\_')
            cursor.execute(f'GRANT ALL ON `{grant}`.* TO %s@%s', (user, 'localhost'))
    finally:
        db.close()
    return {'purpose': 'MAIN_FICTIONAL_TESTING', 'database': name, 'user': user, 'password': password,
            'port': 3308 if (LOCAL / 'mysql.json').exists() else 3307,
            'server_uuid': uuid, 'media': str(LOCAL / 'datasets' / name / 'media'), 'created': stamp}


def rebuild():
    """Resume development safely by retaining the incomplete fictional database."""
    previous = json.loads(MANIFEST.read_text())
    write(LOCAL / 'retained' / (previous['database'] + '.json'), previous)
    manifest = {**previous, **new_database()}
    write(MANIFEST, manifest)
    for name in ('seed.py', 'tests.py', 'scenarios.py', 'verify.py'):
        shutil.copy2(ROOT / 'main_testing' / name, RUNTIME / 'main_testing' / name)
    command(['migrate', '--noinput'])
    command(['shell', '-c', 'from main_testing.seed import seed; seed()'])
    command(['shell', '-c', 'from main_testing.scenarios import add_scenarios; add_scenarios()'])


def command(arguments):
    env = os.environ.copy()
    env.update(MAIN_TESTING_MANIFEST=str(MANIFEST), DJANGO_SETTINGS_MODULE='config.main_testing_settings',
               PYTHONUNBUFFERED='1', PYTHONIOENCODING='utf-8')
    with (LOCAL / (arguments[0] + '.log')).open('a', encoding='utf-8') as log:
        process = subprocess.Popen([sys.executable, '-B', 'manage.py', *arguments, '--settings=config.main_testing_settings'],
            cwd=RUNTIME, env=env, creationflags=FLAGS, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding='utf-8', errors='replace')
        for line in process.stdout:
            print(line, end='', flush=True)
            log.write(line)
            log.flush()
        if process.wait():
            raise RuntimeError('Application command failed; inspect ' + str(LOCAL / (arguments[0] + '.log')))


def baseline():
    manifest = json.loads(MANIFEST.read_text())
    dump = LOCAL / 'baseline.sql'
    assert not dump.exists(), 'Do not overwrite the initial baseline'
    client('mysqldump.exe', manifest['database'], dump)
    db = admin()
    try:
        write(LOCAL / 'baseline.json', {'sha256': sha(dump), 'manifest': manifest,
                                      'fingerprint': fingerprint(db, manifest['database'])})
    finally:
        db.close()
    print('Fictional starting snapshot saved; restore always creates another database.')


def restore():
    with socket.socket() as probe:
        if probe.connect_ex(('127.0.0.1', 8000)) == 0:
            raise RuntimeError('Stop port 8000 before restoring. Port 8001 must remain running.')
    data = json.loads((LOCAL / 'baseline.json').read_text())
    assert sha(LOCAL / 'baseline.sql') == data['sha256']
    previous = json.loads(MANIFEST.read_text())
    from scripts.main_testing_mysql import start as start_mysql
    start_mysql()
    manifest = {**data['manifest'], **new_database()}
    client('mysql.exe', manifest['database'], LOCAL / 'baseline.sql', restore=True)
    db = admin()
    try:
        assert fingerprint(db, manifest['database']) == data['fingerprint']
    finally:
        db.close()
    # Evidence remains private and belongs to the immutable starting dataset.
    shutil.copytree(Path(data['manifest']['media']).parent, Path(manifest['media']).parent)
    write(LOCAL / 'retained' / (previous['database'] + '.json'), previous)
    write(MANIFEST, manifest)
    if (ROOT / 'program_intake/migrations/0001_initial.py').exists():
        from scripts.intake_runtime import install
        install()
        command(['shell', '-c', "from django.db import connection; from django.db.migrations.executor import MigrationExecutor; plan=MigrationExecutor(connection).migration_plan([('program_intake','0001_initial')]); assert all(m.app_label=='program_intake' and m.name=='0001_initial' and not backwards for m,backwards in plan), plan"])
        command(['migrate', 'program_intake', '0001', '--noinput'])
        command(['shell', '-c', 'from program_intake.demo import add_examples; add_examples()'])
    command(['check', '--database', 'default'])
    print('Restored baseline into', manifest['database'], '; previous database retained:', previous['database'])


def start():
    # Deploy only this environment's overrides; preserve the frozen application
    # and the original development server's source and database.
    shutil.copytree(ROOT / 'main_testing', RUNTIME / 'main_testing', dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns('__pycache__'))
    if (ROOT / 'program_intake/migrations/0001_initial.py').exists():
        from scripts.intake_runtime import install
        install()
    manifest = json.loads(MANIFEST.read_text())
    if manifest.get('port') == 3308:
        from scripts.main_testing_mysql import start as start_mysql
        start_mysql()
    db = admin()
    try:
        with db.cursor() as cursor:
            cursor.execute('SELECT @@server_uuid')
            assert cursor.fetchone()[0] == manifest['server_uuid']
    finally:
        db.close()
    print('DEVELOPMENT — FICTIONAL TEST DATA', flush=True)
    print('Database:', manifest['database'], '| http://127.0.0.1:8000/testing/', flush=True)
    command(['runlocal', '127.0.0.1:8000', '--noreload'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['provision', 'rebuild', 'start', 'baseline', 'restore', 'verify-preserved'])
    action = parser.parse_args().action
    {'provision': provision, 'rebuild': rebuild, 'start': start, 'baseline': baseline,
     'restore': restore, 'verify-preserved': verify_preserved}[action]()
