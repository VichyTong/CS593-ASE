"""Isolated fixtures shared by the three cumulative HW2 stages."""
import io
import tempfile
import unittest
from pathlib import Path

from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from app import create_app


PAPER = {
    'source_id': '2501.01234', 'title': 'Reliable Research Workflows',
    'authors': ['Alice Example', 'Bob Example'], 'year': 2025,
    'abstract': 'A controlled study of reproducible research tools.',
    'category': 'cs.SE',
}
TEXT_LINES = [
    'Reliable Research Workflows', 'Alice Example and Bob Example', '2025',
    'Abstract', 'We evaluate a library assistant using 80 small programs.',
    'The controlled study measures persistence and question answering.',
    '1 Introduction', 'The ZEBRA benchmark contains 80 small programs.',
    'The main limitation is the small dataset and lack of field evidence.',
    'Results demonstrate reproducible storage across process restarts.',
]


def pdf_bytes(lines=None, *, metadata=True, pages=1, password=None):
    """Create a real, small text PDF; no external files or PDF services."""
    writer = PdfWriter()
    for _ in range(pages):
        page = writer.add_blank_page(width=612, height=792)
        font = DictionaryObject({NameObject('/Type'): NameObject('/Font'),
            NameObject('/Subtype'): NameObject('/Type1'),
            NameObject('/BaseFont'): NameObject('/Helvetica')})
        page[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'):
            DictionaryObject({NameObject('/F1'): writer._add_object(font)})})
        stream = DecodedStreamObject()
        selected = TEXT_LINES if lines is None else lines
        escaped = [s.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)') for s in selected]
        stream.set_data(('BT /F1 12 Tf 50 740 Td 16 TL ' +
            ' '.join(f'({line}) Tj T*' for line in escaped) + ' ET').encode('ascii'))
        page[NameObject('/Contents')] = writer._add_object(stream)
    if metadata:
        writer.add_metadata({'/Title': TEXT_LINES[0], '/Author': 'Alice Example; Bob Example'})
    if password:
        writer.encrypt(password)
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


class IsolatedApp(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix='papertrail-hw2-')
        self.addCleanup(self.directory.cleanup)
        self.config = {
            'TESTING': True, 'DATA_DIR': self.directory.name,
            'LLM_API_KEY': '', 'LLM_MODEL': 'test-model',
            'LLM_BASE_URL': 'https://provider.example.invalid/v1',
            'LLM_MAX_OUTPUT_TOKENS': 1800, 'LLM_TIMEOUT': 2,
            'LLM_REASONING_EFFORT': '', 'APP_USERNAME': '', 'APP_PASSWORD': '',
        }
        self.app = create_app(self.config)
        self.client = self.app.test_client()

    def save_paper(self, **changes):
        response = self.client.post('/api/papers', json=dict(PAPER, **changes))
        self.assertEqual(response.status_code, 201, response.json)
        return response.json['paper']

    def upload_paper(self, raw=None, filename='research.pdf'):
        response = self.client.post('/api/upload', data={
            'file': (io.BytesIO(pdf_bytes() if raw is None else raw), filename)})
        self.assertEqual(response.status_code, 201, response.json)
        return response.json['paper']

    def enable_model(self):
        llm = self.app.extensions['llm']
        llm.api_key = 'test-only-not-a-real-key'
        return llm

    def history(self, paper_id):
        return self.client.get(f'/api/papers/{paper_id}').json['paper']['analyses']

    def stored_pdfs(self):
        return list((Path(self.directory.name) / 'uploads').glob('*.pdf'))
