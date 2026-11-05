"""Deterministic time and HTTP response fixtures, with no provider logic replaced."""
from unittest.mock import Mock
import xml.etree.ElementTree as ET

import requests

SEARCH_URL = 'https://export.arxiv.org/api/query'
PDF_URL = 'https://arxiv.org/pdf/2501.01234'
DOWNLOAD_OPTIONS = {'timeout': (10, 60), 'stream': True, 'allow_redirects': False}


class ControlledClock:
    def __init__(self, now=1000.0):
        self.now = now
        self.sleep = Mock(side_effect=self.advance)

    def monotonic(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


def paper(ident, title):
    """Gold bibliographic values: ordinary synthetic evidence, not parsed output."""
    return {
        'source_id': ident, 'source': 'arxiv', 'title': title,
        'authors': ['Dana Tester'], 'year': 2025, 'abstract': 'Synthetic search evidence.',
        'category': 'cs.SE', 'url': f'https://arxiv.org/abs/{ident}',
    }


def atom_feed(papers=(), *, total=None, invalid_entry=False, error_entry=False):
    atom = 'http://www.w3.org/2005/Atom'
    opensearch = 'http://a9.com/-/spec/opensearch/1.1/'
    root = ET.Element('{' + atom + '}feed')
    if total is not None:
        ET.SubElement(root, '{' + opensearch + '}totalResults').text = str(total)
    if invalid_entry:
        invalid = ET.SubElement(root, '{' + atom + '}entry')
        ET.SubElement(invalid, '{' + atom + '}id').text = 'https://other.example.invalid/record'
        ET.SubElement(invalid, '{' + atom + '}title').text = 'This is not an arXiv paper'
    for item in papers:
        entry = ET.SubElement(root, '{' + atom + '}entry')
        ET.SubElement(entry, '{' + atom + '}id').text = item['url'] + 'v2'
        ET.SubElement(entry, '{' + atom + '}title').text = item['title']
        for name in item['authors']:
            author = ET.SubElement(entry, '{' + atom + '}author')
            ET.SubElement(author, '{' + atom + '}name').text = name
        if item['year'] is not None:
            ET.SubElement(entry, '{' + atom + '}published').text = str(item['year']) + '-01-01T00:00:00Z'
        ET.SubElement(entry, '{' + atom + '}summary').text = item['abstract']
        if item['category']:
            ET.SubElement(entry, '{' + atom + '}category', term=item['category'])
    if error_entry:
        entry = ET.SubElement(root, '{' + atom + '}entry')
        ET.SubElement(entry, '{' + atom + '}id').text = 'https://arxiv.org/api/errors#incorrect_id_format'
    return ET.tostring(root, encoding='utf-8')


def feed_response(content):
    response = requests.Response()
    response.status_code = 200
    response.url = SEARCH_URL
    response._content = content
    return response


class StreamResponse:
    """A closeable HTTP response double with real iteration and HTTP failures.

    chunks is an iterable or a factory, so a transfer can fail after yielding
    some data. The application never receives mocked download return values.
    """
    def __init__(self, chunks=(), *, status=200, location=None):
        self.status_code = status
        self.request = None
        self.headers = {} if location is None else {'Location': location}
        self.is_redirect = status in (301, 302, 303, 307, 308)
        self.chunks = chunks
        self.closed = False
        self.iterations = 0

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.closed = True
        return False

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError('Synthetic upstream HTTP failure', response=self)

    def iter_content(self, chunk_size):
        self.iterations += 1
        yield from self.chunks() if callable(self.chunks) else self.chunks


def chunks_of(raw):
    return (raw[offset:offset + 65536] for offset in range(0, len(raw), 65536))
