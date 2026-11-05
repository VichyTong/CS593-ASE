"""Round 1: follow coverage gaps into real provider and PDF logic."""
import io
import unittest
from unittest.mock import MagicMock, Mock, patch

import requests
import providers
from pdf_tools import MAX_PDF_BYTES, PaperError, cited_pages, extract_metadata, extract_pdf, select_context
from providers import LLM, download_paper, search_papers
from support import IsolatedApp, PAPER, pdf_bytes


FEED = b'''<feed xmlns="http://www.w3.org/2005/Atom"
 xmlns:o="http://a9.com/-/spec/opensearch/1.1/">
 <o:totalResults>21</o:totalResults><entry>
 <id>http://arxiv.org/abs/2501.01234v2</id>
 <title> Reliable\n Research Workflows </title>
 <author><name>Alice Example</name></author><author><name>Bob Example</name></author>
 <published>2025-01-02T00:00:00Z</published>
 <summary>A controlled study.</summary><category term="cs.SE"/>
 </entry><entry><id>http://example.invalid/not-a-paper</id></entry></feed>'''


def search_response(content=FEED):
    response = Mock()
    response.content = content
    return response


def download_response(*, chunks=(b'%PDF-fixture',), redirect=None):
    response = MagicMock()
    response.__enter__.return_value = response
    response.is_redirect = redirect is not None
    response.headers = {'Location': redirect} if redirect else {}
    response.iter_content.return_value = iter(chunks)
    return response


class SearchProviderTests(unittest.TestCase):
    def setUp(self):
        self.addCleanup(patch.stopall)
        patch('providers._cache', {}).start()
        patch('providers._last_search', 0.0).start()
        patch('providers.time.monotonic', return_value=1000.0).start()
        self.sleep = patch('providers.time.sleep').start()

    def test_atom_feed_maps_real_bibliographic_fields(self):
        with patch('providers.requests.get', return_value=search_response()):
            result = search_papers('reliable research')
        self.assertEqual(result['total'], 21)
        self.assertEqual(len(result['papers']), 1)
        paper = result['papers'][0]
        self.assertEqual(paper['source_id'], '2501.01234')
        self.assertEqual(paper['title'], PAPER['title'])
        self.assertEqual(paper['authors'], PAPER['authors'])
        self.assertEqual(paper['year'], 2025)
        self.assertEqual(paper['url'], 'https://arxiv.org/abs/2501.01234')

    def test_keyword_query_pagination_sort_and_stop_words(self):
        with patch('providers.requests.get', return_value=search_response()) as get:
            result = search_papers('Attention Is All You Need', page=3, sort='submittedDate')
        params = get.call_args.kwargs['params']
        self.assertEqual(params['search_query'], 'all:Attention AND all:Need')
        self.assertEqual(params['start'], 20)
        self.assertEqual(params['sortBy'], 'submittedDate')
        self.assertEqual(result['page'], 3)

    def test_identifiers_and_arxiv_links_use_id_lookup(self):
        for query, expected in [('2501.01234v2', '2501.01234v2'),
                                ('https://arxiv.org/abs/2501.01234', '2501.01234'),
                                ('hep-th/9901001', 'hep-th/9901001')]:
            with self.subTest(query=query), patch('providers.requests.get', return_value=search_response()) as get:
                search_papers(query)
                self.assertEqual(get.call_args.kwargs['params']['id_list'], expected)
                self.assertNotIn('search_query', get.call_args.kwargs['params'])

    def test_fresh_search_cache_avoids_second_request(self):
        with patch('providers.requests.get', return_value=search_response()) as get:
            first = search_papers('reliable')
            second = search_papers(' reliable ')
        self.assertEqual(first, second)
        self.assertEqual(get.call_count, 1)

    def test_expired_cache_refreshes_and_searches_are_throttled(self):
        providers._cache[('reliable', 1, 'relevance')] = (0.0, {'papers': []})
        providers._last_search = 999.0
        with patch('providers.requests.get', return_value=search_response()) as get:
            result = search_papers('reliable')
        get.assert_called_once()
        self.sleep.assert_called_once()
        self.assertAlmostEqual(self.sleep.call_args.args[0], 2.1)
        self.assertEqual(result['total'], 21)

    def test_empty_token_query_is_actionable(self):
        with patch('providers.requests.get') as get, self.assertRaisesRegex(PaperError, 'topic'):
            search_papers('!!!')
        get.assert_not_called()

    def test_timeout_and_invalid_xml_become_actionable_errors(self):
        with patch('providers.requests.get', side_effect=requests.Timeout()), self.assertRaisesRegex(PaperError, 'unavailable'):
            search_papers('timeout')
        with patch('providers.requests.get', return_value=search_response(b'<broken>')), self.assertRaisesRegex(PaperError, 'unavailable'):
            search_papers('broken xml')

    def test_arxiv_error_entry_does_not_look_like_empty_success(self):
        feed = b'<feed xmlns="http://www.w3.org/2005/Atom"><entry><id>http://arxiv.org/api/errors#bad_query</id></entry></feed>'
        with patch('providers.requests.get', return_value=search_response(feed)), self.assertRaisesRegex(PaperError, 'simpler keywords'):
            search_papers('provider error')


class DownloadProviderTests(unittest.TestCase):
    def test_invalid_id_never_starts_download(self):
        with patch('providers.requests.get') as get, self.assertRaisesRegex(PaperError, 'Invalid'):
            download_paper('../../private')
        get.assert_not_called()

    def test_allowed_redirect_streams_exact_bytes(self):
        redirect = download_response(redirect='https://export.arxiv.org/pdf/2501.01234')
        final = download_response(chunks=(b'%PDF-', b'paper-text'))
        with patch('providers.requests.get', side_effect=[redirect, final]) as get:
            raw = download_paper('2501.01234')
        self.assertEqual(raw, b'%PDF-paper-text')
        self.assertEqual(get.call_args.args[0], 'https://export.arxiv.org/pdf/2501.01234')
        self.assertFalse(get.call_args.kwargs['allow_redirects'])

    def test_redirect_rejects_untrusted_hosts_http_and_ports(self):
        for url in ('https://unrelated.example/paper.pdf', 'http://arxiv.org/pdf/x', 'https://arxiv.org:8443/pdf/x'):
            with self.subTest(url=url), patch('providers.requests.get', return_value=download_response(redirect=url)) as get:
                with self.assertRaisesRegex(PaperError, 'Unexpected PDF location'):
                    download_paper('2501.01234')
                self.assertEqual(get.call_count, 1)

    def test_streaming_download_rejects_over_twenty_megabytes(self):
        response = download_response(chunks=(b'x' * MAX_PDF_BYTES, b'y'))
        with patch('providers.requests.get', return_value=response), self.assertRaisesRegex(PaperError, '20 MB'):
            download_paper('2501.01234')

    def test_redirect_loop_is_bounded(self):
        with patch('providers.requests.get', side_effect=lambda *a, **k: download_response(redirect='/pdf/2501.01234')) as get:
            with self.assertRaisesRegex(PaperError, 'too many'):
                download_paper('2501.01234')
        self.assertEqual(get.call_count, 4)

    def test_network_failure_has_manual_upload_guidance(self):
        with patch('providers.requests.get', side_effect=requests.ConnectionError()), self.assertRaisesRegex(PaperError, 'upload a PDF'):
            download_paper('2501.01234')


class LLMProviderTests(IsolatedApp):
    def model(self, **changes):
        return LLM(dict(self.config, LLM_API_KEY='test-only-not-a-real-key', **changes))

    def test_http_contract_sends_context_and_question(self):
        response = Mock(status_code=200)
        response.json.return_value = {'choices': [{'message': {'content': ' Grounded answer. '}, 'finish_reason': 'stop'}]}
        llm = self.model(LLM_MODEL='gpt-6-luna')
        with patch('providers.requests.post', return_value=response) as post:
            self.assertEqual(llm.complete('system rules', '[p. 1] actual text', 'question?'), 'Grounded answer.')
        body = post.call_args.kwargs['json']
        self.assertEqual(body['messages'], [{'role': 'system', 'content': 'system rules'},
            {'role': 'user', 'content': '[p. 1] actual text'}, {'role': 'user', 'content': 'question?'}])
        self.assertEqual(body['model'], 'gpt-6-luna')
        self.assertEqual(body['max_completion_tokens'], 1800)
        self.assertEqual(body['reasoning_effort'], 'none')
        self.assertTrue(post.call_args.args[0].endswith('/v1/chat/completions'))

    def test_missing_credentials_prevent_network_request(self):
        with patch('providers.requests.post') as post, self.assertRaisesRegex(PaperError, 'Connect an AI model'):
            LLM(self.config).complete('system', 'text')
        post.assert_not_called()

    def test_insecure_or_credential_bearing_endpoints_are_rejected(self):
        for url in ('http://provider.example/v1', 'https://name:password@example.com/v1',
                    'https://example.com/v1?secret=x', 'https://example.com/v1#fragment'):
            with self.subTest(url=url), patch('providers.requests.post') as post:
                with self.assertRaisesRegex(PaperError, 'HTTPS'):
                    self.model(LLM_BASE_URL=url).complete('system', 'text')
                post.assert_not_called()

    def test_provider_credentials_and_quota_errors_are_specific(self):
        for status, message in ((401, 'credentials'), (403, 'credentials'), (429, 'quota')):
            with self.subTest(status=status), patch('providers.requests.post', return_value=Mock(status_code=status)):
                with self.assertRaisesRegex(PaperError, message):
                    self.model().complete('system', 'text')

    def test_timeout_does_not_return_fake_answer(self):
        with patch('providers.requests.post', side_effect=requests.Timeout()), self.assertRaisesRegex(PaperError, 'request failed'):
            self.model().complete('system', 'text')

    def test_malformed_and_empty_provider_payloads_are_rejected(self):
        payloads = [{}, {'choices': []}, {'choices': [{'message': {'content': ''}}]},
                    {'choices': [{'message': {'content': None}}]}]
        for payload in payloads:
            response = Mock(status_code=200)
            response.json.return_value = payload
            with self.subTest(payload=payload), patch('providers.requests.post', return_value=response):
                with self.assertRaisesRegex(PaperError, 'request failed'):
                    self.model().complete('system', 'text')

    def test_truncated_answer_is_rejected(self):
        response = Mock(status_code=200)
        response.json.return_value = {'choices': [{'message': {'content': 'Partial answer'}, 'finish_reason': 'length'}]}
        with patch('providers.requests.post', return_value=response), self.assertRaisesRegex(PaperError, 'output limit'):
            self.model().complete('system', 'text')

    def test_metadata_parses_fenced_json_and_rejects_invalid_shapes(self):
        llm = self.model()
        with patch.object(llm, 'complete', return_value='```json\n{"title":"A title","authors":[],"year":null,"abstract":""}\n```'):
            self.assertEqual(llm.metadata([{'page': 1, 'text': 'opening pages'}])['title'], 'A title')
        for answer in ('not json', '[]'):
            with self.subTest(answer=answer), patch.object(llm, 'complete', return_value=answer):
                with self.assertRaisesRegex(PaperError, 'metadata'):
                    llm.metadata([{'page': 1, 'text': 'opening pages'}])


class PDFAndContextTests(unittest.TestCase):
    def test_password_protected_pdf_is_actionable(self):
        with self.assertRaisesRegex(PaperError, 'password protected'):
            extract_pdf(pdf_bytes(password='locked-test-fixture'))

    def test_zero_and_over_limit_page_counts_are_rejected(self):
        for count in (0, 151):
            with self.subTest(pages=count), self.assertRaisesRegex(PaperError, '1 to 150'):
                extract_pdf(pdf_bytes(pages=count))

    def test_image_only_pdf_requests_ocr(self):
        with self.assertRaisesRegex(PaperError, 'OCR'):
            extract_pdf(pdf_bytes(lines=[]))

    def test_corrupt_pdf_has_readable_failure_message(self):
        with self.assertRaisesRegex(PaperError, 'could not be read'):
            extract_pdf(b'%PDF-not-a-readable-document')

    def test_oversized_pdf_is_rejected_before_parsing(self):
        with self.assertRaisesRegex(PaperError, '20 MB'):
            extract_pdf(b'%PDF-' + b' ' * MAX_PDF_BYTES)

    def test_metadata_fallback_uses_publication_year(self):
        text = ('A Long Research Paper Title\nAlice Example and Bob Example\nAbstract\n'
                'We evaluate a 2014 dataset.\nConference on Reliable Systems 2025\n'
                'arXiv:2501.01234v2\n1 Introduction\nFurther discussion.')
        metadata = extract_metadata([{'page': 1, 'text': text}], {'/Title': 'paper.tex'})
        self.assertEqual(metadata['title'], 'A Long Research Paper Title')
        self.assertEqual(metadata['authors'], ['Alice Example', 'Bob Example'])
        self.assertEqual(metadata['year'], 2025)
        self.assertEqual(metadata['arxiv_id'], '2501.01234')
        self.assertNotIn('Further discussion', metadata['abstract'])

    def test_short_paper_context_preserves_all_text_and_page_markers(self):
        pages = [{'page': 1, 'text': 'Opening evidence'}, {'page': 2, 'text': 'Final evidence'}]
        context, selected, coverage = select_context(pages)
        self.assertIn('[p. 1]\nOpening evidence', context)
        self.assertIn('[p. 2]\nFinal evidence', context)
        self.assertEqual(selected, pages)
        self.assertEqual(coverage, 'Full extracted text')

    def test_long_summary_samples_end_and_respects_budget(self):
        pages = [{'page': n, 'text': f'Page {n}. ' + 'ordinary material ' * 200} for n in range(1, 31)]
        context, selected, coverage = select_context(pages, budget=15000)
        self.assertLessEqual(len(context), 15000)
        self.assertIn(1, {p['page'] for p in selected})
        self.assertIn(30, {p['page'] for p in selected})
        self.assertIn('sampled', coverage)

    def test_question_retrieval_selects_late_relevant_evidence(self):
        pages = [{'page': n, 'text': 'ordinary material ' * 200} for n in range(1, 31)]
        pages[24]['text'] = 'ZEBRA benchmark evidence ' * 200
        context, selected, coverage = select_context(pages, 'Which ZEBRA benchmark?', budget=15000)
        self.assertIn(25, {p['page'] for p in selected})
        self.assertIn('ZEBRA', context)
        self.assertLessEqual(len(context), 15000)
        self.assertIn('keywords', coverage)

    def test_empty_context_is_rejected(self):
        with self.assertRaisesRegex(PaperError, 'no readable text'):
            select_context([{'page': 1, 'text': '  '}])

    def test_citation_ranges_and_invalid_ranges_are_bounded(self):
        self.assertEqual(cited_pages('Evidence [p. 2], [pp. 4-6, 8].'), {2, 4, 5, 6, 8})
        self.assertEqual(cited_pages('Invalid [pp. 9-2] and [pp. 1-9999].'), set())
        self.assertEqual(cited_pages('No citation.'), set())
