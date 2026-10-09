# Papertrail demo script

Target length: 2-3 minutes. Use the running app at http://127.0.0.1:8000. Record the browser window, without exposing `.env` or an API key.

The assignment explicitly requires search, save, PDF upload, a generated summary, and at least one answered question. A complete demo must show real model output. The app does not contain a mock/demo AI mode.

## Before recording

1. Configure a working model in `.env` and restart the app.
2. Check that **AI settings** shows the expected model, then verify one real summary.
3. Download the public PDF [Attention Is All You Need](https://arxiv.org/pdf/1706.03762). Its arXiv record is [1706.03762](https://arxiv.org/abs/1706.03762).
4. Use a separate `DATA_DIR` if you want an empty demo library. Keep that directory through restarts to demonstrate persistence. Do not delete your own research library just to reset the demo.

## Recording sequence

| Time | Action | Suggested narration |
| --- | --- | --- |
| 0:00-0:15 | Open Discover | “This is Papertrail, an AI research assistant built with Codex. It brings discovery, a persistent library, and paper analysis into one workspace.” |
| 0:15-0:40 | Search `software testing`, then search `1706.03762` | “Search calls the arXiv API. Results include the title, authors, year, abstract, and original paper link. An exact arXiv ID finds a known paper.” |
| 0:40-0:55 | Save the result, open My library, refresh | “The paper is saved to SQLite. It remains available after a page refresh or server restart.” |
| 0:55-1:20 | Upload the PDF and inspect metadata | “Uploaded PDFs are processed locally. This paper’s arXiv identifier matches its bibliographic record. Other papers use PDF text and optional AI extraction. Details are editable.” |
| 1:20-1:55 | Open AI summary, click Generate summary | “The model reads extracted PDF content, rather than just the title or abstract. The summary covers the research question, method, findings, limitations, and takeaway. Page references connect it to the source.” |
| 1:55-2:25 | Ask “What datasets are used, and what results are reported?” | “The answer is grounded in this paper’s text. I can expand the excerpts and follow a page reference. The question and answer are saved with the paper.” |
| 2:25-2:45 | Click a page reference, refresh, return to AI summary | “Source text remains inspectable, and the analysis persists. The interface also adapts to smaller screens.” |

## Accuracy notes

- Do not claim a live model check from automated tests; those tests mock model responses.
- If the provider is unavailable, resolve it before recording the summary/Q&A segments. A setup dialog is not a successful AI demonstration.
- If a captioned walkthrough is assembled from screenshots, label it as such. It should show actual completed actions and results, not reconstructed or fabricated application output.
- A continuous screen recording is the strongest demonstration of interaction. The script can be used to make one with your preferred screen recorder.
