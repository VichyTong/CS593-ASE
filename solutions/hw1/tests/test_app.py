"""Focused HW1 checks. External providers are mocked except in manual live checks."""
import io
import json
import tempfile
import unittest
from unittest.mock import Mock, patch

from pypdf import PdfWriter
from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject
from app import create_app
from pdf_tools import select_context, cited_page_numbers
from providers import LLM, download_arxiv
from pdf_tools import PaperError


def paper_pdf():
    writer = PdfWriter()
    texts = [
        ['A Controlled Study of Search', 'Alice Example and Bob Example', '2025', 'Abstract',
         'We compare retrieval methods in a controlled study of research paper search.',
         'The approach uses lexical matching and persistent local storage for repeatability.',
         '1 Introduction', 'We investigate how retrieval quality changes with query specificity.'],
        ['2 Evaluation', 'The ORCHID dataset contains 120 examples.',
         'Our method obtains 87 percent accuracy compared with 73 percent for the baseline.',
         '3 Limitations', 'The experiment uses a small synthetic collection, not real users.']]
    for lines in texts:
        page = writer.add_blank_page(width=612, height=792)
        font = DictionaryObject({NameObject('/Type'): NameObject('/Font'),
            NameObject('/Subtype'): NameObject('/Type1'), NameObject('/BaseFont'): NameObject('/Helvetica')})
        page[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'): DictionaryObject({NameObject('/F1'): writer._add_object(font)})})
        stream = DecodedStreamObject()
        stream.set_data(('BT /F1 12 Tf 50 740 Td 18 TL ' + ' T* '.join(f'({line}) Tj' for line in lines) + ' ET').encode())
        page[NameObject('/Contents')] = writer._add_object(stream)
    writer.add_metadata({'/Title': 'A Controlled Study of Search', '/Author': 'Alice Example; Bob Example'})
    out = io.BytesIO(); writer.write(out); return out.getvalue()


class ApplicationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.config = {'TESTING': True, 'DATA_DIR': self.temp.name, 'LLM_API_KEY': '',
                       'APP_USERNAME': '', 'APP_PASSWORD': ''}
        self.app = create_app(self.config)
        self.client = self.app.test_client()

    def tearDown(self):
        self.temp.cleanup()

    def upload(self):
        return self.client.post('/api/upload', data={'file': (io.BytesIO(paper_pdf()), 'sample.pdf')})

    def save(self):
        return self.client.post('/api/papers', json={'source_id': '1706.03762', 'title': 'Attention Is All You Need',
            'authors': ['Ashish Vaswani'], 'year': 2017, 'abstract': 'A transformer paper.'})

    def test_search_mapping_and_saved_flag(self):
        p = self.save().json['paper']
        with patch('app.search_arxiv', return_value=[p]) as search:
            result = self.client.get('/api/search?q=attention')
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json['papers'][0]['saved_id'], p['id'])
        search.assert_called_once_with('attention')

    def test_persistence_and_dedup_after_restart(self):
        first = self.save().json['paper']['id']
        self.assertEqual(self.save().json['paper']['id'], first)
        restarted = create_app(self.config).test_client()
        self.assertEqual(len(restarted.get('/api/papers').json['papers']), 1)
        self.assertEqual(restarted.get(f'/api/papers/{first}').json['paper']['year'], 2017)

    def test_pdf_upload_metadata_and_text(self):
        response = self.upload()
        self.assertEqual(response.status_code, 201)
        paper = response.json['paper']
        self.assertEqual(paper['authors'], ['Alice Example', 'Bob Example'])
        self.assertEqual(paper['year'], 2025)
        self.assertIn('compare retrieval', paper['abstract'])
        self.assertEqual(paper['page_count'], 2)
        detail = self.client.get(f'/api/papers/{paper["id"]}').json['paper']
        self.assertIn('ORCHID', detail['pages'][1]['text'])
        self.assertEqual(self.upload().json['paper']['id'], paper['id'])

    def test_invalid_and_empty_pdf_rejected(self):
        response = self.client.post('/api/upload', data={'file': (io.BytesIO(b'not a pdf'), 'bad.pdf')})
        self.assertEqual(response.status_code, 400)
        writer = PdfWriter(); writer.add_blank_page(612, 792); stream = io.BytesIO(); writer.write(stream)
        result = self.client.post('/api/upload', data={'file': (io.BytesIO(stream.getvalue()), 'scan.pdf')})
        self.assertEqual(result.status_code, 400)
        self.assertIn('OCR', result.json['error'])

    def test_edit_and_validation(self):
        ident = self.upload().json['paper']['id']
        bad = self.client.patch(f'/api/papers/{ident}', json={'title': 'Fixed', 'year': 'wrong'})
        self.assertEqual(bad.status_code, 400)
        good = self.client.patch(f'/api/papers/{ident}', json={'title': 'Fixed', 'authors': ['A. Author'], 'year': 2024, 'abstract': 'Reviewed.'})
        self.assertEqual(good.json['paper']['title'], 'Fixed')

    def test_missing_key_and_missing_full_text(self):
        ident = self.save().json['paper']['id']
        self.assertEqual(self.client.post(f'/api/papers/{ident}/analyze', json={'kind': 'summary'}).status_code, 400)
        self.app.extensions['llm'].api_key = 'test-key'
        response = self.client.post(f'/api/papers/{ident}/analyze', json={'kind': 'summary'})
        self.assertIn('full paper', response.json['error'])

    def test_llm_uses_body_and_saves_summary_and_question(self):
        ident = self.upload().json['paper']['id']
        llm = self.app.extensions['llm']; llm.api_key = 'test-key'
        with patch.object(llm, 'complete', return_value='The ORCHID dataset has 120 examples [p. 2].') as complete:
            for kind in ['summary', 'question']:
                response = self.client.post(f'/api/papers/{ident}/analyze', json={'kind': kind, 'question': 'What dataset is used?'})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json['analysis']['sources'][0]['page'], 2)
                self.assertIn('ORCHID', complete.call_args.args[1])
                self.assertIn('[p. 2]', complete.call_args.args[1])
        restarted = create_app(self.config).test_client()
        self.assertEqual(len(restarted.get(f'/api/papers/{ident}').json['paper']['analyses']), 2)

    def test_invalid_model_citation_is_flagged(self):
        ident = self.upload().json['paper']['id']
        llm = self.app.extensions['llm']; llm.api_key = 'test-key'
        with patch.object(llm, 'complete', return_value='Unsupported result [p. 99].'):
            result = self.client.post(f'/api/papers/{ident}/analyze', json={'kind': 'summary'}).json['analysis']
        self.assertIn('Citation warning', result['answer'])
        self.assertEqual(result['sources'], [])

    def test_provider_failure_does_not_save_fake_analysis(self):
        ident = self.upload().json['paper']['id']
        llm = self.app.extensions['llm']; llm.api_key = 'test-key'
        with patch.object(llm, 'complete', side_effect=PaperError('Provider unavailable')):
            response = self.client.post(f'/api/papers/{ident}/analyze', json={'kind': 'summary'})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.client.get(f'/api/papers/{ident}').json['paper']['analyses'], [])

    def test_metadata_model_failure_falls_back(self):
        llm = self.app.extensions['llm']; llm.api_key = 'test-key'
        with patch.object(llm, 'metadata', side_effect=PaperError('bad model JSON')):
            response = self.upload()
        self.assertEqual(response.status_code, 201)
        self.assertIn('unavailable', response.json['notice'])

    def test_download_and_cascade_delete(self):
        ident = self.save().json['paper']['id']
        with patch('app.download_arxiv', return_value=paper_pdf()):
            self.assertTrue(self.client.post(f'/api/papers/{ident}/content').json['paper']['has_full_text'])
        with self.client.get(f'/api/papers/{ident}/pdf') as response:
            self.assertEqual(response.data, paper_pdf())
        self.assertEqual(self.client.delete(f'/api/papers/{ident}').status_code, 200)
        self.assertEqual(self.client.get(f'/api/papers/{ident}').status_code, 404)

    def test_deleting_one_record_preserves_shared_pdf(self):
        saved = self.save().json['paper']['id']
        with patch('app.download_arxiv', return_value=paper_pdf()):
            self.client.post(f'/api/papers/{saved}/content')
        uploaded = self.upload().json['paper']['id']
        self.client.delete(f'/api/papers/{saved}')
        with self.client.get(f'/api/papers/{uploaded}/pdf') as response:
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data, paper_pdf())

    def test_cross_origin_writes_and_bad_source_ids(self):
        self.assertEqual(self.client.post('/api/papers', json={}, headers={'Origin': 'https://untrusted.example'}).status_code, 403)
        self.assertEqual(self.client.post('/api/papers', json={'source_id': 'http://127.0.0.1/private'}).status_code, 400)
        with self.assertRaises(PaperError): download_arxiv('../../etc/passwd')

    def test_long_context_covers_ending_and_retrieves_evidence(self):
        pages = [{'page': n + 1, 'text': ('General background. ' * 300)} for n in range(30)]
        pages[-1]['text'] += ' UNIQUEORCHID dataset 120 examples.'
        context, _, coverage = select_context(pages)
        self.assertIn('[p. 30]', context)
        self.assertIn('not the entire paper', coverage)
        context, _, _ = select_context(pages, 'What is UNIQUEORCHID?')
        self.assertIn('UNIQUEORCHID', context)

    def test_combined_and_range_citations_from_live_model(self):
        self.assertEqual(cited_page_numbers('Evidence [p. 2, p. 6] and [p. 7–9] plus [pp. 10-11].'), {2,6,7,8,9,10,11})
        self.assertEqual(cited_page_numbers('[p. 1-999999999]'), set())

    def test_openai_compatible_request_contract(self):
        llm = LLM('https://api.example.com/v1', 'secret-test', 'example-model')
        response = Mock(status_code=200)
        response.json.return_value = {'choices': [{'message': {'content': 'Answer'}}]}
        with patch('providers.requests.post', return_value=response) as post:
            self.assertEqual(llm.complete('system', 'paper text'), 'Answer')
        self.assertEqual(post.call_args.args[0], 'https://api.example.com/v1/chat/completions')
        self.assertEqual(post.call_args.kwargs['json']['messages'][1]['content'], 'paper text')
        self.assertEqual(post.call_args.kwargs['headers']['Authorization'], 'Bearer secret-test')

    def test_cached_analysis_is_not_billed_again(self):
        ident = self.upload().json['paper']['id']
        llm = self.app.extensions['llm']; llm.api_key = 'test-key'
        with patch.object(llm, 'complete', return_value='The study uses ORCHID [p. 2].') as complete:
            first = self.client.post(f'/api/papers/{ident}/analyze', json={'kind': 'summary'})
            second = self.client.post(f'/api/papers/{ident}/analyze', json={'kind': 'summary'})
        self.assertEqual(complete.call_count, 1)
        self.assertTrue(second.json['cached'])
        self.assertEqual(first.json['analysis']['id'], second.json['analysis']['id'])

    def test_budget_rejects_before_network_call(self):
        llm = LLM('https://api.openai.com/v1', 'test', 'gpt-6-luna',
                  db_path=self.app.extensions['db_path'], budget_usd=0.000001)
        with patch('providers.requests.post') as post:
            with self.assertRaisesRegex(PaperError, 'budget'):
                llm.complete('system', 'paper')
        post.assert_not_called()

    def test_persistent_result_cache_and_explicit_prompt_cache(self):
        llm = LLM('https://api.openai.com/v1', 'test', 'gpt-6-luna', db_path=self.app.extensions['db_path'])
        response = Mock(status_code=200)
        response.json.return_value = {'choices': [{'message': {'content': 'Grounded answer'}}],
            'usage': {'prompt_tokens': 2000, 'completion_tokens': 20, 'prompt_tokens_details': {'cached_tokens': 1024}}}
        with patch('providers.requests.post', return_value=response) as post:
            llm.complete('system', 'shared paper', task='Summarize')
            restarted = LLM('https://api.openai.com/v1', 'test', 'gpt-6-luna', db_path=self.app.extensions['db_path'])
            self.assertEqual(restarted.complete('system', 'shared paper', task='Summarize'), 'Grounded answer')
        self.assertEqual(post.call_count, 1)
        body = post.call_args.kwargs['json']
        self.assertEqual(body['prompt_cache_options'], {'mode': 'explicit', 'ttl': '30m'})
        self.assertEqual(body['messages'][1]['content'][0]['prompt_cache_breakpoint'], {'mode': 'explicit'})
        self.assertEqual(body['messages'][2]['content'], 'Summarize')
        self.assertEqual(body['max_completion_tokens'], 1200)
        self.assertEqual(restarted.budget_status()['cached_tokens'], 1024)
        self.assertEqual(restarted.budget_status()['requests'], 1)


if __name__ == '__main__':
    unittest.main()
