"""Fixtures for the NEW HW2 initial stage; no live data or service access."""
import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import requests
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

# Importing the app normally loads hw1/.env. Never read it in this suite.
with patch('dotenv.load_dotenv', return_value=False):
    from app import create_app


PAPER = {
    'source_id': '2501.01234', 'title': 'Testing Research Libraries',
    'authors': ['Ava Analyst', 'Ben Builder'], 'year': 2025,
    'abstract': 'A controlled study of persistent research libraries.',
    'category': 'cs.SE',
}
PAGE_LINES = [
    [PAPER['title'], 'Ava Analyst and Ben Builder', 'Published 2025',
     'Abstract', 'We evaluate a research library with 72 synthetic papers.',
     'The study measures reliable persistence and reproducible evidence.',
     '1 Introduction', 'All documents are synthetic and contain no private data.',
     'The experiment checks discovery, storage, summaries, and questions.'],
    ['2 Results', 'The HAWK benchmark contains 72 synthetic papers.',
     'Records and answers survived restarting the research library.',
     '3 Limitations', 'The limitation is that no field data is included.',
     'These controlled results do not establish behavior for scanned PDFs.'],
]
ATOM = b'''<feed xmlns="http://www.w3.org/2005/Atom"
    xmlns:opensearch="http://a9.com/-/spec/opensearch/1.1/">
  <opensearch:totalResults>21</opensearch:totalResults>
  <entry><id>https://arxiv.org/abs/2501.01234v2</id>
    <title> Testing Research\n Libraries </title>
    <author><name>Ava Analyst</name></author>
    <author><name>Ben Builder</name></author>
    <published>2025-01-03T00:00:00Z</published>
    <summary>A controlled study of persistent research libraries.</summary>
    <category term="cs.SE"/>
  </entry>
</feed>'''


def pdf_bytes(*, blank=False, password=None, arxiv_id=None):
    """Small, real pypdf-readable bytes, generated entirely in memory."""
    writer = PdfWriter()
    for index, lines in enumerate(PAGE_LINES[:1] if blank else PAGE_LINES):
        page = writer.add_blank_page(width=612, height=792)
        if blank:
            continue
        font = DictionaryObject({
            NameObject('/Type'): NameObject('/Font'),
            NameObject('/Subtype'): NameObject('/Type1'),
            NameObject('/BaseFont'): NameObject('/Helvetica'),
        })
        page[NameObject('/Resources')] = DictionaryObject({
            NameObject('/Font'): DictionaryObject({
                NameObject('/F1'): writer._add_object(font),
            }),
        })
        lines = list(lines)
        if index == 0 and arxiv_id:
            lines.append('arXiv:' + arxiv_id)
        escaped = [line.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')
                   for line in lines]
        stream = DecodedStreamObject()
        stream.set_data(('BT /F1 12 Tf 50 740 Td 16 TL ' +
                         ' '.join(f'({line}) Tj T*' for line in escaped) +
                         ' ET').encode('ascii'))
        page[NameObject('/Contents')] = writer._add_object(stream)
    writer.add_metadata({'/Title': PAPER['title'], '/Author': 'Ava Analyst; Ben Builder'})
    if password:
        writer.encrypt(password)
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


def search_response(content=ATOM):
    response = Mock(status_code=200)
    response.content = content
    return response


def pdf_response(raw):
    response = MagicMock(status_code=200, is_redirect=False)
    response.__enter__.return_value = response
    response.iter_content.return_value = [raw[:100], raw[100:]]
    return response


def llm_response(answer='The HAWK benchmark uses 72 papers. [p. 2]', *, status=200,
                 finish='stop'):
    response = Mock(status_code=status)
    response.json.return_value = {
        'choices': [{'message': {'content': answer}, 'finish_reason': finish}],
    }
    return response


class IsolatedCase(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix='papertrail-hw2-initial-')
        self.addCleanup(directory.cleanup)
        self.directory = Path(directory.name)
        # These guards also protect a direct unittest discovery invocation.
        self.start_patch(patch('dotenv.load_dotenv', return_value=False))
        self.start_patch(patch.dict(os.environ, {
            'DATA_DIR': directory.name, 'LLM_API_KEY': '', 'OPENAI_API_KEY': '',
            'LLM_BASE_URL': 'https://llm.example.invalid/v1',
            'LLM_MODEL': 'unit-test-model', 'LLM_MAX_OUTPUT_TOKENS': '1800',
            'LLM_TIMEOUT': '2', 'LLM_REASONING_EFFORT': '',
            'APP_USERNAME': '', 'APP_PASSWORD': '',
        }))
        if getattr(requests.sessions.Session.request, '_papertrail_initial_guard', False) is not True:
            self.start_patch(patch('requests.sessions.Session.request',
                                  side_effect=AssertionError('Unexpected real HTTP request')))
        self.start_patch(patch('providers._cache', {}))
        self.start_patch(patch('providers._last_search', 0.0))
        self.start_patch(patch('providers.time.sleep', return_value=None))
        self.config = {
            'TESTING': True, 'DATA_DIR': directory.name,
            'LLM_API_KEY': '', 'LLM_MODEL': 'unit-test-model',
            'LLM_BASE_URL': 'https://llm.example.invalid/v1',
            'LLM_MAX_OUTPUT_TOKENS': 1800, 'LLM_TIMEOUT': 2,
            'LLM_REASONING_EFFORT': '', 'APP_USERNAME': '', 'APP_PASSWORD': '',
        }
        self.app = create_app(self.config)
        self.client = self.app.test_client()

    def start_patch(self, patcher):
        value = patcher.start()
        self.addCleanup(patcher.stop)
        return value

    def save(self, **changes):
        response = self.client.post('/api/papers', json=dict(PAPER, **changes))
        self.assertEqual(response.status_code, 201, response.get_data(as_text=True))
        self.assertTrue(response.json['created'])
        return response.json['paper']

    def upload(self, raw=None):
        response = self.client.post('/api/upload', data={
            'file': (io.BytesIO(pdf_bytes() if raw is None else raw), 'fixture.pdf'),
        })
        self.assertEqual(response.status_code, 201, response.get_data(as_text=True))
        return response.json['paper']

    def enable_llm(self):
        self.app.extensions['llm'].api_key = 'dummy-test-key'
        self.config['LLM_API_KEY'] = 'dummy-test-key'
        return self.app.extensions['llm']

    def detail(self, paper_id):
        response = self.client.get(f'/api/papers/{paper_id}')
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        return response.json['paper']

    def pdf_files(self):
        return sorted((self.directory / 'uploads').glob('*.pdf'))
