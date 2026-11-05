"""Initial agent-generated suite, retained unchanged for comparison."""
import io
from unittest.mock import patch

from app import create_app
from support import IsolatedApp, PAPER


class InitialTests(IsolatedApp):
    def test_homepage_serves_application(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('Papertrail', response.get_data(as_text=True))
        self.assertIn('text/html', response.content_type)

    def test_search_preserves_bibliographic_fields(self):
        result = {'papers': [PAPER], 'total': 1, 'page': 1, 'page_size': 10}
        with patch('app.search_papers', return_value=result) as search:
            response = self.client.get('/api/search?q=reliable+research')
        self.assertEqual(response.status_code, 200)
        search.assert_called_once_with('reliable research', 1, 'relevance')
        for field in ('title', 'authors', 'year', 'abstract'):
            self.assertEqual(response.json['papers'][0][field], PAPER[field])
        self.assertIsNone(response.json['papers'][0]['saved_id'])

    def test_saved_metadata_survives_restart(self):
        paper = self.save_paper()
        restarted = create_app(self.config).test_client()
        papers = restarted.get('/api/papers').json['papers']
        self.assertEqual(len(papers), 1)
        self.assertEqual(papers[0]['id'], paper['id'])
        self.assertEqual(papers[0]['authors'], PAPER['authors'])
        self.assertEqual(papers[0]['year'], PAPER['year'])

    def test_saving_same_paper_is_idempotent(self):
        original = self.save_paper()
        response = self.client.post('/api/papers', json=PAPER)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json['created'])
        self.assertEqual(response.json['paper']['id'], original['id'])
        self.assertEqual(len(self.client.get('/api/papers').json['papers']), 1)

    def test_real_pdf_upload_extracts_metadata_and_text(self):
        paper = self.upload_paper()
        self.assertEqual(paper['title'], PAPER['title'])
        self.assertEqual(paper['authors'], PAPER['authors'])
        self.assertEqual(paper['year'], 2025)
        self.assertTrue(paper['has_pdf'])
        detail = self.client.get(f"/api/papers/{paper['id']}").json['paper']
        self.assertIn('ZEBRA benchmark', detail['pages'][0]['text'])
        self.assertIn('80 small programs', paper['abstract'])

    def test_edit_round_trips_all_metadata(self):
        paper = self.save_paper()
        edited = {'title': 'Reviewed title', 'authors': ['Carol Reviewer'],
                  'year': None, 'abstract': 'Reviewed abstract.'}
        response = self.client.patch(f"/api/papers/{paper['id']}", json=edited)
        self.assertEqual(response.status_code, 200)
        detail = self.client.get(f"/api/papers/{paper['id']}").json['paper']
        for key, value in edited.items():
            self.assertEqual(detail[key], value)

    def test_delete_removes_library_record(self):
        paper = self.save_paper()
        response = self.client.delete(f"/api/papers/{paper['id']}")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json['ok'])
        self.assertEqual(self.client.get('/api/papers').json['papers'], [])
        self.assertEqual(self.client.get(f"/api/papers/{paper['id']}").status_code, 404)

    def test_summary_uses_pdf_content_and_is_saved(self):
        paper = self.upload_paper()
        llm = self.enable_model()
        with patch.object(llm, 'complete', return_value='A study of 80 programs. [p. 1]') as complete:
            response = self.client.post(f"/api/papers/{paper['id']}/analyze", json={'kind': 'summary'})
        self.assertEqual(response.status_code, 200)
        self.assertIn('ZEBRA benchmark', complete.call_args.args[1])
        self.assertEqual(response.json['analysis']['answer'], 'A study of 80 programs. [p. 1]')
        self.assertEqual(response.json['analysis']['kind'], 'summary')
        self.assertEqual(len(self.history(paper['id'])), 1)

    def test_question_passes_exact_task_and_saves_answer(self):
        paper = self.upload_paper()
        llm = self.enable_model()
        question = 'Which benchmark is used?'
        with patch.object(llm, 'complete', return_value='The ZEBRA benchmark. [p. 1]') as complete:
            response = self.client.post(f"/api/papers/{paper['id']}/analyze",
                                        json={'kind': 'question', 'question': question})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(complete.call_args.args[2], question)
        self.assertEqual(response.json['analysis']['question'], question)
        self.assertIn('ZEBRA', self.history(paper['id'])[0]['answer'])

    def test_unconfigured_model_reports_setup_error(self):
        paper = self.save_paper()
        with patch('app.download_paper') as download:
            response = self.client.post(f"/api/papers/{paper['id']}/analyze", json={'kind': 'summary'})
        self.assertEqual(response.status_code, 400)
        self.assertIn('Connect an AI model', response.json['error'])
        download.assert_not_called()
        self.assertEqual(self.history(paper['id']), [])

    def test_invalid_pdf_is_rejected_without_saving(self):
        response = self.client.post('/api/upload', data={'file': (io.BytesIO(b'plain text'), 'fake.pdf')})
        self.assertEqual(response.status_code, 400)
        self.assertIn('valid PDF', response.json['error'])
        self.assertEqual(self.client.get('/api/papers').json['papers'], [])

    def test_missing_paper_returns_actionable_json(self):
        response = self.client.get('/api/papers/9999')
        self.assertEqual(response.status_code, 404)
        self.assertIn('library', response.json['error'])
