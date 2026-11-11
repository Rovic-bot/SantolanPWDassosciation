"""Exercise current registration/review UI against this fictional environment only."""
import json
import os
from pathlib import Path
import subprocess
from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import Client
from membership.forms import ApplicationForm
from core.demo_seed import upload
from .seed import require_environment


def onsite():
    require_environment()
    local = Path(os.environ['MAIN_TESTING_MANIFEST']).parent
    root = local.parents[1]
    text = (root / 'scripts/onsite_profile_browser_qa.cjs').read_text(encoding='utf-8')
    for before, after in [('Pasig City', 'Fictional Municipality'), ('Santolan\'', 'Imaginary District\''),
                          ('Sample Street', 'Invented Avenue'), ('Mara', 'Zarela'), ('Santos', 'Cloudmere'),
                          ('09123456789', '00000009999'), ('https://registry.example.test/', 'https://example.invalid/simulated-registry-no-government-service'),
                          ('https://registry.example.test/**', 'https://example.invalid/**')]:
        text = text.replace(before, after)
    script = local / 'onsite-browser.cjs'
    script.write_text(text, encoding='utf-8')
    portrait = local / 'artificial-portrait.png'
    portrait.write_bytes(upload(portrait=True).read())
    actor = get_user_model().objects.get(username=settings.MAIN_TESTING_MANIFEST['admin_username'])
    client = Client()
    client.force_login(actor)
    env = os.environ.copy()
    env.update(QA_URL='http://127.0.0.1:8000', QA_COOKIE_NAME=settings.SESSION_COOKIE_NAME,
        QA_SESSION=client.cookies[settings.SESSION_COOKIE_NAME].value, QA_OUTPUT=str(local / 'screenshots'),
        QA_PATH='/membership/applications/new/', QA_PHOTO=str(portrait),
        QA_UPLOADS=json.dumps({item['id']: item['label'] for item in ApplicationForm().snapshot}))
    result = subprocess.run(['node', str(script)], env=env, capture_output=True, text=True, encoding='utf-8', errors='replace')
    (local / 'onsite-browser.log').write_text(result.stdout + result.stderr, encoding='utf-8')
    print(result.stdout + result.stderr, flush=True)
    if result.returncode:
        raise RuntimeError('Onsite browser checks failed')
