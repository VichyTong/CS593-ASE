Papertrail Homework 2 improvement round 1

This is the separately runnable PDF-focused round requested in the current
English chat. It retains all 37 initial HW2 methods without changing their
assertions and adds 8 methods, for 45 HW2 methods. No legacy HW1 tests or older
experiments are included. Application source is unchanged. No round 2 or final
homework report is included.

Start with experiment-notes.txt for actual results, failures, coverage changes,
correctness review, and limitations. feedback-request.txt preserves the user's
actual round 1 guidance. design-and-setup.txt explains fixture-specific expected
values, requirement ambiguities, and setup decisions before test execution.

Tests and provenance

The following are byte-identical copies from initial_stage/tests:
  initial_support.py
  test_components.py   8 methods
  test_validation.py  14 methods (including both known validation bugs)
  test_workflows.py   15 methods

The additions are tests/test_pdf_round1.py (8 methods) and its fixture generator,
tests/pdf_fixtures_round1.py. Limits and fallback metadata are exercised through
real generated PDFs, pypdf extraction, the upload API, and SQLite. Only external
HTTP boundaries are mocked. Limits are not reduced or patched. Fixtures are
generated on demand; no huge fixture files are committed or retained.

Reproduce from /Users/tong172/Desktop/projects/593-ASE:

  solutions/hw1/.venv/bin/python -B solutions/hw2/round1_stage/run_round1.py --output solutions/hw2/round1_stage/reproduced/round1-only

Choose a new output directory for every run. The runner refuses to overwrite
evidence or to write outputs within the protected initial_stage directory.
It also verifies frozen code and the protected original files before and after
execution. Failing methods are genuine failures; a nonzero exit must not be
interpreted as a setup error without inspecting results and diagnostics.

The existing interpreter and packages are used in the recorded experiment.
For a new environment, these installation commands are provided but were not
executed during this round:

  python3 -m venv solutions/hw2/round1_stage/.venv
  solutions/hw2/round1_stage/.venv/bin/python -m pip install -r solutions/hw2/round1_stage/requirements-test.txt

Substitute that interpreter when running the suite if using the new environment.

Coverage comparison

Compare the preserved initial HW2-only run in
  solutions/hw2/initial_stage/evidence/initial-only
against the current HW2-only round in
  solutions/hw2/round1_stage/evidence/round1-only

The initial measurement is reused from its original execution, not rerun or
overwritten. Exact copies of its raw top-level output files are included in
evidence/initial-comparison-reference for convenience. Their hashes are checked
against the original. These are reference copies, not new measurements.

Both sides include exactly these application files:
  solutions/hw1/app.py
  solutions/hw1/database.py
  solutions/hw1/pdf_tools.py
  solutions/hw1/providers.py

Coverage settings are unchanged: coverage.py 7.17.0, branch=True,
config_file=False, the explicit four-file include list, no omit list, and tracing
started before application import. All 522 executable statements and 174 branch
destinations remain in scope, including guarded server startup in app.py.
Excluded targets include tests, templates, static JavaScript/CSS, dependencies,
and submission tooling. No browser or JavaScript coverage is claimed.

Do not use the HW1-only or combined results as the initial side of this primary
comparison. This round measures only retained initial HW2 tests plus round 1
additions. The older solutions/hw2/tests/test_round1.py was not executed or used
as this round's test source.

Coverage JSON contains separate covered-line and covered-branch counts.
coverage.txt's Cover column combines statements and branch destinations and
therefore differs from a line-only percentage. comparison.json and the notes
report separate metrics for both suites and every application module.

Safety and evidence preservation

The runner disables dotenv loading, clears inherited configuration and keys,
uses temporary SQLite/PDF storage, supplies only dummy credentials, and blocks
real HTTP/socket access. No personal PDFs or library records are required.

evidence/pre-round1-provenance.json protects every file in initial_stage and
the older experiment artifacts. evidence/frozen-inputs.zip and its manifest
preserve the exact round 1 tests, runner, requirements, setup notes, and relevant
application snapshot before the first round 1 application test run. The original
initial_stage remains complete at its original location.

Each original run output includes unittest output, diagnostics, native .coverage
data, coverage JSON/text, HTML coverage, and machine-readable results. The final
round1-evidence.zip preserves these including files ignored by Git. Integrity
checks and SHA256 manifests distinguish originals from derived comparisons.

Only new files inside round1_stage were written for this round. No initial
test correction, application repair, commit, push, round 2 work, or final report
was performed.
