"""Run the installed port-8000 application on fresh disposable MySQL."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
RUNTIME = ROOT / '.local/main-testing/runtime'
source = (ROOT / 'scripts/g12_test_runner.py').read_text(encoding='utf-8')
source = source.replace("DJANGO_SETTINGS_MODULE='config.settings'", "DJANGO_SETTINGS_MODULE='config.intake_test_settings'")
source = source.replace('cwd=root, env=env', 'cwd=runtime, env=env')
source = source.replace("'character-set-server=utf8mb4\\ncollation-server=utf8mb4_0900_ai_ci\\n'",
    "'character-set-server=utf8mb4\\ncollation-server=utf8mb4_0900_ai_ci\\nmax_allowed_packet=512M\\n'")
scope = {'__name__': 'intake_runner', '__file__': str(ROOT / 'scripts/g12_test_runner.py'), 'runtime': RUNTIME}
exec(compile(source, str(ROOT / 'scripts/g12_test_runner.py'), 'exec'), scope)
sys.exit(scope['main']())
