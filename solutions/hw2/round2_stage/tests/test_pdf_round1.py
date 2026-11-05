"""Round 1 additions: real PDF limits, fallback metadata, and enrichment failure."""
import hashlib
import io
import json
from pathlib import Path
import tempfile
from unittest.mock import patch

from pypdf import PdfReader
import requests

from initial_support import IsolatedCase, llm_response
from app import create_app
import database
from pdf_fixtures_round1 import (
    ABSTRACT, AUTHORS, BODY, PAGE_LIMIT, PDF_BYTE_LIMIT, TEXT_LIMIT, TITLE,
    limit_pdf, metadata_pdf, pad_pdf,
)


class PDFCase(IsolatedCase):
    def fresh_storage(self):
        """Independent database/files for each table row, including failed rows."""
        directory = tempfile.TemporaryDirectory(prefix='papertrail-round1-case-')
        self.addCleanup(directory.cleanup)
        self.directory = Path(directory.name)
        self.config = dict(self.config, DATA_DIR=directory.name, LLM_API_KEY='')
        self.app = create_app(self.config)
        self.client = self.app.test_client()

    def post_pdf(self, raw):
        return self.client.post('/api/upload', data={
            'file': (io.BytesIO(raw), 'round1-synthetic.pdf'),
        })

    def assert_no_storage(self):
        response = self.client.get('/api/papers')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['papers'], [])
        with database.connect(self.app.extensions['db_path']) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM papers').fetchone()[0], 0)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM analyses').fetchone()[0], 0)
        # Inspect all stored entries, not just files matching a .pdf suffix.
        self.assertEqual(list((self.directory / 'uploads').rglob('*')), [])

    def assert_stored(self, response, raw, *, page_count):
        self.assertEqual(response.status_code, 201, response.json)
        self.assertTrue(response.json['created'])
        paper = response.json['paper']
        self.assertTrue(paper['has_pdf'])
        self.assertTrue(paper['has_full_text'])
        self.assertEqual(paper['page_count'], page_count)
        detail = self.detail(paper['id'])
        self.assertEqual(detail['analyses'], [])
        self.assertEqual([p['page'] for p in detail['pages']], list(range(1, page_count + 1)))
        files = list((self.directory / 'uploads').iterdir())
        self.assertEqual(len(files), 1)
        self.assertTrue(files[0].is_file())
        self.assertEqual(hashlib.sha256(files[0].read_bytes()).digest(), hashlib.sha256(raw).digest())
        with database.connect(self.app.extensions['db_path']) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM papers').fetchone()[0], 1)
            row = db.execute('SELECT * FROM papers WHERE id=?', (paper['id'],)).fetchone()
            self.assertEqual(json.loads(row['pages']), detail['pages'])
            self.assertEqual(json.loads(row['authors']), paper['authors'])
            for field in ('title', 'year', 'abstract', 'metadata_method'):
                self.assertEqual(row[field], paper[field], field)
        return detail

    def assert_fallback_metadata(self, paper, *, authors=AUTHORS, year=2024):
        self.assertEqual(paper['title'], TITLE)
        self.assertEqual(paper['authors'], authors)
        self.assertEqual(paper['year'], year)
        self.assertEqual(paper['abstract'], ABSTRACT)
        self.assertIn('PDF text', paper['metadata_method'])
        self.assertNotIn('AI extraction', paper['metadata_method'])


class PDFLimitTests(PDFCase):
    def test_pdf_file_size_boundary_is_accepted_and_one_extra_byte_is_rejected(self):
        base = limit_pdf(['Synthetic file size evidence. ' * 12])
        for size, accepted in [(PDF_BYTE_LIMIT, True), (PDF_BYTE_LIMIT + 1, False)]:
            with self.subTest(pdf_bytes=size):
                self.fresh_storage()
                raw = pad_pdf(base, size)
                self.assertEqual(len(raw), size)
                with patch('providers.requests.get') as get, patch('providers.requests.post') as post:
                    response = self.post_pdf(raw)
                get.assert_not_called()
                post.assert_not_called()
                if accepted:
                    detail = self.assert_stored(response, raw, page_count=1)
                    self.assertEqual(detail['pages'][0]['text'], 'Synthetic file size evidence. ' * 12)
                else:
                    self.assertEqual(response.status_code, 400, response.json)
                    self.assertIn('20 MB', response.json['error'])
                    self.assert_no_storage()

    def test_oversized_multipart_request_returns_413_without_storage(self):
        # Separately exercise Flask's real 21 MiB request cap, including overhead.
        raw = pad_pdf(limit_pdf(['Synthetic request size evidence. ' * 12]),
                      PDF_BYTE_LIMIT + 1024 * 1024 + 1)
        with patch('providers.requests.get') as get, patch('providers.requests.post') as post:
            response = self.post_pdf(raw)
        self.assertEqual(response.status_code, 413, response.json)
        self.assertIn('20 MB', response.json['error'])
        get.assert_not_called()
        post.assert_not_called()
        self.assert_no_storage()

    def test_page_count_accepts_one_and_150_and_rejects_zero_and_151(self):
        for count in (1, PAGE_LIMIT, 0, PAGE_LIMIT + 1):
            with self.subTest(pages=count):
                self.fresh_storage()
                texts = [f'Synthetic page {number:03d}. ' + 'Readable boundary evidence. ' * 10
                         for number in range(1, count + 1)]
                raw = limit_pdf(texts)
                with patch('providers.requests.get') as get, patch('providers.requests.post') as post:
                    response = self.post_pdf(raw)
                get.assert_not_called()
                post.assert_not_called()
                if count in (1, PAGE_LIMIT):
                    detail = self.assert_stored(response, raw, page_count=count)
                    self.assertEqual([p['text'] for p in detail['pages']], texts)
                else:
                    self.assertEqual(response.status_code, 400, response.json)
                    self.assertIn('1 to 150 pages', response.json['error'])
                    self.assert_no_storage()

    def test_total_extracted_text_at_limit_and_one_character_either_side(self):
        for total in (TEXT_LIMIT - 1, TEXT_LIMIT, TEXT_LIMIT + 1):
            with self.subTest(extracted_characters=total):
                self.fresh_storage()
                # Single Tj per page: no generated newline. Both pages together
                # reach the limit, proving it is cumulative rather than per-page.
                texts = ['A' * (TEXT_LIMIT // 2), 'B' * (total - TEXT_LIMIT // 2)]
                raw = limit_pdf(texts)
                with patch('providers.requests.get') as get, patch('providers.requests.post') as post:
                    response = self.post_pdf(raw)
                get.assert_not_called()
                post.assert_not_called()
                if total <= TEXT_LIMIT:
                    detail = self.assert_stored(response, raw, page_count=2)
                    self.assertEqual(sum(len(p['text']) for p in detail['pages']), total)
                    for page, expected in zip(detail['pages'], texts):
                        self.assertEqual(len(page['text']), len(expected))
                        self.assertEqual(hashlib.sha256(page['text'].encode()).digest(),
                                         hashlib.sha256(expected.encode()).digest())
                else:
                    self.assertEqual(response.status_code, 400, response.json)
                    self.assertIn('one-million-character', response.json['error'])
                    self.assert_no_storage()


class PDFMetadataTests(PDFCase):
    def test_pdf_without_document_metadata_extracts_clear_title_byline_and_date(self):
        raw = metadata_pdf()
        self.assertIsNone(PdfReader(io.BytesIO(raw)).metadata)
        with patch('providers.requests.get') as get, patch('providers.requests.post') as post:
            response = self.post_pdf(raw)
        get.assert_not_called()
        post.assert_not_called()
        detail = self.assert_stored(response, raw, page_count=1)
        self.assert_fallback_metadata(detail)
        for evidence in (TITLE, 'Dana Tester and Evan Researcher', 'Conference 2024', BODY):
            self.assertIn(evidence, detail['pages'][0]['text'])
        self.assertNotEqual(detail['year'], 2018)  # Dataset year is not publication evidence.

    def test_multiline_prominent_title_is_not_misidentified_as_an_author(self):
        raw = metadata_pdf(multiline=True)
        self.assertIsNone(PdfReader(io.BytesIO(raw)).metadata)
        with patch('providers.requests.get') as get, patch('providers.requests.post') as post:
            response = self.post_pdf(raw)
        get.assert_not_called()
        post.assert_not_called()
        detail = self.assert_stored(response, raw, page_count=1)
        self.assertIn('Reliable Storage for\nResearch Libraries', detail['pages'][0]['text'])
        self.assert_fallback_metadata(detail)

    def test_absent_author_and_publication_year_are_not_invented(self):
        raw = metadata_pdf(unknown_fields=True)
        self.assertIsNone(PdfReader(io.BytesIO(raw)).metadata)
        with patch('providers.requests.get') as get, patch('providers.requests.post') as post:
            response = self.post_pdf(raw)
        get.assert_not_called()
        post.assert_not_called()
        detail = self.assert_stored(response, raw, page_count=1)
        self.assert_fallback_metadata(detail, authors=[], year=None)
        self.assertIn('dataset was collected in 2018', detail['pages'][0]['text'])


class PDFEnrichmentTests(PDFCase):
    def test_optional_ai_metadata_failures_preserve_pdf_fallback_and_review_notice(self):
        cases = [
            ('transport timeout', None, requests.Timeout('synthetic timeout')),
            ('invalid JSON', llm_response('not JSON'), None),
            ('JSON non-object', llm_response('[]'), None),
            ('invalid metadata fields', llm_response(json.dumps({
                'title': 'AI title must not leak into fallback', 'authors': 'not a list',
                'year': 2023, 'abstract': 'AI abstract must not leak into fallback.',
            })), None),
        ]
        for label, provider_response, error in cases:
            with self.subTest(failure=label):
                self.fresh_storage()
                self.enable_llm()
                raw = metadata_pdf()
                with patch('providers.requests.get') as get, \
                        patch('providers.requests.post', return_value=provider_response,
                              side_effect=error) as post:
                    response = self.post_pdf(raw)
                    detail = self.assert_stored(response, raw, page_count=1)
                    self.assert_fallback_metadata(detail)
                    self.assertNotIn('error', response.json)
                    self.assertIn('AI metadata was unavailable', response.json['notice'])
                    self.assertIn('review', response.json['notice'])
                    restarted = create_app(self.config).test_client()
                    persisted = restarted.get(f"/api/papers/{detail['id']}").json['paper']
                    self.assertEqual(persisted, detail)
                    duplicate = self.post_pdf(raw)
                    self.assertEqual(duplicate.status_code, 200)
                    self.assertFalse(duplicate.json['created'])
                    self.assertEqual(duplicate.json['paper'], response.json['paper'])
                get.assert_not_called()  # Fixture has no arXiv identifier.
                post.assert_called_once()
                self.assertEqual(post.call_args.args[0], 'https://llm.example.invalid/v1/chat/completions')
                self.assertEqual(post.call_args.kwargs['timeout'], (10, 2))
                self.assertEqual(post.call_args.kwargs['headers']['Authorization'], 'Bearer dummy-test-key')
                payload = post.call_args.kwargs['json']
                self.assertEqual(payload['model'], 'unit-test-model')
                self.assertIn('Extract bibliographic metadata', payload['messages'][0]['content'])
                self.assertIn(TITLE, payload['messages'][1]['content'])
                self.assertIn(ABSTRACT, payload['messages'][1]['content'])
                self.assertIn('Conference 2024', payload['messages'][1]['content'])
