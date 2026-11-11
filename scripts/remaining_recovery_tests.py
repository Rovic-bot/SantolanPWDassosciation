"""Native dump/restore rehearsal confined to a verified disposable instance."""
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TransactionTestCase, override_settings
from core.content import save_content
from core.models import PublicContent
from core.tests.test_resources import resource_data
from members.models import Member
from members.tests import create_member
from membership.test_registration_intake import synthetic_policy, submitted, upload
from membership import registration_services as registration
from membership.registration_models import RegistrationIntake, RegistrationRevision, RegistrationAttachment, RegistrationAction
from django.utils.datastructures import MultiValueDict
from scripts.durable_test_runner import require_disposable


class DisposableRecoveryTests(TransactionTestCase):
    def test_native_synthetic_database_and_private_file_restore(self):
        require_disposable()
        binary = Path(settings.BASE_DIR) / '.local/mysql-8.4.11-winx64/bin'
        actor = get_user_model().objects.create_superuser('synthetic_recovery_operator')
        create_member('SYNTHETIC-RECOVERY')
        save_content('resources-help', user=actor, data=resource_data(action='publish'))
        with override_settings(ASSOCIATION_REGISTRATION_POLICY=synthetic_policy()):
            binding = registration.binding_for('synthetic-recovery-session')
            context = registration.issue_context(binding)
            registration.submit_registration(context.pk, binding, submitted(), MultiValueDict({'voter_certificate': [upload()]}))
        models = (Member, PublicContent, RegistrationIntake, RegistrationRevision, RegistrationAttachment, RegistrationAction)
        before = {model._meta.label: list(model.objects.order_by('pk').values()) for model in models}
        source = Path(settings.MEDIA_ROOT).resolve()
        temporary_root = Path(os.environ['G12_ARTIFACT_DIR']).resolve()
        self.assertTrue(source.is_relative_to(Path(tempfile.gettempdir()).resolve()))
        self.assertTrue(temporary_root.name.startswith('santolan-g12-tests-'))
        files = {path.relative_to(source).as_posix(): path.read_bytes() for path in source.rglob('*') if path.is_file()}
        self.assertTrue(files)
        config = connection.settings_dict
        self.assertEqual(config['NAME'], 'test_g12_disposable')
        self.assertEqual(config['HOST'], '127.0.0.1')
        environment = {**os.environ, 'MYSQL_PWD': config['PASSWORD']}
        flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
        args = ['--host=127.0.0.1', '--port=' + str(config['PORT']), '--user=' + config['USER']]
        with tempfile.TemporaryDirectory(prefix='recovery-rehearsal-', dir=temporary_root) as directory:
            backup = Path(directory)
            self.assertFalse(backup.is_relative_to(source))
            shutil.copytree(source, backup / 'private-files')
            dump = backup / 'synthetic.sql'
            require_disposable()
            with dump.open('wb') as output:
                result = subprocess.run([str(binary / 'mysqldump.exe'), *args, '--single-transaction',
                    '--no-tablespaces', '--set-gtid-purged=OFF', '--no-create-db', config['NAME']],
                    env=environment, stdout=output, stderr=subprocess.PIPE, creationflags=flags, timeout=90)
            self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))
            dump_hash = hashlib.sha256(dump.read_bytes()).hexdigest()
            # Prove recovery restores data and files; only these fictional objects
            # on the already verified disposable target are changed.
            PublicContent.objects.filter(key='resources-help').update(body='Synthetic post-backup change')
            first = next(iter(files))
            (source / first).write_bytes(b'Synthetic post-backup file change')
            require_disposable()
            connection.close()
            with dump.open('rb') as input_file:
                result = subprocess.run([str(binary / 'mysql.exe'), *args, config['NAME']], env=environment,
                    stdin=input_file, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=flags, timeout=90)
            self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))
            require_disposable()
            for name in files:
                shutil.copy2(backup / 'private-files' / name, source / name)
            self.assertEqual({model._meta.label: list(model.objects.order_by('pk').values()) for model in models}, before)
            self.assertEqual({name: (source / name).read_bytes() for name in files}, files)
            print('Disposable native MySQL dump/restore and private-file restore passed; synthetic SQL SHA-256:',
                dump_hash, 'private file count:', len(files), 'backup temporary directory removed after test.', flush=True)
