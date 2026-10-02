# Verification record

Verified locally on October 1, 2026 (America/Indianapolis).

| Area | Evidence / result |
| --- | --- |
| Real paper search | arXiv returned Attention Is All You Need (1706.03762) and BERT (1810.04805) |
| Library persistence | Saved records survived server restarts and browser refreshes; automated app-recreation test also passed |
| Full PDF download | arXiv paper downloaded and parsed into 15 pages |
| Upload | The same real PDF uploaded through the browser; title, all eight authors, year, and abstract extracted and reviewed |
| Real summary | GPT-6 Luna produced a summary from the full extracted PDF text |
| Real question | Model answered a question about datasets and baselines, with references to PDF pages |
| Citation presentation | Combined citations and ranges parsed; source excerpts available in the interface |
| Local result cache | Repeated question returned "Reused the saved result. No new model charge." |
| Provider prompt cache | Live API response reported 10,418 cached input tokens |
| Spending | Three paid requests; conservative usage-based estimate **$0.003459**, well below the **$5** limit |
| Automated checks | 19 tests passed; see `evidence/tests-after.txt`. External services are mocked in these checks |
| Desktop and mobile layout | Inspected in browser; 390-pixel mobile viewport had no horizontal overflow; screenshots in `evidence/` |

The conservative usage estimate counts all prompt tokens at the cache-write rate, even when the API reported a cheaper cache read. It is not a provider invoice. Request reservations are larger still and remain in the local database to enforce the spending ceiling. The API key and all uploaded PDF data are excluded from the repository.

## Observed issues and fixes

- Initial PDF inspection assumed PyMuPDF was installed. It was not. The source was read with pypdf and visually inspected with Poppler instead.
- The first shared-file deletion implementation removed a PDF still used by another record. A regression reproduced HTTP 500; reference-aware deletion fixed it.
- A live model response included combined/range citations that the original single-page matcher missed. Citation parsing and its check were extended; saved evidence was repaired without another paid call.
- A Gunicorn hot reload failed on macOS due to an Objective-C fork issue. The local demonstration uses Flask's development server. Production instructions target Linux.

## Verification boundaries

- Later arXiv requests returned HTTP 429 or timed out. Earlier searches succeeded and are preserved in the evidence; live search availability depends on arXiv. Avoid repeated retries during a limit window.
- `demo.mp4` is a captioned walkthrough edited from authentic application screenshots, not a continuous screen recording. Its search frame was captured before the final palette change and is labeled accordingly.

- Docker configuration is included but was not executed; Docker is not available in the environment.
- No public hosting service was deployed. The running demonstration is local.
- Model answers were inspected against extracted text, but this does not constitute a factual benchmark or a guarantee against hallucinations.
- Browser screenshots document the app. The tool disallowed capturing the Codex app, so the required conversation screenshots remain a student-supplied step.
