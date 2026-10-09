"""Focused integration tests: persistence, PDFs, grounding, and failure paths.

Network calls are mocked. These tests do not claim a live provider connection.
"""
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject
from app import create_app
import database
from pdf_tools import PaperError, select_context, extract_metadata
from providers import LLM
import providers


def pdf_bytes():
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    font = DictionaryObject({NameObject('/Type'): NameObject('/Font'), NameObject('/Subtype'): NameObject('/Type1'), NameObject('/BaseFont'): NameObject('/Helvetica')})
    page[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'): DictionaryObject({NameObject('/F1'): writer._add_object(font)})})
    stream = DecodedStreamObject()
    lines = ['A Study of Reliable Testing', 'Alice Example and Bob Example', '2025', 'Abstract',
             'We study test generation using controlled experiments and measure coverage.',
             'Our dataset contains 80 small programs. Results show improved bug detection.',
             '1 Introduction', 'The method mutates program inputs and checks properties.',
             'The main limitation is the small evaluation dataset and lack of field data.']
    content = 'BT /F1 12 Tf 50 740 Td 16 TL ' + ' '.join(f'({line}) Tj T*' for line in lines) + ' ET'
    stream.set_data(content.encode('ascii'))
    page[NameObject('/Contents')] = writer._add_object(stream)
    writer.add_metadata({'/Title': lines[0], '/Author': 'Alice Example; Bob Example'})
    out = io.BytesIO(); writer.write(out)
    return out.getvalue()


PAPER = {'source_id': '1706.03762', 'title': 'Attention Is All You Need', 'authors': ['Ashish Vaswani'],
         'year': 2017, 'abstract': 'The Transformer architecture.', 'category': 'cs.CL'}


class AppTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.config = {'TESTING': True, 'DATA_DIR': self.directory.name, 'LLM_API_KEY': '',
                       'APP_USERNAME': '', 'APP_PASSWORD': ''}
        self.app = create_app(self.config)
        self.client = self.app.test_client()

    def tearDown(self):
        self.directory.cleanup()

    def upload(self):
        response = self.client.post('/api/upload', data={'file': (io.BytesIO(pdf_bytes()), 'test.pdf')})
        self.assertEqual(response.status_code, 201, response.json)
        return response.json['paper']

    def test_search_and_save_persist_across_restart(self):
        with patch('app.search_papers', return_value={'papers': [PAPER], 'total': 1, 'page': 1, 'page_size': 10}) as search:
            result = self.client.get('/api/search?q=attention').json
            search.assert_called_once_with('attention', 1, 'relevance')
            self.assertEqual(result['papers'][0]['title'], PAPER['title'])
        first = self.client.post('/api/papers', json=PAPER)
        duplicate = self.client.post('/api/papers', json=PAPER)
        self.assertEqual(first.status_code, 201)
        self.assertEqual(duplicate.status_code, 200)
        restarted = create_app(self.config).test_client()
        saved = restarted.get('/api/papers').json['papers']
        self.assertEqual(len(saved), 1)
        self.assertEqual(saved[0]['id'], first.json['paper']['id'])

    def test_pdf_upload_metadata_text_and_deduplication(self):
        paper = self.upload()
        self.assertEqual(paper['title'], 'A Study of Reliable Testing')
        self.assertEqual(paper['authors'], ['Alice Example', 'Bob Example'])
        self.assertEqual(paper['year'], 2025)
        self.assertIn('80 small programs', paper['abstract'])
        self.assertNotIn('The method mutates', paper['abstract'])
        detail = self.client.get(f"/api/papers/{paper['id']}").json['paper']
        self.assertIn('lack of field data', detail['pages'][0]['text'])
        duplicate = self.client.post('/api/upload', data={'file': (io.BytesIO(pdf_bytes()), 'copy.pdf')})
        self.assertFalse(duplicate.json['created'])
        self.assertEqual(duplicate.json['paper']['id'], paper['id'])

    def test_invalid_upload_and_unknown_paper_are_actionable(self):
        bad = self.client.post('/api/upload', data={'file': (io.BytesIO(b'not a pdf'), 'test.pdf')})
        self.assertEqual(bad.status_code, 400)
        self.assertIn('valid PDF', bad.json['error'])
        writer = PdfWriter(); writer.add_blank_page(100, 100); buf = io.BytesIO(); writer.write(buf)
        scan = self.client.post('/api/upload', data={'file': (io.BytesIO(buf.getvalue()), 'scan.pdf')})
        self.assertIn('OCR', scan.json['error'])
        self.assertEqual(self.client.get('/api/papers/999').status_code, 404)

    def test_edit_and_input_validation(self):
        paper = self.upload(); endpoint = f"/api/papers/{paper['id']}"
        edit = {'title': 'Corrected title', 'authors': ['Reviewed Author'], 'year': None, 'abstract': 'Reviewed abstract'}
        self.assertEqual(self.client.patch(endpoint, json=edit).status_code, 200)
        self.assertEqual(self.client.get(endpoint).json['paper']['title'], edit['title'])
        self.assertEqual(self.client.patch(endpoint, json=dict(edit, year=True)).status_code, 400)
        self.assertEqual(self.client.patch(endpoint, json=dict(edit, authors='wrong')).status_code, 400)
        self.assertEqual(self.client.get('/api/search?q=test&page=-1').status_code, 400)
        self.assertEqual(self.client.post('/api/papers', json=dict(PAPER, source_id='../private')).status_code, 400)

    def test_missing_model_never_returns_canned_summary(self):
        paper = self.client.post('/api/papers', json=PAPER).json['paper']
        with patch('app.download_paper') as download:
            response = self.client.post(f"/api/papers/{paper['id']}/analyze", json={'kind': 'summary'})
            download.assert_not_called()
        self.assertEqual(response.status_code, 400)
        self.assertIn('Connect an AI model', response.json['error'])

    def test_analysis_uses_pdf_text_and_persists_and_caches(self):
        paper = self.upload()
        llm = self.app.extensions['llm']; llm.api_key = 'test-only-key'
        with patch.object(llm, 'complete', return_value='The dataset has 80 programs. [p. 1]') as complete:
            request = {'kind': 'question', 'question': 'What datasets are used?'}
            first = self.client.post(f"/api/papers/{paper['id']}/analyze", json=request)
            self.assertEqual(first.status_code, 200, first.json)
            self.assertIn('80 small programs', complete.call_args.args[1])
            self.assertIn('lack of field data', complete.call_args.args[1])
            self.assertEqual(complete.call_args.args[2], request['question'])
            self.assertEqual(first.json['analysis']['sources'][0]['page'], 1)
            second = self.client.post(f"/api/papers/{paper['id']}/analyze", json=request)
            self.assertTrue(second.json['cached'])
            self.assertEqual(complete.call_count, 1)
        restarted = create_app(self.config).test_client()
        history = restarted.get(f"/api/papers/{paper['id']}").json['paper']['analyses']
        self.assertEqual(len(history), 1)
        self.assertIn('80 programs', history[0]['answer'])

    def test_summary_downloads_content_and_checks_citations(self):
        paper = self.client.post('/api/papers', json=PAPER).json['paper']
        llm = self.app.extensions['llm']; llm.api_key = 'test-only-key'
        with patch('app.download_paper', return_value=pdf_bytes()), patch.object(llm, 'complete', return_value='Unverified claim. [p. 99]') as complete:
            response = self.client.post(f"/api/papers/{paper['id']}/analyze", json={'kind': 'summary'})
            self.assertEqual(response.status_code, 200, response.json)
            self.assertIn('80 small programs', complete.call_args.args[1])
            self.assertIn('not in the supplied context', response.json['analysis']['warning'])

    def test_delete_preserves_shared_pdf_and_cascades_notes(self):
        uploaded = self.upload()
        saved = self.client.post('/api/papers', json=PAPER).json['paper']
        with patch('app.download_paper', return_value=pdf_bytes()):
            self.client.post(f"/api/papers/{saved['id']}/content")
        llm = self.app.extensions['llm']; llm.api_key = 'test-only-key'
        with patch.object(llm, 'complete', return_value='Summary. [p. 1]'):
            self.client.post(f"/api/papers/{uploaded['id']}/analyze", json={'kind': 'summary'})
        self.client.delete(f"/api/papers/{uploaded['id']}")
        response = self.client.get(f"/api/papers/{saved['id']}/pdf")
        self.assertEqual(response.status_code, 200); response.close()
        with database.connect(self.app.extensions['db_path']) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM analyses').fetchone()[0], 0)
        self.client.delete(f"/api/papers/{saved['id']}")
        self.assertEqual(list((Path(self.directory.name) / 'uploads').glob('*.pdf')), [])

    def test_provider_failure_and_cross_origin_writes(self):
        with patch('app.search_papers', side_effect=PaperError('arXiv unavailable')):
            response = self.client.get('/api/search?q=software')
            self.assertEqual(response.status_code, 400)
            self.assertIn('unavailable', response.json['error'])
        self.assertEqual(self.client.post('/api/papers', json=PAPER, headers={'Origin': 'https://unrelated.example'}).status_code, 403)
        status = self.client.get('/api/status')
        self.assertNotIn('LLM_API_KEY', status.get_data(as_text=True))

    def test_long_paper_context_includes_end_and_retrieves_evidence(self):
        pages = [{'page': n, 'text': f'Page {n}. ' + 'ordinary research material ' * 180} for n in range(1, 31)]
        pages[24]['text'] = 'ZEBRA benchmark evidence ' * 180
        context, selected, coverage = select_context(pages, budget=15000)
        self.assertLessEqual(len(context), 15000)
        self.assertIn(30, {p['page'] for p in selected})
        self.assertIn('Excerpts', coverage)
        context, selected, _ = select_context(pages, 'What is the ZEBRA benchmark?', budget=15000)
        self.assertIn(25, {p['page'] for p in selected})
        self.assertLessEqual(len(context), 15000)

    def test_llm_http_contract_and_provider_errors(self):
        llm = LLM(dict(self.app.config, LLM_API_KEY='test-only-key', LLM_MODEL='gpt-6-luna', LLM_REASONING_EFFORT=''))
        mock = Mock(status_code=200)
        mock.json.return_value = {'choices': [{'message': {'content': 'An answer.'}, 'finish_reason': 'stop'}]}
        with patch('providers.requests.post', return_value=mock) as post:
            self.assertEqual(llm.complete('system', 'actual paper text', 'question'), 'An answer.')
            body = post.call_args.kwargs['json']
            self.assertEqual(body['messages'][1]['content'], 'actual paper text')
            self.assertEqual(body['messages'][2]['content'], 'question')
            self.assertEqual(body['max_completion_tokens'], 1800)
            self.assertEqual(body['model'], 'gpt-6-luna')
            self.assertEqual(body['reasoning_effort'], 'none')
        mock.status_code = 401
        with patch('providers.requests.post', return_value=mock), self.assertRaisesRegex(PaperError, 'credentials'):
            llm.complete('system', 'text')

    def test_natural_title_search_does_not_require_stop_words(self):
        response = Mock()
        response.content = b'<feed xmlns="http://www.w3.org/2005/Atom"></feed>'
        with patch('providers.requests.get', return_value=response) as get, patch('providers._cache', {}), patch('providers._last_search', 0):
            providers.search_papers('Attention Is All You Need')
            self.assertEqual(get.call_args.kwargs['params']['search_query'], 'all:Attention AND all:Need')

    def test_pdf_metadata_uses_publication_year_not_dataset_year(self):
        text = ('Attention Is All You Need\nAshish Vaswani\nAbstract\n'
                'The model evaluates on WMT 2014 tasks.\n∗Equal contribution.\n'
                '31st Conference on Neural Information Processing Systems (NIPS 2017)\n'
                'arXiv:1706.03762v7 [cs.CL] 2 Aug 2023\n1 Introduction\nBody text.')
        metadata = extract_metadata([{'page': 1, 'text': text}], {})
        self.assertEqual(metadata['year'], 2017)
        self.assertEqual(metadata['arxiv_id'], '1706.03762')
        self.assertNotIn('Equal contribution', metadata['abstract'])

    def test_upload_enriches_metadata_using_identifier_from_pdf(self):
        with patch('app.extract_pdf', return_value=([{'page': 1, 'text': 'Actual extracted paper text.'}],
                dict(PAPER, title='Wrong header', year=2014, arxiv_id='1706.03762', metadata_method='heuristic'))), \
                patch('app.search_papers', return_value={'papers': [PAPER]}):
            paper = self.upload()
        self.assertEqual(paper['title'], PAPER['title'])
        self.assertEqual(paper['year'], 2017)
        self.assertIn('identifier', paper['metadata_method'])


if __name__ == '__main__':
    unittest.main()
