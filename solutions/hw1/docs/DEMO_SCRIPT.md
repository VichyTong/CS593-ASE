# Demo video

`demo.mp4` is a captioned walkthrough assembled from genuine browser screenshots captured during successful live operation. It shows real search results, saved papers, uploaded metadata, a real GPT-6 Luna summary, a real answer, and source evidence. It is an edited screenshot walkthrough, not a continuous screen recording. No model answer or search result was fabricated. You may submit it if that format is acceptable to the instructor, or use the following script for a continuous personal recording.

## Suggested continuous recording (2–3 minutes)

Start the app using the README and open http://127.0.0.1:8000. Keep keys, terminals displaying configuration, and unrelated windows out of the recording.

| Approximate time | Action | Suggested narration |
| --- | --- | --- |
| 0:00–0:15 | Show the main screen | "Research Desk is my HW1 AI Research Assistant. It uses Flask, SQLite, arXiv, and GPT-6 Luna." |
| 0:15–0:35 | Search `1810.04805` or a research topic | "Search results include the title, authors, year, abstract, and original paper link." |
| 0:35–0:50 | Save a result; open My library; refresh | "Saved papers remain in the local SQLite library across refreshes and restarts." |
| 0:50–1:15 | Upload a text-based research PDF; review metadata | "PDF upload extracts title, authors, year, abstract, and page-numbered text. The extracted metadata can be corrected." |
| 1:15–1:40 | Open AI notebook; generate a summary | "The summary uses the PDF's text. It records its coverage and includes page references." |
| 1:40–2:05 | Ask about datasets and baselines | "This answer is generated from the selected paper. I can expand a cited page to compare the claim with the evidence." |
| 2:05–2:20 | Repeat the question | "An identical question returns the saved result without another API charge. Prompt caching also reduces repeated input cost for different questions." |

For the demonstrated paper, a useful question is: "What datasets are used, and what are the main results compared with the baselines?"

The downloaded arXiv PDF can be obtained from the paper's **Download PDF** button. Upload it through the file picker to demonstrate the upload path. A search result and its uploaded PDF may appear as separate entries because their source identifiers differ, but they can safely share the stored PDF.

The original live demonstration made three paid requests total: summary, metadata extraction, and question answering. Reusing cached results during the recording is intentional; explain that rather than claiming each replay makes a fresh API request.
