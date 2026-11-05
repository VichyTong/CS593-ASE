"""New HW2 initial tests of the five documented Papertrail workflows."""
import io
import json
from unittest.mock import patch

import database
from pdf_tools import PaperError
from initial_support import (
    IsolatedCase, PAPER, llm_response, pdf_bytes, pdf_response, search_response,
)
from app import create_app


class WorkflowTests(IsolatedCase):
    def test_home_and_status_expose_configuration_without_secrets(self):
        self.enable_llm()
        home = self.client.get('/')
        self.assertEqual(home.status_code, 200)
        self.assertEqual(home.mimetype, 'text/html')
        self.assertIn('Papertrail', home.get_data(as_text=True))
        status = self.client.get('/api/status')
        self.assertEqual(status.status_code, 200)
        self.assertEqual(status.json, {
            'llm_configured': True, 'model': 'unit-test-model',
            'provider_host': 'llm.example.invalid', 'search_provider': 'arXiv',
        })
        self.assertNotIn('dummy-test-key', status.get_data(as_text=True))
        self.assertEqual(status.headers['Cache-Control'], 'no-store')
        self.assertEqual(home.headers['X-Content-Type-Options'], 'nosniff')

    def test_search_parses_arxiv_and_links_saved_results_with_pagination(self):
        saved = self.save()
        with patch('providers.requests.get', return_value=search_response()) as get:
            response = self.client.get('/api/search', query_string={
                'q': 'Testing the Research Libraries', 'page': 2, 'sort': 'submittedDate',
            })
        self.assertEqual(response.status_code, 200, response.json)
        self.assertEqual(response.json['total'], 21)
        self.assertEqual(response.json['page'], 2)
        self.assertEqual(response.json['page_size'], 10)
        self.assertEqual(len(response.json['papers']), 1)
        result = response.json['papers'][0]
        for key, expected in PAPER.items():
            self.assertEqual(result[key], expected, key)
        self.assertEqual(result['saved_id'], saved['id'])
        self.assertEqual(result['url'], 'https://arxiv.org/abs/2501.01234')
        get.assert_called_once()
        self.assertEqual(get.call_args.args[0], 'https://export.arxiv.org/api/query')
        self.assertEqual(get.call_args.kwargs['params'], {
            'start': 10, 'max_results': 10,
            'search_query': 'all:Testing AND all:Research AND all:Libraries',
            'sortBy': 'submittedDate', 'sortOrder': 'descending',
        })

    def test_library_persists_and_deduplicates_versions_across_restart(self):
        self.assertEqual(self.client.get('/api/papers').json['papers'], [])
        first = self.save(source_id='2501.01234v2')
        duplicate = self.client.post('/api/papers', json=dict(PAPER, source_id='2501.01234v3'))
        self.assertEqual(duplicate.status_code, 200)
        self.assertFalse(duplicate.json['created'])
        self.assertEqual(duplicate.json['paper']['id'], first['id'])
        second = self.save(source_id='2501.54321', title='Another synthetic paper')
        restarted = create_app(self.config).test_client()
        papers = restarted.get('/api/papers').json['papers']
        self.assertEqual([p['id'] for p in papers], [second['id'], first['id']])
        for key, expected in PAPER.items():
            self.assertEqual(papers[1][key], expected, key)
        self.assertFalse(papers[1]['has_pdf'])
        self.assertFalse(papers[1]['has_full_text'])

    def test_metadata_edit_normalizes_and_persists_all_fields(self):
        paper = self.save()
        response = self.client.patch(f"/api/papers/{paper['id']}", json={
            'title': '  Corrected title  ', 'authors': [' Ava Reviewer ', '  '],
            'year': '', 'abstract': '  Reviewed abstract.  ',
        })
        self.assertEqual(response.status_code, 200)
        restarted = create_app(self.config).test_client()
        edited = restarted.get(f"/api/papers/{paper['id']}").json['paper']
        for key, expected in {
            'title': 'Corrected title', 'authors': ['Ava Reviewer'],
            'year': None, 'abstract': 'Reviewed abstract.',
            'metadata_method': 'Reviewed by user', 'source_id': PAPER['source_id'],
        }.items():
            self.assertEqual(edited[key], expected, key)

    def test_real_pdf_upload_extracts_text_metadata_and_downloadable_bytes(self):
        raw = pdf_bytes()
        paper = self.upload(raw)
        self.assertEqual(paper['title'], PAPER['title'])
        self.assertEqual(paper['authors'], PAPER['authors'])
        self.assertEqual(paper['year'], 2025)
        self.assertIn('72 synthetic papers', paper['abstract'])
        self.assertNotIn('1 Introduction', paper['abstract'])
        self.assertTrue(paper['has_pdf'])
        self.assertTrue(paper['has_full_text'])
        self.assertEqual(paper['page_count'], 2)
        detail = self.detail(paper['id'])
        self.assertEqual([p['page'] for p in detail['pages']], [1, 2])
        self.assertIn('HAWK benchmark', detail['pages'][1]['text'])
        self.assertEqual(detail['analyses'], [])
        self.assertEqual(len(self.pdf_files()), 1)
        response = self.client.get(f"/api/papers/{paper['id']}/pdf")
        self.addCleanup(response.close)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, 'application/pdf')
        self.assertIn('attachment', response.headers['Content-Disposition'])
        self.assertEqual(response.data, raw)

    def test_duplicate_upload_reuses_record_and_stored_file(self):
        raw = pdf_bytes()
        first = self.upload(raw)
        with patch('app.extract_pdf') as extract:
            duplicate = self.client.post('/api/upload', data={
                'file': (io.BytesIO(raw), 'renamed.PDF'),
            })
        self.assertEqual(duplicate.status_code, 200)
        self.assertFalse(duplicate.json['created'])
        self.assertEqual(duplicate.json['paper']['id'], first['id'])
        self.assertIn('already', duplicate.json['notice'])
        extract.assert_not_called()
        self.assertEqual(len(self.pdf_files()), 1)
        self.assertEqual(len(self.client.get('/api/papers').json['papers']), 1)

    def test_arxiv_full_text_loads_once_and_survives_restart(self):
        paper = self.save()
        raw = pdf_bytes()
        with patch('providers.requests.get', return_value=pdf_response(raw)) as get:
            first = self.client.post(f"/api/papers/{paper['id']}/content")
            again = self.client.post(f"/api/papers/{paper['id']}/content")
        self.assertEqual(first.status_code, 200, first.json)
        self.assertEqual(again.status_code, 200, again.json)
        self.assertEqual(first.json['paper']['pages'], again.json['paper']['pages'])
        self.assertIn('HAWK benchmark', first.json['paper']['pages'][1]['text'])
        get.assert_called_once_with('https://arxiv.org/pdf/2501.01234',
                                    timeout=(10, 60), stream=True, allow_redirects=False)
        restarted = create_app(self.config).test_client()
        detail = restarted.get(f"/api/papers/{paper['id']}").json['paper']
        self.assertTrue(detail['has_full_text'])
        self.assertEqual(detail['pages'], first.json['paper']['pages'])
        self.assertEqual(self.pdf_files()[0].read_bytes(), raw)

    def test_summary_downloads_pdf_sends_grounded_prompt_and_persists_evidence(self):
        paper = self.save()
        self.enable_llm()
        answer = 'Controlled study of 72 synthetic papers. [p. 1] No field data. [p. 2]'
        with patch('providers.requests.get', return_value=pdf_response(pdf_bytes())) as get, \
                patch('providers.requests.post', return_value=llm_response(answer)) as post:
            response = self.client.post(f"/api/papers/{paper['id']}/analyze", json={'kind': 'summary'})
        self.assertEqual(response.status_code, 200, response.json)
        self.assertFalse(response.json['cached'])
        analysis = response.json['analysis']
        self.assertEqual(analysis['answer'], answer)
        self.assertEqual(analysis['kind'], 'summary')
        self.assertEqual(analysis['question'], '')
        self.assertEqual(analysis['model'], 'unit-test-model')
        self.assertEqual(analysis['coverage'], 'Full extracted text')
        self.assertEqual(analysis['warning'], '')
        self.assertEqual([p['page'] for p in analysis['sources']], [1, 2])
        self.assertNotIn('cache_key', analysis)
        get.assert_called_once()
        post.assert_called_once()
        self.assertEqual(post.call_args.args[0], 'https://llm.example.invalid/v1/chat/completions')
        body = post.call_args.kwargs['json']
        self.assertEqual(body['model'], 'unit-test-model')
        self.assertEqual(body['max_completion_tokens'], 1800)
        self.assertIn('ONLY from the supplied paper text', body['messages'][0]['content'])
        self.assertIn('[p. 1]', body['messages'][1]['content'])
        self.assertIn('[p. 2]', body['messages'][1]['content'])
        self.assertIn('72 synthetic papers', body['messages'][1]['content'])
        self.assertIn('no field data', body['messages'][1]['content'])
        self.assertIn('Limitations', body['messages'][2]['content'])
        restarted = create_app(self.config).test_client()
        history = restarted.get(f"/api/papers/{paper['id']}").json['paper']['analyses']
        self.assertEqual(history, [analysis])

    def test_question_is_trimmed_grounded_and_cached_across_restart(self):
        paper = self.upload()
        self.enable_llm()
        endpoint = f"/api/papers/{paper['id']}/analyze"
        answer = 'The HAWK benchmark contains 72 synthetic papers. [p. 2]'
        with patch('providers.requests.post', return_value=llm_response(answer)) as post:
            response = self.client.post(endpoint, json={
                'kind': 'question', 'question': '  Which benchmark is used?  ',
            })
            self.assertEqual(response.status_code, 200, response.json)
            restarted = create_app(self.config).test_client()
            cached = restarted.post(endpoint, json={
                'kind': 'question', 'question': 'Which benchmark is used?',
            })
        self.assertEqual(cached.status_code, 200)
        self.assertFalse(response.json['cached'])
        self.assertTrue(cached.json['cached'])
        self.assertEqual(cached.json['analysis'], response.json['analysis'])
        post.assert_called_once()
        messages = post.call_args.kwargs['json']['messages']
        self.assertEqual(messages[-1]['content'], 'Which benchmark is used?')
        self.assertIn('HAWK benchmark', messages[1]['content'])
        analysis = response.json['analysis']
        self.assertEqual(analysis['question'], 'Which benchmark is used?')
        self.assertEqual(analysis['answer'], answer)
        self.assertEqual([s['page'] for s in analysis['sources']], [2])
        self.assertEqual(self.detail(paper['id'])['analyses'], [analysis])

    def test_deletion_cascades_analyses_and_preserves_a_shared_pdf(self):
        raw = pdf_bytes()
        uploaded = self.upload(raw)
        saved = self.save()
        with patch('app.download_paper', return_value=raw):
            self.assertEqual(self.client.post(f"/api/papers/{saved['id']}/content").status_code, 200)
        self.enable_llm()
        with patch('providers.requests.post', return_value=llm_response()):
            response = self.client.post(f"/api/papers/{uploaded['id']}/analyze", json={'kind': 'summary'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(self.pdf_files()), 1)
        deleted = self.client.delete(f"/api/papers/{uploaded['id']}")
        self.assertEqual(deleted.status_code, 200)
        self.assertTrue(deleted.json['ok'])
        self.assertEqual(self.client.get(f"/api/papers/{uploaded['id']}").status_code, 404)
        with database.connect(self.app.extensions['db_path']) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM analyses').fetchone()[0], 0)
        download = self.client.get(f"/api/papers/{saved['id']}/pdf")
        self.addCleanup(download.close)
        self.assertEqual(download.status_code, 200)
        self.assertEqual(download.data, raw)
        download.close()
        self.assertEqual(self.client.delete(f"/api/papers/{saved['id']}").status_code, 200)
        self.assertEqual(self.pdf_files(), [])
        self.assertEqual(self.client.get('/api/papers').json['papers'], [])

    def test_upload_prefers_matching_arxiv_metadata_over_ai(self):
        llm = self.enable_llm()
        matched = dict(PAPER, title='Authoritative arXiv title', year=2024)
        with patch('app.search_papers', return_value={'papers': [matched]}) as search, \
                patch.object(llm, 'metadata') as metadata:
            paper = self.upload(pdf_bytes(arxiv_id='2501.01234v2'))
        search.assert_called_once_with('2501.01234')
        metadata.assert_not_called()
        self.assertEqual(paper['title'], matched['title'])
        self.assertEqual(paper['year'], 2024)
        self.assertIn('arXiv metadata matched', paper['metadata_method'])

    def test_upload_succeeds_with_pdf_metadata_during_arxiv_outage(self):
        with patch('app.search_papers', side_effect=PaperError('arXiv unavailable')):
            paper = self.upload(pdf_bytes(arxiv_id='2501.01234'))
        self.assertEqual(paper['title'], PAPER['title'])
        self.assertTrue(paper['has_full_text'])
        self.assertIn('PDF text', paper['metadata_method'])

    def test_configured_upload_uses_ai_metadata_json(self):
        self.enable_llm()
        metadata = dict(title='AI extracted title', authors=['Cora Curator'],
                        year=2024, abstract='An extracted abstract.')
        with patch('providers.requests.post', return_value=llm_response(json.dumps(metadata))) as post:
            paper = self.upload()
        for key, expected in metadata.items():
            self.assertEqual(paper[key], expected, key)
        self.assertIn('AI extraction', paper['metadata_method'])
        self.assertIn('HAWK benchmark', post.call_args.kwargs['json']['messages'][1]['content'])

    def test_analysis_warns_about_citations_outside_supplied_pages(self):
        paper = self.upload()
        self.enable_llm()
        answer = 'An unsupported claim. [p. 99]'
        with patch('providers.requests.post', return_value=llm_response(answer)):
            response = self.client.post(f"/api/papers/{paper['id']}/analyze", json={'kind': 'summary'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['analysis']['answer'], answer)
        self.assertIn('not in the supplied context', response.json['analysis']['warning'])
        self.assertEqual(response.json['analysis']['sources'], [])

    def test_analysis_without_citations_warns_and_retains_source_excerpts(self):
        paper = self.upload()
        self.enable_llm()
        with patch('providers.requests.post', return_value=llm_response('No citations returned.')):
            response = self.client.post(f"/api/papers/{paper['id']}/analyze", json={'kind': 'summary'})
        self.assertEqual(response.status_code, 200)
        analysis = response.json['analysis']
        self.assertIn('No page references', analysis['warning'])
        self.assertEqual([s['page'] for s in analysis['sources']], [1, 2])
