"""New HW2 initial tests of input boundaries, failures, and access control."""
import base64
import io
from datetime import date
from unittest.mock import patch

import requests
from initial_support import IsolatedCase, PAPER, llm_response, pdf_bytes
from app import create_app


class ValidationTests(IsolatedCase):
    def test_invalid_search_parameters_are_client_errors(self):
        cases = [
            {}, {'q': ' '}, {'q': 'x'}, {'q': 'x' * 201},
            {'q': 'testing', 'page': '0'}, {'q': 'testing', 'page': '101'},
            {'q': 'testing', 'page': '-1'}, {'q': 'testing', 'sort': 'title'},
            {'q': 'testing', 'page': '\u00b2'},
        ]
        with patch('app.search_papers') as search:
            for args in cases:
                with self.subTest(args=args):
                    response = self.client.get('/api/search', query_string=args)
                    self.assertEqual(response.status_code, 400, response.json)
                    self.assertIsInstance(response.json['error'], str)
            search.assert_not_called()

    def test_search_accepts_documented_length_and_page_boundaries(self):
        for query, page in [('ab', 1), ('x' * 200, 100)]:
            with self.subTest(length=len(query), page=page):
                payload = {'papers': [], 'total': 0, 'page': page, 'page_size': 10}
                with patch('app.search_papers', return_value=payload) as search:
                    response = self.client.get('/api/search', query_string={'q': query, 'page': page})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json, payload)
                search.assert_called_once_with(query, page, 'relevance')

    def test_invalid_metadata_is_rejected_without_changing_saved_record(self):
        paper = self.save()
        endpoint = f"/api/papers/{paper['id']}"
        cases = [
            {'title': ''}, {'title': ' '}, {'title': 'x' * 1001},
            {'authors': 'Ava Analyst'}, {'authors': None}, {'authors': [42]},
            {'authors': ['x' * 201]}, {'authors': ['A'] * 101},
            {'abstract': None}, {'abstract': 'x' * 12001},
            {'year': True}, {'year': False}, {'year': 1899},
            {'year': date.today().year + 2}, {'year': 'twenty twenty-five'},
        ]
        original = self.detail(paper['id'])
        for changes in cases:
            with self.subTest(field=next(iter(changes)), value=repr(next(iter(changes.values())))[:80]):
                response = self.client.patch(endpoint, json=dict(PAPER, **changes))
                self.assertEqual(response.status_code, 400, response.json)
                self.assertIsInstance(response.json['error'], str)
                self.assertEqual(self.detail(paper['id']), original)

    def test_invalid_save_payloads_do_not_create_records(self):
        for payload in [[], {}, dict(PAPER, source_id='../private'),
                        dict(PAPER, source_id=123), dict(PAPER, source_id=None),
                        dict(PAPER, category=[]), dict(PAPER, category='x' * 101)]:
            with self.subTest(payload=payload):
                response = self.client.post('/api/papers', json=payload)
                self.assertEqual(response.status_code, 400, response.json)
                self.assertIn('error', response.json)
                self.assertEqual(self.client.get('/api/papers').json['papers'], [])

    def test_invalid_uploads_report_errors_without_storing_files(self):
        cases = [
            (None, '', 'Choose a PDF'),
            (b'plain text', 'notes.txt', 'Choose a PDF'),
            (b'plain text', 'fake.pdf', 'valid PDF'),
            (b'%PDF-1.7\nbroken', 'broken.pdf', 'could not be read'),
            (pdf_bytes(blank=True), 'scan.pdf', 'OCR'),
            (pdf_bytes(password='fixture-password'), 'locked.pdf', 'password protected'),
        ]
        for raw, filename, message in cases:
            with self.subTest(filename=filename):
                data = {} if raw is None else {'file': (io.BytesIO(raw), filename)}
                response = self.client.post('/api/upload', data=data)
                self.assertEqual(response.status_code, 400, response.json)
                self.assertIn(message, response.json['error'])
                self.assertEqual(self.client.get('/api/papers').json['papers'], [])
                self.assertEqual(self.pdf_files(), [])

    def test_invalid_analysis_payloads_are_client_errors_without_provider_calls(self):
        paper = self.save()
        self.enable_llm()
        cases = [[], {}, {'kind': 'translate'}, {'kind': []}, {'kind': {}},
                 {'kind': 'question', 'question': ''},
                 {'kind': 'question', 'question': '  '},
                 {'kind': 'question', 'question': 'x' * 2001},
                 {'kind': 'question', 'question': 123}]
        with patch('app.download_paper') as download, patch('providers.requests.post') as post:
            for payload in cases:
                with self.subTest(payload=payload):
                    response = self.client.post(f"/api/papers/{paper['id']}/analyze", json=payload)
                    self.assertEqual(response.status_code, 400, response.json)
                    self.assertIsInstance(response.json['error'], str)
            download.assert_not_called()
            post.assert_not_called()
        self.assertEqual(self.detail(paper['id'])['analyses'], [])

    def test_missing_model_reports_setup_error_before_download(self):
        paper = self.save()
        with patch('app.download_paper') as download, patch('providers.requests.post') as post:
            response = self.client.post(f"/api/papers/{paper['id']}/analyze", json={'kind': 'summary'})
        self.assertEqual(response.status_code, 400)
        self.assertIn('Connect an AI model', response.json['error'])
        download.assert_not_called()
        post.assert_not_called()
        self.assertFalse(self.detail(paper['id'])['has_full_text'])
        self.assertEqual(self.detail(paper['id'])['analyses'], [])

    def test_search_timeout_is_actionable_and_leaves_library_unchanged(self):
        with patch('providers.requests.get', side_effect=requests.Timeout('synthetic timeout')):
            response = self.client.get('/api/search?q=testing')
        self.assertEqual(response.status_code, 400)
        self.assertIn('arXiv is unavailable', response.json['error'])
        self.assertEqual(self.client.get('/api/papers').json['papers'], [])

    def test_failed_pdf_download_leaves_content_unset(self):
        paper = self.save()
        with patch('providers.requests.get', side_effect=requests.ConnectionError('synthetic failure')):
            response = self.client.post(f"/api/papers/{paper['id']}/content")
        self.assertEqual(response.status_code, 400)
        self.assertIn('Could not download', response.json['error'])
        detail = self.detail(paper['id'])
        self.assertFalse(detail['has_pdf'])
        self.assertEqual(detail['pages'], [])
        self.assertEqual(self.pdf_files(), [])

    def test_llm_quota_error_is_not_cached_and_retry_can_succeed(self):
        paper = self.upload()
        self.enable_llm()
        endpoint = f"/api/papers/{paper['id']}/analyze"
        with patch('providers.requests.post', side_effect=[
                llm_response(status=429), llm_response(),
        ]) as post:
            failed = self.client.post(endpoint, json={'kind': 'summary'})
            self.assertEqual(failed.status_code, 400)
            self.assertIn('quota', failed.json['error'])
            self.assertEqual(self.detail(paper['id'])['analyses'], [])
            succeeded = self.client.post(endpoint, json={'kind': 'summary'})
        self.assertEqual(succeeded.status_code, 200, succeeded.json)
        self.assertFalse(succeeded.json['cached'])
        self.assertEqual(post.call_count, 2)
        self.assertEqual(len(self.detail(paper['id'])['analyses']), 1)

    def test_missing_papers_are_404_for_all_paper_operations(self):
        self.enable_llm()
        operations = [
            ('GET', '/api/papers/9999', None),
            ('PATCH', '/api/papers/9999', PAPER),
            ('DELETE', '/api/papers/9999', None),
            ('POST', '/api/papers/9999/content', None),
            ('GET', '/api/papers/9999/pdf', None),
            ('POST', '/api/papers/9999/analyze', {'kind': 'summary'}),
        ]
        for method, url, body in operations:
            with self.subTest(method=method, url=url):
                response = self.client.open(url, method=method, json=body)
                self.assertEqual(response.status_code, 404, response.json)
                self.assertIn('library', response.json['error'])

    def test_pdf_without_loaded_content_is_actionable(self):
        paper = self.save()
        response = self.client.get(f"/api/papers/{paper['id']}/pdf")
        self.assertEqual(response.status_code, 400)
        self.assertIn('Load the full text', response.json['error'])

    def test_basic_auth_requires_correct_credentials(self):
        config = dict(self.config, APP_USERNAME='fixture-user', APP_PASSWORD='fixture-password')
        client = create_app(config).test_client()
        for credentials in [None, 'fixture-user:incorrect']:
            with self.subTest(credentials=credentials):
                headers = {} if credentials is None else {
                    'Authorization': 'Basic ' + base64.b64encode(credentials.encode()).decode(),
                }
                response = client.get('/api/papers', headers=headers)
                self.assertEqual(response.status_code, 401)
                self.assertIn('Basic realm=', response.headers['WWW-Authenticate'])
        encoded = base64.b64encode(b'fixture-user:fixture-password').decode()
        response = client.get('/api/papers', headers={'Authorization': 'Basic ' + encoded})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['papers'], [])
        with self.assertRaisesRegex(RuntimeError, 'Set both'):
            create_app(dict(self.config, APP_USERNAME='fixture-user', APP_PASSWORD=''))

    def test_cross_origin_changes_are_denied_but_same_origin_is_allowed(self):
        denied = self.client.post('/api/papers', json=PAPER,
                                  headers={'Origin': 'https://other.example.invalid'})
        self.assertEqual(denied.status_code, 403)
        self.assertIn('Cross-origin', denied.json['error'])
        self.assertEqual(self.client.get('/api/papers').json['papers'], [])
        allowed = self.client.post('/api/papers', json=PAPER, headers={'Origin': 'http://localhost'})
        self.assertEqual(allowed.status_code, 201)
        self.assertEqual(len(self.client.get('/api/papers').json['papers']), 1)
