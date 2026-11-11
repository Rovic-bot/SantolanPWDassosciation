"""Source-integration regression settings; connection supplied by disposable runner."""
from .settings import *

INSTALLED_APPS = [*INSTALLED_APPS, 'program_intake']
TEMPLATES[0]['DIRS'].insert(0, BASE_DIR / 'program_intake/templates')
STATICFILES_DIRS.insert(0, BASE_DIR / 'program_intake/static')
# Existing regression URLs and evidence contracts retain their historical behavior.
# New integration tests opt into the secure intake URLconf and submission guard.
PROGRAM_INTAKE_ENABLED = False
