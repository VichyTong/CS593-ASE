# Verification record

Dates: October 3–4, 2026. Environment: macOS, Python 3.11.4, local browser preview. Live AI follow-up: October 4.

## Automated checks

**14 tests passed** with `python -m unittest discover -s tests -v` after the final backend corrections. These tests use temporary databases and mocked external APIs. The JavaScript syntax check and `git diff --check` also passed.

Coverage includes restart persistence, PDF extraction, metadata editing, upload deduplication, invalid/scanned PDFs, missing-model behavior, full-text prompt construction, saved Q&A, analysis cache reuse, citation validation, content sharing during deletion, long-paper context selection, provider errors, origin checking, stop-word query handling, publication-date extraction, and arXiv identifier enrichment.

## Live browser checks

| Check | Observed result |
| --- | --- |
| Real arXiv search by ID `1706.03762` | Returned *Attention Is All You Need*, eight authors, 2017, abstract, and source link. |
| Keyword query `attention is all you need` | Initially returned zero results; after common-word filtering it returned 8,126 results in a live API request. An ID remains better for an exact known paper. |
| Save and browse | Saved the search result and saw it in My library. |
| Refresh persistence | Reloaded the browser; the saved record remained. |
| Process restart persistence | Restarted the server during fixes; the saved arXiv record remained. |
| Download actual public PDF | Downloaded the 15-page arXiv PDF (2,215,244 bytes). |
| Load full text from a saved result | Used the reading-room button; the actual arXiv PDF was downloaded and all 15 pages became available. |
| PDF upload | Extracted 15 readable pages and saved the PDF. |
| Metadata correction | First upload exposed a wrong title/year; repaired extraction and identifier enrichment. A fresh upload then showed the correct title, all eight authors, 2017, and the abstract. |
| Edit details | Saved the review form and verified the updated paper view. |
| Source inspection | Opened Source text and expanded physical PDF page 1. |
| Responsive layout | Inspected desktop at 1440 x 1000 and mobile at 390 x 844; mobile document width equaled the viewport (no horizontal overflow) for discovery and reading. |
| AI configuration | User configured the ignored local key. Restarted with `gpt-6-luna`, `reasoning_effort=none`, and a 1,800-token output cap. |
| Live summary | Generated five sections from the full extracted 15-page paper through the real OpenAI API. Saved model, coverage, page references, and source excerpts. |
| Live Q&A | Asked “What datasets are used, and what results are reported?” Received a real answer about WMT 2014 and Penn Treebank, with concrete results and PDF references. |
| AI persistence and reuse | Reloaded the browser and saw both saved responses. Repeated both API requests; each returned the existing result with `cached=true`. |
| Grouped citations | Fixed frontend rendering of grouped references such as `[pp. 7–8]`. Clicking its page 7 button opened physical PDF page 7 with the training data section. |

## Observed issues and repairs

1. Natural-title search required every common word. It now omits common English stop words; a regression test verifies query construction.
2. A copyright notice and dataset date were selected as PDF metadata. Prominent title text, publication-context years, contribution-footnote boundaries, and identifier-based arXiv enrichment repair the demonstrated case.
3. Supporting UI text was too pale in the first visual pass; contrast was increased.
4. The skip-to-content link conflicted with hash routing; it now focuses the main element directly.
5. Gunicorn worker reload on macOS triggered an Objective-C fork error. The verified local demo uses `python app.py`; Gunicorn deployment instructions are scoped to Linux. Docker was not available here, so its configuration was not run.
6. The live model used grouped page references. The backend already recognized them, but the frontend only linked single-page references. The renderer now expands grouped references into page buttons; verified through the actual saved answer.

## Evidence

`evidence/01-home.jpg`, `02-search.jpg`, `03-library.jpg`, `04-upload.jpg`, `05-metadata.jpg`, `06-summary.jpg`, `07-question.jpg`, `reading-room.jpg`, `08-evidence.jpg`, `09-mobile.jpg`, and `mobile-home.jpg` are actual browser screenshots from this session. `live-ai-verification.json` preserves the real responses, model, citations, and cache checks without credentials. `metadata-before.jpg` records the failed extraction before the repair. `ai-setup-pending.jpg` preserves the earlier configuration gate for historical context.

The model noted that the supplied paper reports 41.8 English–French BLEU in its table and 41.0 in the results paragraph. Both numbers were checked in extracted physical page 8. This spot check and page validation do not establish that every generated claim is correct.

No cloud deployment or Brightspace submission is claimed by this record. The student supplied personal reflection details on October 9; these are now incorporated and distinguish personal functional checks from agent-run verification. Three genuine conversation screenshots supplied October 8 are included as Figures 1-3; they show the initial request, initial delivery/setup response, and model-selection follow-up, rather than individual debugging exchanges.

## Artifact verification

The reflection draft was rendered and visually inspected. Earlier versions embedded the before/after metadata screenshots; the October 8 quality update below replaces those application figures with vector content. The 88-second `demo.mp4` is a captioned walkthrough assembled from actual browser screenshots of all five required flows, including the real `gpt-6-luna` summary and answer. It was decoded successfully and representative frames were inspected. The earlier 70-second `demo-preview.mp4` is retained as an incomplete historical preview; use `demo.mp4` for review/submission. The walkthrough is a screenshot sequence, not a continuous screen recording.

October 8 PDF-quality update: the report's raster application figures were replaced by two vector pages from `application-evidence.pdf`. The first is explicitly a transcription of visible values in the historical failure screenshot. The second renders the app's metadata HTML/CSS populated from the saved paper record, with print-only layout adjustments to reveal all authors and the full abstract. A headless renderer processed local HTML without desktop automation or model calls. Both standalone pages and their embedded report versions were checked for extractable text and zero raster images. The three user-supplied conversation screenshots remain unchanged.


## October 9 submission preparation

The application was copied into a fresh directory without local credentials, the original virtual environment, or the original database. Following the README, a new Python 3.11.4 environment installed only `requirements.txt` and used `.env.example` with an empty key. `pip check` reported no broken requirements, all 14 automated tests passed, and JavaScript syntax validation passed. Actual HTTP checks confirmed the homepage and static assets, a PDF upload, the correct missing-model message, and persistence after stopping and restarting the app process.

The 88-second demo decoded all 2,112 frames successfully, and all nine scene samples were visually checked. Repository candidates were checked against the locally configured credential values and common token patterns with no findings. `.env`, runtime data, and virtual environments remain ignored. Anonymous GitHub access returned 404, so grader access still requires confirmation. Detailed non-secret results are in `evidence/submission-checks.json`.

The report now incorporates the student's October 9 account: choosing Codex for its interface and newer models, personally trying all five required features, surprise at the 53-minute-55-second initial run after brief design guidance, and the plan to prepare API access and model choice earlier next time. Existing Figures 2 and 3 are explicitly connected to the unfinished AI setup, the student's configuration/model instruction, and the reported successful verification. They do not claim to show the separate search/metadata debugging exchanges.

The personalized seven-page report compiled successfully and every page was visually checked. All report text is black, the five prompts and draft notice are removed, and the embedded application evidence remains vector PDF. Overleaf commit `d64719e` and GitHub application/materials commit `5952063` were pushed and verified against the remote branch. No Brightspace submission was performed.
