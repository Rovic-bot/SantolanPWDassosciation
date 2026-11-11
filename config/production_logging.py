"""Allowlisted request diagnostics: never serialize an exception or request."""
import json
import logging
from ssl import SSLCertVerificationError

from django.core.exceptions import FieldError, ImproperlyConfigured
from django.db import (
    DataError, DatabaseError, IntegrityError, InterfaceError, InternalError,
    NotSupportedError, OperationalError, ProgrammingError,
)
from django.template import TemplateDoesNotExist, TemplateSyntaxError
from django.urls import NoReverseMatch


# Use names from these trusted classes, never an arbitrary exception's name.
EXCEPTION_TYPES = (
    (OperationalError, 'database'), (ProgrammingError, 'database'),
    (IntegrityError, 'database'), (InterfaceError, 'database'),
    (DataError, 'database'), (InternalError, 'database'),
    (NotSupportedError, 'database'), (DatabaseError, 'database'),
    (SSLCertVerificationError, 'tls'),
    (TemplateDoesNotExist, 'template'), (TemplateSyntaxError, 'template'),
    (NoReverseMatch, 'routing'), (ImproperlyConfigured, 'configuration'),
    (FieldError, 'orm'), (OSError, 'io'),
    (ImportError, 'import'), (TypeError, 'application'),
    (ValueError, 'application'), (KeyError, 'application'),
    (AttributeError, 'application'), (NameError, 'application'),
)
MYSQL_ERRORS = {
    1040: 'too_many_connections', 1044: 'database_access_denied',
    1045: 'authentication_denied', 1049: 'unknown_database',
    1054: 'unknown_column', 1062: 'duplicate_key', 1142: 'command_denied',
    1146: 'missing_table', 1205: 'lock_timeout', 1213: 'deadlock',
    2002: 'connection_failed', 2003: 'connection_failed',
    2005: 'hostname_resolution_failed', 2006: 'server_gone_away',
    2013: 'connection_lost', 2026: 'tls_connection_failed',
}
PUBLIC_ROUTES = {
    'core:home': 'home', 'core:about': 'about',
    'programs:list': 'programs', 'core:programs': 'programs',
}


class SanitizedRequestFormatter(logging.Formatter):
    def format(self, record):
        # Do not call getMessage(), super().format(), str(exception), or any
        # traceback formatter. All can contain SQL, evidence paths or secrets.
        exception = record.exc_info[1] if record.exc_info else None
        category, exception_name = ('http', 'none') if exception is None else ('application', 'Exception')
        for exception_type, known_category in EXCEPTION_TYPES:
            if isinstance(exception, exception_type):
                category, exception_name = known_category, exception_type.__name__
                break

        request = getattr(record, 'request', None)
        match = getattr(request, 'resolver_match', None)
        route = PUBLIC_ROUTES.get(getattr(match, 'view_name', None), 'other')
        status = getattr(record, 'status_code', None)
        payload = {
            'event': 'django_request_error', 'route': route,
            'status': status if type(status) is int and 100 <= status <= 599 else None,
            'category': category, 'exception': exception_name,
        }
        if isinstance(exception, DatabaseError) and exception.args:
            code = exception.args[0]
            if type(code) is int and code in MYSQL_ERRORS:
                payload.update(mysql_code=code, error=MYSQL_ERRORS[code])
        return json.dumps(payload, separators=(',', ':'))


class SanitizedRequestHandler(logging.StreamHandler):
    def handleError(self, record):
        # StreamHandler's default failure diagnostic prints the ORIGINAL
        # message/arguments to stderr. Never fall back to that unsafe output.
        pass


REQUEST_LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {'safe_request': {'()': SanitizedRequestFormatter}},
    'handlers': {
        'safe_request_stderr': {
            'class': 'config.production_logging.SanitizedRequestHandler',
            'level': 'ERROR', 'formatter': 'safe_request',
            'stream': 'ext://sys.stderr',
        },
    },
    'loggers': {
        'django.request': {
            'handlers': ['safe_request_stderr'], 'level': 'ERROR',
            # Prevent duplicate output or a raw report in ancestor handlers.
            'propagate': False,
        },
    },
}
