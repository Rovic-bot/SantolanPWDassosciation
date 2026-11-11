"""Back up the verified isolated lab, then apply only the additive intake migration."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from scripts.main_testing import LOCAL, MANIFEST, admin, client, fingerprint, sha, write, command
from scripts.intake_runtime import install


def deploy():
    manifest = json.loads(MANIFEST.read_text(encoding='utf-8'))
    assert manifest['purpose'] == 'MAIN_FICTIONAL_TESTING' and manifest['port'] == 3308
    assert manifest['database'].startswith('santolan_lab_')
    db = admin()
    try:
        with db.cursor() as cursor:
            cursor.execute('SELECT @@server_uuid')
            assert cursor.fetchone()[0] == manifest['server_uuid']
        backup = LOCAL / 'before-program-intake.sql'
        proof = backup.with_suffix('.json')
        if not backup.exists():
            before = fingerprint(db, manifest['database'])
            client('mysqldump.exe', manifest['database'], backup)
            assert backup.stat().st_size and before == fingerprint(db, manifest['database'])
            write(proof, {'database': manifest['database'], 'server_uuid': manifest['server_uuid'],
                'sha256': sha(backup), 'fingerprint': before})
        else:
            retained = json.loads(proof.read_text(encoding='utf-8'))
            assert retained['database'] == manifest['database'] and retained['sha256'] == sha(backup)
        print('Verified recovery backup:', backup, flush=True)
    finally:
        db.close()
    install()
    command(['shell', '-c', "from django.db import connection; from django.db.migrations.executor import MigrationExecutor; plan=MigrationExecutor(connection).migration_plan([('program_intake','0001_initial')]); assert all(m.app_label=='program_intake' and m.name=='0001_initial' and not backwards for m,backwards in plan), plan; print('Verified additive intake-only migration plan:', [(m.app_label,m.name) for m,b in plan])"])
    command(['migrate', 'program_intake', '0001', '--noinput'])
    command(['check', '--database', 'default'])
    command(['makemigrations', '--check', '--dry-run'])


if __name__ == '__main__':
    deploy()
