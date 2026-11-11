"""Email regressions on the disposable G12 database with external sockets blocked."""
import socket
from unittest.mock import patch

from scripts.registration_intake_test_runner import RegistrationIntakeTestRunner


class EmailTestRunner(RegistrationIntakeTestRunner):
    def run_tests(self, test_labels, **kwargs):
        original_lookup = socket.getaddrinfo
        original_connect = socket.socket.connect
        original_connect_ex = socket.socket.connect_ex

        def require_loopback(host):
            if host not in ('localhost', '127.0.0.1', '::1', b'localhost', b'127.0.0.1', b'::1'):
                raise AssertionError('Email tests prohibit external network connections.')

        def lookup(host, *args, **options):
            require_loopback(host)
            return original_lookup(host, *args, **options)

        def connect(sock, address):
            require_loopback(address[0])
            return original_connect(sock, address)

        def connect_ex(sock, address):
            require_loopback(address[0])
            return original_connect_ex(sock, address)

        with patch('socket.getaddrinfo', lookup), patch('socket.socket.connect', connect), \
                patch('socket.socket.connect_ex', connect_ex):
            return super().run_tests(test_labels, **kwargs)
