"""Execution- and coverage-guided round 2 provider and failure-state tests."""
from contextlib import contextmanager
import hashlib
from pathlib import Path
import tempfile
from unittest.mock import call, patch

import requests
from initial_support import IsolatedCase, pdf_bytes
from app import create_app
import database
from pdf_tools import PaperError
import providers
from pdf_fixtures_round1 import PDF_BYTE_LIMIT, pad_pdf
from provider_fixtures_round2 import (
    ControlledClock, DOWNLOAD_OPTIONS, PDF_URL, SEARCH_URL, StreamResponse,
    atom_feed, chunks_of, feed_response, paper,
)


@contextmanager
def controlled_search():
    clock = ControlledClock()
    # Initialize isolated provider state; the actual cache/throttle code runs.
    with patch('providers.time', clock), patch('providers._cache', {}), \
            patch('providers._last_search', 0.0):
        yield clock


class ProviderCase(IsolatedCase):
    def fresh_storage(self):
        directory = tempfile.TemporaryDirectory(prefix='papertrail-round2-case-')
        self.addCleanup(directory.cleanup)
        self.directory = Path(directory.name)
        self.config = dict(self.config, DATA_DIR=directory.name, LLM_API_KEY='')
        self.app = create_app(self.config)
        self.client = self.app.test_client()

    def assert_search_result(self, result, expected_papers, *, page=1, total=None):
        self.assertEqual(result, {
            'papers': expected_papers, 'total': len(expected_papers) if total is None else total,
            'page': page, 'page_size': 10,
        })

    def assert_search_request(self, recorded_call, params):
        self.assertEqual(recorded_call.args, (SEARCH_URL,))
        self.assertEqual(recorded_call.kwargs['params'], params)
        self.assertEqual(recorded_call.kwargs['timeout'], (10, 40))

    def assert_unchanged_paper(self, paper_id, before, before_row):
        self.assertEqual(self.detail(paper_id), before)
        self.assertFalse(before['has_pdf'])
        self.assertFalse(before['has_full_text'])
        self.assertEqual(before['pages'], [])
        self.assertEqual(before['analyses'], [])
        self.assertEqual(list((self.directory / 'uploads').rglob('*')), [])
        with database.connect(self.app.extensions['db_path']) as db:
            row = dict(db.execute('SELECT * FROM papers WHERE id=?', (paper_id,)).fetchone())
            self.assertEqual(row, before_row)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM papers').fetchone()[0], 1)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM analyses').fetchone()[0], 0)


class SearchTimingTests(ProviderCase):
    def test_cache_reuses_before_expiry_and_refreshes_at_and_after_ten_minutes(self):
        editions = [paper('2501.00001', 'First edition'),
                    paper('2501.00002', 'At expiry edition'),
                    paper('2501.00003', 'After expiry edition')]
        responses = [feed_response(atom_feed([p], total=1)) for p in editions]
        with controlled_search() as clock, \
                patch('providers.requests.get', side_effect=responses) as get:
            first = providers.search_papers('graph testing')
            self.assert_search_result(first, [editions[0]])
            clock.now = 1599.99
            self.assert_search_result(providers.search_papers('graph testing'), [editions[0]])
            self.assertEqual(get.call_count, 1)
            clock.now = 1600.0  # Exactly 600 seconds since the cached response.
            self.assert_search_result(providers.search_papers('graph testing'), [editions[1]])
            self.assertEqual(get.call_count, 2)
            clock.now = 2199.99
            self.assert_search_result(providers.search_papers('graph testing'), [editions[1]])
            self.assertEqual(get.call_count, 2)
            clock.now = 2200.25  # 600.25 seconds since the refreshed response.
            self.assert_search_result(providers.search_papers('graph testing'), [editions[2]])
            self.assertEqual(get.call_count, 3)
            clock.sleep.assert_not_called()
        for recorded_call in get.call_args_list:
            self.assert_search_request(recorded_call, {
                'start': 0, 'max_results': 10, 'search_query': 'all:graph AND all:testing',
                'sortBy': 'relevance', 'sortOrder': 'descending',
            })

    def test_cache_keys_separate_query_page_and_sort_results(self):
        cases = [('graph testing', 1, 'relevance'), ('graph storage', 1, 'relevance'),
                 ('graph testing', 2, 'relevance'), ('graph testing', 1, 'submittedDate')]
        papers = [paper(f'2501.1000{index}', f'Isolated result {index}') for index in range(4)]
        responses = [feed_response(atom_feed([p], total=31)) for p in papers]
        with controlled_search() as clock, \
                patch('providers.requests.get', side_effect=responses) as get:
            for index, ((query, page, sort), expected) in enumerate(zip(cases, papers)):
                with self.subTest(query=query, page=page, sort=sort):
                    clock.advance(4)
                    result = providers.search_papers(query, page, sort)
                    self.assert_search_result(result, [expected], page=page, total=31)
                    self.assertEqual(get.call_count, index + 1)
                    terms = 'all:graph AND all:' + ('storage' if 'storage' in query else 'testing')
                    self.assert_search_request(get.call_args, {
                        'start': (page - 1) * 10, 'max_results': 10, 'search_query': terms,
                        'sortBy': sort, 'sortOrder': 'descending',
                    })
            for (query, page, sort), expected in zip(cases, papers):
                with self.subTest(revisit=(query, page, sort)):
                    clock.advance(4)
                    self.assert_search_result(providers.search_papers(query, page, sort),
                                              [expected], page=page, total=31)
                    self.assertEqual(get.call_count, 4)
            clock.sleep.assert_not_called()

    def test_throttle_waits_only_for_the_missing_interval_without_real_sleep(self):
        expected = paper('2501.23456', 'Throttle evidence')
        request_times = []
        with controlled_search() as clock:
            def respond(*args, **kwargs):
                request_times.append(clock.now)
                return feed_response(atom_feed([expected], total=1))
            with patch('providers.requests.get', side_effect=respond) as get:
                for query, at in [('first query', 1000.0), ('second query', 1001.0),
                                  ('third query', 1007.0)]:
                    clock.now = at
                    self.assert_search_result(providers.search_papers(query), [expected])
                self.assertEqual(get.call_count, 3)
            clock.sleep.assert_called_once()
            self.assertAlmostEqual(clock.sleep.call_args.args[0], 2.1)
        self.assertAlmostEqual(request_times[0], 1000.0)
        self.assertAlmostEqual(request_times[1], 1003.1)
        self.assertAlmostEqual(request_times[2], 1007.0)
        self.assertGreaterEqual(request_times[1] - request_times[0] + 1e-9, 3.1)
        for recorded_call, word in zip(get.call_args_list, ('first', 'second', 'third')):
            self.assert_search_request(recorded_call, {
                'start': 0, 'max_results': 10, 'search_query': f'all:{word} AND all:query',
                'sortBy': 'relevance', 'sortOrder': 'descending',
            })


class DownloadTests(ProviderCase):
    def test_permitted_relative_and_arxiv_redirects_return_exact_streamed_pdf(self):
        raw = pdf_bytes()
        responses = [StreamResponse(status=302, location='/pdf/2501.01234v2'),
                     StreamResponse(status=303, location='https://export.arxiv.org/pdf/2501.01234v2'),
                     StreamResponse([raw[:100], b'', raw[100:]])]
        with patch('providers.requests.get', side_effect=responses) as get:
            result = providers.download_paper('2501.01234')
        self.assertEqual(result, raw)
        self.assertEqual(get.call_args_list, [
            call(PDF_URL, **DOWNLOAD_OPTIONS),
            call('https://arxiv.org/pdf/2501.01234v2', **DOWNLOAD_OPTIONS),
            call('https://export.arxiv.org/pdf/2501.01234v2', **DOWNLOAD_OPTIONS),
        ])
        self.assertTrue(all(response.closed for response in responses))
        self.assertEqual([response.iterations for response in responses], [0, 0, 1])

    def test_streamed_download_accepts_size_limit_and_rejects_one_extra_byte(self):
        base = pdf_bytes()
        for size in (PDF_BYTE_LIMIT, PDF_BYTE_LIMIT + 1):
            with self.subTest(streamed_bytes=size):
                raw = pad_pdf(base, size)
                response = StreamResponse(chunks_of(raw))
                with patch('providers.requests.get', return_value=response) as get:
                    if size == PDF_BYTE_LIMIT:
                        result = providers.download_paper('2501.01234')
                        self.assertEqual(len(result), size)
                        self.assertEqual(hashlib.sha256(result).digest(), hashlib.sha256(raw).digest())
                    else:
                        with self.assertRaisesRegex(PaperError, 'exceeds the 20 MB limit'):
                            providers.download_paper('2501.01234')
                get.assert_called_once_with(PDF_URL, **DOWNLOAD_OPTIONS)
                self.assertTrue(response.closed)
                self.assertEqual(response.iterations, 1)

    def test_failed_transfers_and_redirect_exhaustion_preserve_saved_paper_state(self):
        raw = pdf_bytes()
        for label in ('interrupted stream', 'oversized stream', 'redirect exhaustion', 'upstream HTTP failure'):
            with self.subTest(failure=label):
                self.fresh_storage()
                saved = self.save()
                endpoint = f"/api/papers/{saved['id']}/content"
                before = self.detail(saved['id'])
                with database.connect(self.app.extensions['db_path']) as db:
                    before_row = dict(db.execute('SELECT * FROM papers WHERE id=?', (saved['id'],)).fetchone())
                responses = []

                def respond(*args, **kwargs):
                    # Eight is a fixture guard against an unbounded loop, not
                    # a specification of how many redirects the app must allow.
                    if len(responses) >= 8:
                        raise AssertionError('Download failed to bound redirect retries')
                    if label == 'interrupted stream':
                        def interrupted():
                            yield raw  # Even a readable prefix must not be saved after a transport failure.
                            raise requests.exceptions.ChunkedEncodingError('Synthetic interrupted body')
                        response = StreamResponse(interrupted)
                    elif label == 'oversized stream':
                        response = StreamResponse(chunks_of(pad_pdf(raw, PDF_BYTE_LIMIT + 1)))
                    elif label == 'redirect exhaustion':
                        response = StreamResponse(status=302, location='/pdf/2501.01234')
                    else:
                        response = StreamResponse(status=503)
                    responses.append(response)
                    return response

                with patch('providers.requests.get', side_effect=respond) as get:
                    failed = self.client.post(endpoint)
                self.assertEqual(failed.status_code, 400, failed.json)
                self.assertEqual(set(failed.json), {'error'})
                message = ('exceeds the 20 MB limit' if label == 'oversized stream' else
                           'redirected too many times' if label == 'redirect exhaustion' else
                           'Could not download this paper')
                self.assertIn(message, failed.json['error'])
                self.assertGreaterEqual(get.call_count, 1)
                self.assertLessEqual(get.call_count, 8)
                self.assertEqual(get.call_args_list, [call(PDF_URL, **DOWNLOAD_OPTIONS)] * get.call_count)
                self.assertTrue(all(response.closed for response in responses))
                self.assert_unchanged_paper(saved['id'], before, before_row)
                if label == 'interrupted stream':
                    # A clean retry must download again, rather than trust/cache
                    # the complete-looking bytes from the interrupted response.
                    with patch('providers.requests.get', return_value=StreamResponse(chunks_of(raw))) as retry:
                        success = self.client.post(endpoint)
                    retry.assert_called_once_with(PDF_URL, **DOWNLOAD_OPTIONS)
                    self.assertEqual(success.status_code, 200, success.json)
                    self.assertTrue(success.json['paper']['has_full_text'])
                    self.assertTrue(success.json['paper']['has_pdf'])
                    self.assertEqual(success.json['paper']['page_count'], 2)
                    self.assertIn('HAWK benchmark', success.json['paper']['pages'][1]['text'])
                    files = list((self.directory / 'uploads').iterdir())
                    self.assertEqual(len(files), 1)
                    self.assertEqual(files[0].read_bytes(), raw)
                    self.assertEqual(self.detail(saved['id'])['analyses'], [])


class ProviderErrorTests(ProviderCase):
    def test_malformed_and_error_feeds_are_not_cached_or_returned_as_success(self):
        recovered = paper('2501.01234', 'Recovered search result')
        cases = [('malformed XML', b'<feed', 'arXiv is unavailable'),
                 ('error entry', atom_feed([recovered], total=1, error_entry=True),
                  'arXiv could not process this search')]
        for label, bad_feed, error in cases:
            with self.subTest(feed=label):
                self.fresh_storage()
                saved = self.save()
                before = self.detail(saved['id'])
                with database.connect(self.app.extensions['db_path']) as db:
                    before_row = dict(db.execute('SELECT * FROM papers WHERE id=?', (saved['id'],)).fetchone())
                with controlled_search(), patch('providers.requests.get', side_effect=[
                        feed_response(bad_feed), feed_response(atom_feed([recovered], total=1)),
                ]) as get:
                    failed = self.client.get('/api/search?q=feed+testing')
                    self.assertEqual(failed.status_code, 400, failed.json)
                    self.assertEqual(set(failed.json), {'error'})
                    self.assertIn(error, failed.json['error'])
                    self.assert_unchanged_paper(saved['id'], before, before_row)
                    retry = self.client.get('/api/search?q=feed+testing')
                    cached = self.client.get('/api/search?q=feed+testing')
                    self.assertEqual(retry.status_code, 200, retry.json)
                    self.assertEqual(cached.status_code, 200, cached.json)
                    self.assert_search_result(retry.json, [dict(recovered, saved_id=saved['id'])])
                    self.assertEqual(cached.json, retry.json)
                    self.assertEqual(get.call_count, 2)
                self.assert_unchanged_paper(saved['id'], before, before_row)
                for recorded_call in get.call_args_list:
                    self.assert_search_request(recorded_call, {
                        'start': 0, 'max_results': 10, 'search_query': 'all:feed AND all:testing',
                        'sortBy': 'relevance', 'sortOrder': 'descending',
                    })

    def test_non_arxiv_entries_are_ignored_while_valid_unknown_fields_are_preserved(self):
        expected = dict(paper('2501.99999', 'Known paper with unknown fields'),
                        authors=[], year=None, category='')
        with controlled_search(), patch('providers.requests.get', return_value=feed_response(
                atom_feed([expected], invalid_entry=True))) as get:
            result = providers.search_papers('unknown fields')
        self.assert_search_result(result, [expected])
        get.assert_called_once()

    def test_punctuation_only_search_reports_input_error_without_http(self):
        with controlled_search(), patch('providers.requests.get') as get:
            response = self.client.get('/api/search', query_string={'q': '!!!'})
        self.assertEqual(response.status_code, 400, response.json)
        self.assertEqual(set(response.json), {'error'})
        self.assertIn('research topic, keywords, or an arXiv ID', response.json['error'])
        get.assert_not_called()
        self.assertEqual(self.client.get('/api/papers').json['papers'], [])

    def test_direct_unconfigured_llm_client_fails_before_http(self):
        for key, model in [('', 'unit-test-model'), ('dummy-test-key', '')]:
            with self.subTest(key_present=bool(key), model=model):
                llm = providers.LLM(dict(self.config, LLM_API_KEY=key, LLM_MODEL=model))
                self.assertFalse(llm.configured)
                with patch('providers.requests.post') as post:
                    with self.assertRaisesRegex(PaperError, 'Connect an AI model first'):
                        llm.complete('system', 'Synthetic paper evidence.', 'A question')
                post.assert_not_called()
