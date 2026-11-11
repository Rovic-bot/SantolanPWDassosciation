import json
import os
from pathlib import Path
from django.conf import settings
from core.demo_seed import upload
from members.models import Member
from main_testing.seed import require_environment
from .access import registered_name


def prepare_main():
    require_environment()
    directory = Path(os.environ['MAIN_TESTING_MANIFEST']).parent
    data = json.loads((Path(settings.MEDIA_ROOT).parent / 'intake-demo.json').read_text(encoding='utf-8'))
    assets = directory / 'intake-browser'
    assets.mkdir(exist_ok=True)
    for name, content in [('portrait.png', upload(portrait=True)),
                          ('socioeconomic.pdf', upload('Fictional observation: 90 assessment units. Submitted solely for program review.'))]:
        (assets / name).write_bytes(content.read())
    member = Member.objects.get(control_number=data['public_member']['control_number'])
    fixture = {'url': 'http://127.0.0.1:8000', 'program': data['public_program'],
        'rankingProgram': data['ranking_program'], 'requirement': data['public_requirement'],
        'member': {**data['public_member'], 'name': member.full_name, 'full_name': registered_name(member)}, 'photo': str(assets / 'portrait.png'),
        'document': str(assets / 'socioeconomic.pdf'), 'output': str(directory / 'screenshots'),
        'login_file': str(directory / 'login.json')}
    (assets / 'input.json').write_text(json.dumps(fixture), encoding='utf-8')
    print('Prepared fictional browser inputs without copying credentials.')
