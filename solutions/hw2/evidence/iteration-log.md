# Actual agent interaction and iteration record

This is a text record of this Codex session, not a reconstructed student conversation. The detailed iteration instructions below are agent-authored work instructions. They were not supplied by the student. No conversation screenshots are claimed.

## Student request (verbatim)

> 你可以帮我做这个作业吗？

The preceding student message asked for an explanation of the supplied HW2 PDF. Codex summarized its requirements before this authorization.

## Initial generation: agent work instruction

Generate a new, separate unittest suite for the existing HW1 Papertrail app. Cover its five required workflows and a few ordinary error paths with meaningful assertions. Use temporary SQLite/PDF storage and mocked search/model boundaries. Preserve the 14 legacy HW1 tests. Measure only app.py, database.py, pdf_tools.py, and providers.py, and archive the unmodified application before improvements.

Observed run: 12/12 test methods passed; 315/522 executable lines (60.34%) and 63/174 branch destinations (36.21%) covered. No application bugs were detected by this initial suite. Review found no incorrect initial assertions. Main gaps were the provider internals, download limits, PDF failures, long-document selection, and validation/state transitions. The homepage check only establishes HTML delivery, not browser interaction correctness.

## Round 1: coverage-guided agent work instruction

The initial provider module has 101/130 missed lines. Replace the coverage blind spot caused by mocking high-level search and LLM methods with focused tests of the actual provider code, mocking HTTP only. Check Atom parsing, query parameters, cache expiry/throttling, trusted redirects, streaming limits, request contracts, provider failures, PDF rejection paths, and bounded context/citation handling. Retain the initial suite unchanged. Do not infer LLM answer quality from a mock response.

Representative execution feedback: initial `coverage.txt` identifies providers.py lines 20-77, 81-102, 121-150, and 153-164 as unexecuted. The same immutable application snapshot is used for the next run.
