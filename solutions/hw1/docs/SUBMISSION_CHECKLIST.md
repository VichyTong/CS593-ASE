# Homework 1 submission checklist

The brief says **October 10, 11:59 PM**. It does not explicitly state a timezone; confirm the course/Brightspace timezone. The application is 60% of the homework grade and the reflection is 40%.

## Application

| Requirement | Implementation | Verification |
| --- | --- | --- |
| Graphical frontend and backend | Responsive Papertrail UI and Flask API | Browser checked on desktop/mobile |
| External paper search | arXiv API with full result metadata, sorting, and pages | Real ID and keyword queries checked |
| Persistent local library | SQLite papers and analysis history | Browser refresh, server restart, and integration test |
| PDF upload and metadata | pypdf, identifier enrichment, optional model extraction, review form | Real 15-page research paper verified |
| LLM summary from paper content | Full-text extraction and bounded page-preserving context | Real `gpt-6-luna` summary verified October 4 |
| Paper Q&A | Text-grounded answers, page references, saved history | Real answer, citation navigation, refresh persistence, and cache reuse verified |

## Repository

- [x] Complete source, dependency pins, configuration example, and run/setup instructions.
- [x] README describing the features, architecture, limitations, tests, and deployment options.
- [x] Credentials excluded from Git and kept on the server.
- [x] Existing repository link: https://github.com/VichyTong/CS593-ASE.
- [ ] Review and commit/push this local version so the submitted link contains these changes.
- [x] Run the README instructions in a clean environment: fresh Python 3.11 environment, example configuration, dependency installation/check, 14 passing tests, actual HTTP startup/upload, and restart persistence verified October 9. That day's live arXiv request returned HTTP 429; earlier successful live checks are recorded separately.
- [ ] Confirm grader access. The Git remote works with the current account, but anonymous GitHub access returned 404 on October 9.

## Demo video

- [x] Real screenshots of search, saving, upload, corrected metadata, reading, and responsive layout.
- [x] `DEMO_SCRIPT.md` provides the complete five-flow recording plan.
- [x] Configure `.env`, restart the app, and verify a real generated summary and answered question.
- [x] Complete `demo.mp4` with all five required flows. The 88-second captioned walkthrough uses actual browser screenshots and real AI responses. Use `DEMO_SCRIPT.md` if you prefer a continuous screen recording.

## Reflection report

- [x] `REFLECTION.md` covers all five required discussion topics with observed development events.
- [x] Actual failure evidence and correction details are preserved.
- [x] Personalized seven-page report uploaded to [Overleaf](https://www.overleaf.com/project/6ac7d8e49907ab7405d67d38) on October 9. Local compilation and visual inspection passed. Application figures retain vector text; original conversation screenshots are included.
- [x] Replace all five personal prompts using the student's October 9 account and remove the draft notice. Black report text retained.
- [ ] Student reads the finished wording before submission.
- [x] Add genuine Codex conversation screenshots: Figures 1-3 show the initial prompt, initial delivery/setup exchange, and model-selection follow-up with the reported verification result. Added October 8; individual debugging exchanges are not pictured.
- [x] Explain the incomplete AI setup and the student's corrective configuration/model input alongside Figures 2 and 3. The separate search/metadata debugging exchanges are not pictured; additional original captures could strengthen those examples.
- [x] Compile the personalized report to `reflection.pdf`; `reflection-overleaf.pdf` is an identical copy. Older draft/preview artifacts are not submission files.

## Final submission

- [x] Check repository candidates for local credentials and common token patterns; keep `.env` and runtime data out of Git.
- [ ] Confirm the repository is accessible to the grader.
- [x] Check that the video plays and includes search, save, upload, summary, and one answered question.
- [x] Include the student's own discussion and original chat evidence; final wording still requires the student's read-through.
- [ ] Submit the repository link, video, and report on Brightspace.

See `VERIFICATION.md` for the precise difference between implemented, tested with mocks, and verified live. The agent has not submitted anything to Brightspace.
