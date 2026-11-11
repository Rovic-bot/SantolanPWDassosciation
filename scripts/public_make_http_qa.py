"""Read-only public route, media, PDF and filter smoke checks on the local preview."""
from collections import deque
from hashlib import sha256
from html.parser import HTMLParser
import json
from pathlib import Path
from urllib.parse import urljoin, urlsplit
from urllib.request import urlopen


class PublicHTML(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.images = []
        self.fields = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'a' and attrs.get('href'):
            self.links.append(attrs['href'])
        if tag == 'img' and attrs.get('src'):
            self.images.append(attrs['src'])
        if tag in {'input', 'select', 'textarea'} and attrs.get('name'):
            self.fields.append(attrs['name'])


def main():
    base = 'http://127.0.0.1:8013'
    roots = ['/', '/about/', '/announcements/', '/events/', '/programs/',
             '/results/', '/membership/register/', '/resources/']
    extra = ['/membership/registration/apply/', '/membership/registration/pdao/',
             '/programs/tracking/', '/assistance/referrals/', '/assistance/referrals/verify/',
             '/announcements/?q=zzzznoresult20261104', '/programs/?q=zzzznoresult20261104',
             '/programs/?period=all&page=2', '/events/?period=past']
    queue, seen, rows, images, pdfs = deque(roots + extra), set(), [], set(), []
    while queue:
        route = queue.popleft()
        if route in seen:
            continue
        seen.add(route)
        response = urlopen(base + route, timeout=20)
        data = response.read()
        content_type = response.headers.get_content_type()
        if content_type == 'application/pdf':
            assert data.startswith(b'%PDF-'), route
            pdfs.append({'route': route, 'sha256': sha256(data).hexdigest(), 'bytes': len(data)})
            continue
        text = data.decode('utf-8-sig')
        assert 'css/public-make.css' in text, route
        assert 'portal-redesign' in text, route
        parser = PublicHTML()
        parser.feed(text)
        images.update(urljoin(base + route, image) for image in parser.images)
        rows.append({'route': route, 'status': response.status, 'final_route': urlsplit(response.url).path,
                     'theme': True, 'fields': parser.fields})
        for href in parser.links:
            url = urlsplit(urljoin(base + route, href))
            if url.netloc != '127.0.0.1:8013':
                continue
            path = url.path
            # No staff pages, state-changing actions, private-document endpoints or arbitrary query crawl.
            public = path.startswith(('/about/', '/announcements/', '/events/', '/programs/',
                                      '/results/', '/membership/registration/', '/resources/'))
            blank_pdf = path.startswith('/membership/forms/')
            if (public or blank_pdf) and not any(part in path for part in ('/finish/', '/image/', '/status/', '/qr/')) and not url.query:
                queue.append(path)
    image_rows = []
    for url in sorted(images):
        response = urlopen(url, timeout=20)
        data = response.read()
        assert data and response.headers.get_content_type().startswith('image/'), url
        image_rows.append({'path': urlsplit(url).path, 'status': response.status, 'bytes': len(data)})
    login = urlopen(base + '/accounts/login/').read().decode()
    assert 'css/public-make.css' not in login
    assert 'portal-redesign' not in login
    output = Path('docs/public-make-2026-11-04')
    output.mkdir(parents=True, exist_ok=True)
    report = {'pages': rows, 'images': image_rows, 'blank_forms': pdfs,
              'staff_sign_in_isolated': True, 'method': 'Public GET requests only; no form submissions.'}
    (output / 'http-checks.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps({'public_views_checked': len(rows), 'images_checked': len(image_rows),
                      'pdfs_checked': len(pdfs), 'staff_sign_in_isolated': True}))


if __name__ == '__main__':
    main()
