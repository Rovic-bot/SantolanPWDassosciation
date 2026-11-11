"""Identity guards for the owner's empty, loopback-only development database."""
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOCAL = ROOT / '.local/development'
MANIFEST = LOCAL / 'connection.json'
PURPOSE = 'SANTOLAN_LOCAL_DEVELOPMENT'


def load_manifest():
    from django.core.exceptions import ImproperlyConfigured
    if not MANIFEST.is_file():
        raise ImproperlyConfigured('Fresh local development configuration is missing. No older database will be used.')
    item = json.loads(MANIFEST.read_text(encoding='utf-8'))
    if (item.get('purpose') != PURPOSE or Path(item['repository']).resolve() != ROOT.resolve()
            or item['database'] != 'santolan_pwd_development' or item['host'] != '127.0.0.1'
            or item['mysql_port'] != 3309 or item['http_port'] != 8013
            or Path(item['datadir']).resolve() != (ROOT / '.local/ewaf-twelve-demo/mysql-data').resolve()
            or Path(item['media']).resolve() != (LOCAL / 'private-media').resolve()):
        raise ImproperlyConfigured('Unexpected local development identity. Refusing to use another database.')
    return item


def verify_connection(sender=None, connection=None, **kwargs):
    from django.core.exceptions import ImproperlyConfigured
    item = load_manifest()
    if connection.vendor != 'mysql' or connection.settings_dict['HOST'] != item['host']:
        raise ImproperlyConfigured('The verified local MySQL instance is required.')
    with connection.cursor() as cursor:
        cursor.execute('SELECT DATABASE(), @@port, @@datadir, @@server_uuid, @@bind_address')
        name, port, datadir, server_uuid, bind = cursor.fetchone()
    if (name != item['database'] or port != item['mysql_port'] or server_uuid != item['server_uuid']
            or Path(datadir).resolve() != Path(item['datadir']).resolve() or bind != '127.0.0.1'):
        connection.close()
        raise ImproperlyConfigured('Local database identity mismatch; access refused.')


class LocalIdentityMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response['X-Santolan-Environment'] = 'LOCAL-DEVELOPMENT'
        return response


def health(request):
    from django.db import connection
    from django.http import JsonResponse
    verify_connection(connection=connection)
    item = load_manifest()
    return JsonResponse({'purpose': PURPOSE, 'instance_id': item['instance_id'],
        'database': item['database'], 'pid': os.getpid()})
