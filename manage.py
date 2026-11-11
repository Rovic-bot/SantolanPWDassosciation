#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys
from pathlib import Path


def main():
    """Run administrative tasks."""
    # Keep the owner's identity-checked runtime, including its fail-closed
    # behavior if a manifest is missing. A new checkout uses its own .env.
    managed = (Path(__file__).resolve().parent / '.local/development').exists()
    os.environ.setdefault('DJANGO_SETTINGS_MODULE',
        'config.current_development_settings' if managed else 'config.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
