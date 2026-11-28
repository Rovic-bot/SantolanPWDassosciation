"""Loopback-only SMTP and S3 protocol checks; not hosted-provider acceptance.

Install the audit-only Moto/Flask/aiosmtpd tools in the private tools directory.
No operational settings, credentials, database or external recipient is used.
"""
from pathlib import Path
import sys
import os
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
# Append so the application's pinned boto3/Django versions take precedence.
sys.path.append(os.environ.get('QA_PYTHON_TOOLS', str(ROOT / '.local/qa-tools')))

from datetime import datetime, timedelta, timezone
from email import policy
from email.parser import BytesParser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from ipaddress import ip_address
import hashlib
import json
import logging
import os
import secrets
import smtplib
import socket
import ssl
from tempfile import TemporaryDirectory
from threading import Thread
from urllib.request import urlopen
from urllib.error import HTTPError

from aiosmtpd.controller import Controller
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from django.conf import settings
settings.configure(SECRET_KEY=secrets.token_urlsafe(50), USE_TZ=True,
    DEFAULT_CHARSET='utf-8', EMAIL_BACKEND='django.core.mail.backends.smtp.EmailBackend')
from django.core.files.base import ContentFile
from django.core.mail import EmailMessage, get_connection
from documents.storage import SupabasePrivateStorage
from core.email_delivery import send_message, EmailDeliveryUnconfirmed
from moto.server import DomainDispatcherApplication, create_backend_app
from werkzeug.serving import make_server, WSGIRequestHandler

logging.getLogger('werkzeug').setLevel(logging.ERROR)
logging.getLogger('mail.log').setLevel(logging.CRITICAL)
original_connect = socket.socket.connect
def local_connect(sock, address):
    if isinstance(address, tuple):
        host = address[0]
        if host != 'localhost' and not ip_address(host).is_loopback:
            raise AssertionError('External network is forbidden in local integration checks.')
    return original_connect(sock, address)
socket.socket.connect = local_connect

results = []
def passed(case, objective):
    results.append({'id': case, 'objective': objective, 'status': 'PASS'})
class QuietRequestHandler(WSGIRequestHandler):
    def log(self, *args, **kwargs): pass
class Metadata(BaseHTTPRequestHandler):
    state = 'private'
    api_key = secrets.token_urlsafe(32)
    def log_message(self, *args): pass
    def do_GET(self):
        code = 403 if self.headers.get('apikey') != self.api_key else 503 if self.state == 'unavailable' else 200
        self.send_response(code); self.send_header('Content-Type','application/json'); self.end_headers()
        self.wfile.write(json.dumps({'id':'synthetic-private','public':self.state=='public'}).encode())
class MailSink:
    mode = 'accept'
    messages = []
    attempts = 0
    async def handle_DATA(self, server, session, envelope):
        self.attempts += 1
        if self.mode == 'reject': return '550 Synthetic test rejection'
        self.messages.append(envelope.content)
        if self.mode == 'uncertain':
            server.transport.close()
            return '250 Synthetic accepted but connection interrupted'
        return '250 Synthetic accepted'

def main():
    services = []
    mail = None
    previous_ca = os.environ.get('SSL_CERT_FILE')
    with TemporaryDirectory(prefix='santolan-wire-check-') as temp:
        folder = Path(temp)
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'Synthetic local integration CA')])
        now = datetime.now(timezone.utc)
        certificate = (x509.CertificateBuilder().subject_name(subject).issuer_name(subject)
            .public_key(key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(now-timedelta(minutes=1)).not_valid_after(now+timedelta(hours=1))
            .add_extension(x509.BasicConstraints(ca=True,path_length=None),critical=True)
            .add_extension(x509.SubjectAlternativeName([x509.DNSName('localhost'),x509.IPAddress(ip_address('127.0.0.1'))]),critical=False)
            .sign(key,hashes.SHA256()))
        cert = folder/'ca.pem'; private = folder/'server.key'
        cert.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
        private.write_bytes(key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
        os.environ['SSL_CERT_FILE'] = str(cert)
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);context.load_cert_chain(cert,private)
        try:
            s3 = make_server('127.0.0.1',0,DomainDispatcherApplication(create_backend_app),threaded=True,
                ssl_context=(str(cert),str(private)),request_handler=QuietRequestHandler)
            metadata = ThreadingHTTPServer(('127.0.0.1',0),Metadata)
            metadata.socket = context.wrap_socket(metadata.socket,server_side=True)
            for server in [s3,metadata]:
                Thread(target=server.serve_forever,daemon=True).start();services.append(server)
            storage = SupabasePrivateStorage(project_ref='a'*20,bucket_api_key=Metadata.api_key,
                bucket_name='synthetic-private',region_name='us-east-1',access_key='synthetic-access',secret_key=secrets.token_urlsafe(32))
            # Test-only endpoint substitution. Production endpoint validation is unchanged.
            storage.endpoint_url = f'https://127.0.0.1:{s3.server_port}'
            storage.verify = str(cert)
            storage._bucket_api_url = f'https://127.0.0.1:{metadata.server_port}/'
            client = storage.connection.meta.client
            client.create_bucket(Bucket=storage.bucket_name)
            payload = b'SYNTHETIC private file\x00' * 60000
            name = storage.save('synthetic/proof.bin',ContentFile(payload))
            assert storage.size(name)==len(payload)
            with storage.open(name) as stream: assert stream.read()==payload
            passed('LOCAL-S3-01','Verified HTTPS upload, spooled download and size through the real adapter')
            second = storage.save(name,ContentFile(b'SYNTHETIC second object'))
            assert second != name
            with storage.open(name) as stream: assert stream.read()==payload
            passed('LOCAL-S3-02','Duplicate upload keeps original bytes and generates a distinct name')
            try: urlopen(storage.endpoint_url+'/'+storage.bucket_name+'/'+name,timeout=5)
            except HTTPError as error: assert error.code==403
            else: raise AssertionError('Anonymous object read must fail')
            passed('LOCAL-S3-03','Anonymous wire request cannot read the private object')
            try: storage.url(name)
            except ValueError: pass
            else: raise AssertionError('Application must not issue a storage URL')
            passed('LOCAL-S3-04','Public/signed storage URLs remain disabled')
            for state in ['public','unavailable']:
                Metadata.state=state
                try: storage.save('synthetic/denied.bin',ContentFile(b'SYNTHETIC'))
                except OSError: pass
                else: raise AssertionError('Unverified bucket must reject upload')
                Metadata.state='private'
                assert not storage.exists('synthetic/denied.bin')
                passed('LOCAL-S3-05' if state=='public' else 'LOCAL-S3-06',state+' metadata fails closed before writing an object')
            Metadata.api_key = secrets.token_urlsafe(32)
            try: storage.open(name)
            except OSError: pass
            else: raise AssertionError('Rejected metadata credentials must deny access')
            Metadata.api_key = storage._bucket_api_key
            passed('LOCAL-S3-07','Rejected bucket-metadata credential denies access')
            backup = {}
            for object_name in [name,second]:
                with storage.open(object_name) as stream: backup[object_name]=stream.read()
                storage.delete(object_name)
                assert not storage.exists(object_name)
            for object_name,content in backup.items():
                assert storage.save(object_name,ContentFile(content))==object_name
                with storage.open(object_name) as stream: assert hashlib.sha256(stream.read()).digest()==hashlib.sha256(content).digest()
                assert client.head_object(Bucket=storage.bucket_name,Key=object_name)['CacheControl']=='private, no-store'
            passed('LOCAL-S3-08','Synthetic object backup/delete/restore preserves names, hashes and private cache policy')
            for object_name in backup: storage.delete(object_name)
            assert client.list_objects_v2(Bucket=storage.bucket_name).get('KeyCount')==0
            passed('LOCAL-S3-09','Cleanup leaves no synthetic objects')
            sink=MailSink()
            with socket.socket() as probe: probe.bind(('127.0.0.1',0));mail_port=probe.getsockname()[1]
            mail=Controller(sink,hostname='127.0.0.1',port=mail_port,ssl_context=context)
            mail.start()
            from io import BytesIO
            from reportlab.pdfgen.canvas import Canvas
            document = BytesIO()
            canvas = Canvas(document)
            canvas.drawString(72, 720, 'SYNTHETIC local mail attachment')
            canvas.save()
            pdf = document.getvalue()
            def message():
                connection=get_connection(backend='django.core.mail.backends.smtp.EmailBackend',host='127.0.0.1',port=mail_port,use_ssl=True,use_tls=False,timeout=5)
                item=EmailMessage('SYNTHETIC local acceptance','Synthetic certificate test only.',from_email='sender@example.test',to=['recipient@example.test'],connection=connection)
                item.attach('Synthetic-Certificate.pdf',pdf,'application/pdf')
                return item
            send_message(message())
            assert len(sink.messages)==sink.attempts==1
            captured=BytesParser(policy=policy.default).parsebytes(sink.messages[0])
            assert list(captured.iter_attachments())[0].get_payload(decode=True)==pdf
            passed('LOCAL-MAIL-01','Actual TLS SMTP submission preserves the generated PDF attachment')
            sink.mode='reject'
            try: send_message(message())
            except smtplib.SMTPDataError: pass
            else: raise AssertionError('SMTP rejection must remain a failure')
            assert len(sink.messages)==1 and sink.attempts==2
            passed('LOCAL-MAIL-02','SMTP rejection does not manufacture acceptance or retry')
            sink.mode='uncertain'
            try: send_message(message())
            except EmailDeliveryUnconfirmed: pass
            else: raise AssertionError('Interrupted acknowledgment must remain uncertain')
            assert len(sink.messages)==2 and sink.attempts==3
            passed('LOCAL-MAIL-03','Interrupted acceptance is uncertain and does not automatically resend')
        finally:
            if mail:mail.stop()
            for server in reversed(services):server.shutdown();server.server_close()
            if previous_ca is None:os.environ.pop('SSL_CERT_FILE',None)
            else:os.environ['SSL_CERT_FILE']=previous_ca
    destination = Path(os.environ.get('QA_OUTPUT', str(ROOT / '.local/qa-integrations.json')))
    destination.parent.mkdir(parents=True, exist_ok=True)
    Path(destination).write_text(json.dumps({'conditions':'Loopback HTTPS Moto S3 emulator, synthetic bucket metadata and TLS SMTP capture; pinned application SDK; external sockets blocked; no hosted provider or actual recipient contacted.','tests':results},indent=2),encoding='utf-8')
    print(f'{len(results)} local protocol/restore checks passed; no hosted email or storage claim.')

if __name__=='__main__': main()
