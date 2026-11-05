"""New HW2 initial tests of storage, context, and external-client contracts."""
import sqlite3
from unittest.mock import patch

import database
import providers
from pdf_tools import PaperError, cited_pages, select_context
from initial_support import IsolatedCase, llm_response, pdf_response, search_response


class ComponentTests(IsolatedCase):
    def test_database_rolls_back_the_entire_failed_transaction(self):
        path = self.app.extensions['db_path']
        with self.assertRaises(sqlite3.IntegrityError):
            with database.connect(path) as db:
                for title in ('First insert', 'Duplicate insert'):
                    db.execute('INSERT INTO papers (source_id,title,source) VALUES (?,?,?)',
                               ('2501.00001', title, 'arxiv'))
        with database.connect(path) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM papers').fetchone()[0], 0)

    def test_short_context_retains_all_text_and_original_page_numbers(self):
        pages = [{'page': 2, 'text': 'Opening research evidence.'},
                 {'page': 5, 'text': 'Closing research evidence.'}]
        context, selected, coverage = select_context(pages)
        self.assertEqual(context, '[p. 2]\nOpening research evidence.\n\n[p. 5]\nClosing research evidence.')
        self.assertEqual(selected, pages)
        self.assertEqual(coverage, 'Full extracted text')

    def test_long_context_is_bounded_and_samples_or_ranks_relevant_pages(self):
        pages = [{'page': n, 'text': 'ordinary research material ' * 180} for n in range(1, 13)]
        pages[6]['text'] = 'HAWK benchmark evidence ' * 180
        context, selected, coverage = select_context(pages, budget=6000)
        self.assertLessEqual(len(context), 6000)
        self.assertTrue(selected)
        self.assertIn(12, {p['page'] for p in selected})
        self.assertIn('sampled', coverage)
        context, selected, coverage = select_context(pages, 'Which HAWK benchmark?', budget=6000)
        self.assertLessEqual(len(context), 6000)
        self.assertIn(7, {p['page'] for p in selected})
        self.assertIn('question keywords', coverage)

    def test_empty_context_is_rejected_and_citation_ranges_are_parsed(self):
        with self.assertRaisesRegex(PaperError, 'no readable text'):
            select_context([{'page': 1, 'text': ' \n '}])
        self.assertEqual(cited_pages('Evidence [pp. 1-3, 5], repeated [p. 2].'), {1, 2, 3, 5})
        self.assertEqual(cited_pages('No citations here.'), set())

    def test_arxiv_exact_id_search_and_repeated_query_cache(self):
        with patch('providers.requests.get', return_value=search_response()) as get:
            first = providers.search_papers('https://arxiv.org/abs/2501.01234v2')
            second = providers.search_papers('https://arxiv.org/abs/2501.01234v2')
        self.assertEqual(first, second)
        self.assertEqual(first['papers'][0]['source_id'], '2501.01234')
        self.assertEqual(get.call_args.kwargs['params'], {
            'id_list': '2501.01234v2', 'start': 0, 'max_results': 10,
        })
        get.assert_called_once()

    def test_invalid_id_and_untrusted_pdf_redirect_are_rejected(self):
        with patch('providers.requests.get') as get:
            with self.assertRaisesRegex(PaperError, 'Invalid arXiv'):
                providers.download_paper('../private')
            get.assert_not_called()
        response = pdf_response(b'')
        response.is_redirect = True
        response.headers = {'Location': 'https://other.example.invalid/paper.pdf'}
        with patch('providers.requests.get', return_value=response) as get:
            with self.assertRaisesRegex(PaperError, 'Unexpected PDF location'):
                providers.download_paper('2501.01234')
        get.assert_called_once_with('https://arxiv.org/pdf/2501.01234',
                                    timeout=(10, 60), stream=True, allow_redirects=False)

    def test_llm_rejects_insecure_remote_endpoint_before_sending(self):
        llm = self.enable_llm()
        llm.base_url = 'http://llm.example.invalid/v1'
        with patch('providers.requests.post') as post:
            with self.assertRaisesRegex(PaperError, 'HTTPS model endpoint'):
                llm.complete('system', 'synthetic paper', 'question')
            post.assert_not_called()

    def test_llm_rejects_empty_malformed_and_truncated_responses(self):
        llm = self.enable_llm()
        malformed = llm_response()
        malformed.json.return_value = {'choices': []}
        for response, message in [
            (llm_response('  '), 'AI request failed'),
            (malformed, 'AI request failed'),
            (llm_response('Partial answer', finish='length'), 'output limit'),
            (llm_response(status=401), 'credentials'),
        ]:
            with self.subTest(message=message, payload=response.json.return_value):
                with patch('providers.requests.post', return_value=response):
                    with self.assertRaisesRegex(PaperError, message):
                        llm.complete('system', 'synthetic paper', 'question')
