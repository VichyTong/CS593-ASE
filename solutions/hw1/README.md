# Research Desk — HW1 AI Research Assistant

A complete local web application for finding, collecting, and understanding research papers. Built with **Flask, vanilla JavaScript, SQLite, pypdf, arXiv, and an OpenAI-compatible LLM API**.

## Quick start

Python **3.11 or newer** is recommended. No Node.js build step is required.

```bash
cd solutions/hw1
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
python app.py
```

On Windows PowerShell, activate with `.venv\Scripts\Activate.ps1` and use `Copy-Item .env.example .env`. If `.env` already exists, edit it instead of overwriting it.

Open **http://127.0.0.1:8000**. The server starts with an empty library on a clean installation. Search and PDF upload work without an LLM key. **Real summaries and questions require a configured model**; the app never substitutes canned answers.

### Configure the LLM

Edit `.env` locally and restart the server:

```dotenv
LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=your-api-key
LLM_MODEL=gpt-6-luna
```

The model is configurable; the example is not an automatic claim that your provider supports it. For another OpenAI-compatible provider, set its base URL (including `/v1` when required), key, and exact model name. The app calls `/chat/completions` with `model`, `messages`, and a 1,200-token output limit. GPT-6 Luna uses `reasoning_effort=none` and the standard service tier. Credentials are read on the server and never returned to the browser. `OPENAI_API_KEY` also works if `LLM_API_KEY` is empty.

Optional local Ollama setup (install Ollama separately and use a model that fits your computer):

```dotenv
LLM_BASE_URL=http://localhost:11434/v1
LLM_API_KEY=ollama
LLM_MODEL=your-installed-model
```

Allow sufficient context in the chosen model for up to 42,000 characters of paper text plus instructions. Provider-specific request limits can differ. HTTP is accepted only for loopback model endpoints; hosted endpoints require HTTPS.

## Features and usage

1. **Search:** enter keywords such as `software testing`, a topic such as `retrieval augmented generation`, or an arXiv ID such as `1706.03762`. Results include title, authors, first-publication year, abstract, and a source link. Keyword searches AND the words together. arXiv provides up to 12 results per request; it is not a comprehensive index of every discipline.
2. **Save:** click **Save to library**. Browse or filter **My library**. Repeated saves are deduplicated by arXiv ID. SQLite retains papers, text, summaries, and questions across reloads and restarts.
3. **Upload:** click **Upload a PDF** and choose a text-based paper (20 MB / 150 pages maximum). The app extracts all readable pages and bibliographic metadata. If a model is configured, it improves metadata using the first two pages. A review form lets you correct title, authors, year, and abstract. Identical uploads are deduplicated by SHA-256.
4. **Read:** open a paper. For a search result, select **Load full paper** to fetch and extract its arXiv PDF. Inspect **Source text**, organized by original PDF page number. Download the saved PDF when needed.
5. **Summarize:** open **AI notebook → Generate summary**. The model receives actual PDF text, not only search metadata. The response covers the problem, approach, evidence, results, and limitations.
6. **Ask:** ask a natural-language question. Answers include requested `[p. N]` references and expandable source excerpts. Questions in Chinese are supported by the prompt, subject to the configured model's abilities. Every successful analysis is saved.
7. **Manage:** edit metadata or remove a paper with confirmation. Deleting one record preserves any PDF still referenced by another record.

## Architecture

```text
Browser (HTML / CSS / JavaScript)
             |
        Flask JSON API
         /      |       \
  arXiv API   SQLite    OpenAI-compatible model API
      |         |             ^
   PDF fetch -> pypdf -> page-preserving text/context selection
```

| File / directory | Responsibility |
| --- | --- |
| `app.py` | App factory, REST endpoints, validation, orchestration, optional authentication |
| `database.py` | SQLite schema, transactions, serialization |
| `providers.py` | arXiv Atom search, allowlisted PDF download, LLM HTTP client |
| `pdf_tools.py` | PDF parsing, metadata fallback, page-preserving context selection |
| `templates/index.html` | Accessible interface structure and dialogs |
| `static/` | Responsive styling and frontend state/actions |
| `tests/test_app.py` | Focused integration checks with external API mocks |
| `docs/` | Demo guide, reflection draft, development evidence, submission checklist |
| `data/` | Runtime-only SQLite database and PDFs; excluded from Git |

SQLite uses `papers` and `analyses` tables. Each operation has a short-lived connection, parameterized SQL, foreign keys, and transactions. Foreign-key cascade removes a deleted paper's analyses. PDFs use content hashes rather than untrusted filenames.

### Grounding and limits

The app sends all extracted text if it fits within the 42,000-character budget. For a longer paper, summaries use excerpts spread through the paper; questions rank chunks by keyword matches and include the opening context. The UI records the coverage for each response. This is lightweight retrieval, not an embedding-based search engine or a guarantee of complete coverage. The prompt asks the model to report missing evidence and treat paper instructions as untrusted. Citation page numbers are checked against supplied pages; unsupported or absent references produce a warning. Page validation does **not** prove that a model's interpretation is correct.

Metadata extraction is best effort. Some PDFs have absent or misleading metadata; multi-column text, equations, tables, scanned pages, and unusual layouts may extract poorly. Scans with no readable text are rejected with an OCR explanation. The year in arXiv search is the first arXiv publication year and may differ from a later conference/journal year. Unknown metadata stays blank and is editable.

PDF content is sent to the configured LLM provider only for model-backed metadata extraction, summaries, or questions. Local files and analyses remain in `data/`. Do not upload private papers to a hosted model unless you are permitted to share them with that provider.

## Configuration

| Variable | Default | Use |
| --- | --- | --- |
| `LLM_BASE_URL` | `https://api.openai.com/v1` | Compatible API base |
| `LLM_API_KEY` | empty | Server-side credential; required for AI |
| `LLM_MODEL` | `gpt-6-luna` | Exact model identifier |
| `LLM_TIMEOUT` | `120` | Model read timeout, seconds |
| `LLM_BUDGET_USD` | `5.00` | Persistent conservative spending ceiling |
| `LLM_MAX_OUTPUT_TOKENS` | `1200` | Per-request output limit |
| `LLM_INPUT_PRICE` / `LLM_OUTPUT_PRICE` | `0.125` / `0.50` | USD per million tokens, using the highest standard input rate |
| `DATA_DIR` | `data` | Database and PDF directory; relative to application root |
| `HOST` / `PORT` | `127.0.0.1` / `8000` | Development listener |
| `APP_USERNAME` / `APP_PASSWORD` | empty | Optional Basic authentication; set both together |

## Cache and spending controls

For OpenAI `gpt-6-luna`, the request explicitly enables prompt caching with a 30-minute TTL and marks the paper text as the reusable prefix. The question comes after that prefix. This allows different questions about the same short paper to reuse the same cached text. Cache hits depend on provider behavior and matching prefixes; changing selected excerpts can reduce reuse.

Two additional local caches avoid calls entirely: identical successful LLM requests are stored in SQLite, and repeated summaries or identical questions return the existing analysis without another charge. Cached results survive restarts. No automatic model retry is performed.

The default budget is **$5 USD**, as requested. Before each uncached request, the app reserves a conservative cost using UTF-8 bytes plus a framing allowance as an upper estimate of input tokens, the configured cache-write input rate, and the maximum output tokens. Reservations persist even after errors, so a timeout cannot silently reset the spending allowance. Calls are rejected before network access when the next reservation would exceed the limit. Actual token usage, provider-reported cached tokens, and a conservative usage-based estimate are stored in `llm_calls` and exposed through `/api/status`. This is an application-side limit, not a provider account billing cap; it covers only calls through this database and assumes the configured prices are correct. Other apps using the same key are outside its scope. Do not delete the runtime database to reset a budget unintentionally.

Default rates match [GPT-6 Luna Standard pricing](https://developers.openai.com/api/docs/models/gpt-6-luna), checked October 1, 2026: $0.10 input, $0.01 cached input, $0.125 cache writes, $0.50 output per million tokens. Estimates deliberately count all input at $0.125. Update the price variables before choosing a different model, provider, or service tier. A higher-priced model with unchanged rates would invalidate the estimate.

## Run checks

```bash
python -m unittest discover -s tests -v
```

Tests use temporary databases and synthetic PDFs, with network/model responses mocked. They check persistence across app recreation, upload parsing, deduplication, shared-file deletion, metadata correction, no-key/full-text gating, real-text prompt construction, saved Q&A, citation warnings, context selection, provider failures, and the LLM request format. They do not prove a live provider works. Live verification is recorded separately in `docs/VERIFICATION.md`.

## Deployment

This assignment app is intended for one user's research library. For a local demonstration, `python app.py` is sufficient. For a persistent server on Linux:

```bash
source .venv/bin/activate
gunicorn --workers 1 --threads 4 --timeout 180 --bind 127.0.0.1:8000 'app:create_app()'
```

Use one worker to keep the in-process arXiv throttling consistent. Put a reverse proxy with HTTPS in front of a public installation, configure both authentication variables, and mount a persistent `DATA_DIR`. Basic authentication must be protected by HTTPS. This app has a single shared library, not separate user accounts. Do not use Flask's development server for public hosting.

Alternatively, with Docker installed:

```bash
docker compose up --build -d
```

The Compose configuration binds only `127.0.0.1:8000` and keeps `/app/data` in a named persistent volume. Configure `.env` before starting. Stop with `docker compose down`; do not add `-v` unless you intentionally want to delete the library. Container localhost refers to the container, so the sample Ollama loopback configuration is for native execution, not Docker.

### Troubleshooting

- **No results:** try fewer keywords or a known ID; punctuation alone is not a valid query.
- **arXiv unavailable:** the public service can throttle or time out. Searches are spaced at least three seconds apart and cached for five minutes within one worker. Wait and retry; PDF upload remains available.
- **Full text unavailable:** retry the download, or obtain the PDF yourself and upload it as a separate library entry.
- **No model:** edit `.env` and restart. Model setup reports configuration, not guaranteed provider availability.
- **401/403 or 429 from model:** check credentials, model access, quota, and provider limits. Keys and raw provider errors are not shown in the browser.
- **Metadata wrong:** use the review form. Automatic extraction cannot reliably recover information absent from the PDF.
- **Missing library after deployment:** keep `DATA_DIR` on persistent storage and use the same directory after restart.

## Submission materials

- Repository: https://github.com/VichyTong/CS593-ASE (application in `solutions/hw1`).
- `docs/demo.mp4`: 1 minute 44 second captioned walkthrough made from real application screenshots.
- `docs/DEMO_SCRIPT.md`: step-by-step plan and narration for a continuous recording if needed.
- `docs/reflection.pdf`: formatted reflection draft, still requiring student review and genuine chat screenshots.
- `docs/REFLECTION.md`: agent-assisted reflection draft grounded in this development session; review and personalize before submission.
- `docs/SUBMISSION_CHECKLIST.md`: requirement mapping and remaining user-dependent items.
- `docs/VERIFICATION.md` and `docs/evidence/`: actual validation and screenshots.

## Primary references

- [arXiv API manual](https://info.arxiv.org/help/api/user-manual.html)
- [OpenAI Chat Completions API](https://developers.openai.com/api/reference/resources/chat)
- [OpenAI prompt caching](https://developers.openai.com/api/docs/guides/prompt-caching)
- [Ollama OpenAI compatibility](https://docs.ollama.com/api/openai-compatibility)
- [Flask documentation](https://flask.palletsprojects.com/)
- [pypdf text extraction](https://pypdf.readthedocs.io/en/stable/user/extract-text.html)

The application was developed with Codex, including implementation, debugging, and documentation. See the reflection for the extent of agent assistance and the distinction between live and mocked verification.
