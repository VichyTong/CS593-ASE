Papertrail Homework 2 initial test stage

This is the initial generation and evaluation requested in the current English
chat on November 2, 2026 (America/Chicago). The new suite contains 37 unittest
test methods. Its first execution is preserved, including genuine failures.
No improvement round or final homework report is included.

Files and provenance

  tests/test_workflows.py   15 new methods covering the main application flows
  tests/test_validation.py 14 new methods covering validation and failures
  tests/test_components.py  8 new methods covering lower-level contracts
  tests/initial_support.py Synthetic fixtures and disposable application setup
  run_initial.py           Offline runner and evidence collector
  experiment-notes.txt     Results, test review, bugs, and remaining gaps
  setup-notes.txt          Actual environment and harness configuration
  generation-request.txt  The actual user request, with line wrapping normalized
  interaction-excerpts.txt Selected genuine chat excerpts, not a full transcript
  evidence/                First executions, coverage, hashes, and frozen inputs

The 14 pre-existing Homework 1 methods remain in
solutions/hw1/tests/test_app.py. They are not newly generated Homework 2 tests.

Existing solutions/hw2/tests/test_initial.py, test_round1.py, support.py,
run_experiment.py, and solutions/hw2/evidence existed before this request.
They were not modified or executed here. Their results must not be attributed
to this initial stage. Their hashes are recorded in evidence/frozen-manifest.json.
The older initial suite and helper were inspected as existing-test context;
the older round1 test contents were not used to generate this suite.

Reproducing the measurements

Run commands from the repository root:
  /Users/tong172/Desktop/projects/593-ASE

The existing interpreter used for the recorded runs is:
  solutions/hw1/.venv/bin/python

For a fresh environment (not installed during the recorded experiment):
  python3 -m venv solutions/hw2/initial_stage/.venv
  solutions/hw2/initial_stage/.venv/bin/python -m pip install -r solutions/hw2/initial_stage/requirements-test.txt

Choose the appropriate interpreter and run each measurement in a new process:

  solutions/hw1/.venv/bin/python -B solutions/hw2/initial_stage/run_initial.py --suite legacy --output solutions/hw2/initial_stage/reproduced/hw1-only
  solutions/hw1/.venv/bin/python -B solutions/hw2/initial_stage/run_initial.py --suite initial --output solutions/hw2/initial_stage/reproduced/initial-only
  solutions/hw1/.venv/bin/python -B solutions/hw2/initial_stage/run_initial.py --suite combined --output solutions/hw2/initial_stage/reproduced/combined

The output directory must not already exist. The runner refuses to overwrite
evidence or run against changed frozen inputs. Reproduction directory names can
be changed without affecting the measurement scope. The initial and combined
runs currently exit with status 1 because they detect application bugs. Do not
mark those tests as expected failures or change the assertions to claim success.

All three measurements include exactly these application files:
  solutions/hw1/app.py
  solutions/hw1/database.py
  solutions/hw1/pdf_tools.py
  solutions/hw1/providers.py

Coverage uses coverage.py 7.17.0, branch=True, config_file=False, an explicit
include list, and no omit list. It starts before application import. There are
522 executable Python statements and 174 branch destinations in this snapshot.
Test code, templates, CSS, JavaScript, submission tools, dependencies, and the
Python __main__ server startup environment are not separate measured targets.
The guarded startup line inside app.py remains included and uncovered.

Suite definitions for later comparison:
  legacy   = only solutions/hw1/tests/test_app.py (14 methods)
  initial  = only this directory's three test_*.py modules (37 methods)
  combined = the above two suites together (51 methods)

Use initial-only as the primary baseline for evaluating newly generated tests.
If later comparisons include Homework 1 tests, compare against combined instead.
Keep the same four application files, coverage options, and test provenance.
Do not compare a generated-only initial result with a cumulative final result
without separately reporting the changed suite scope.

Each result directory contains raw unittest output, diagnostics, coverage JSON,
coverage text, the native .coverage database, HTML coverage, and results.json
with exact suite paths, counts, package versions, command, hashes, and events.
The text report's Cover column mixes statement and branch coverage. Separate
line and branch percentages in results.json and experiment-notes.txt use the
raw covered/total values; these are intentionally distinct metrics.

Safety and preservation

The runner disables dotenv loading, clears inherited configuration, uses dummy
keys and temporary data directories, and blocks real HTTP and socket access.
All arXiv and LLM responses are mocked; no paid calls or personal library access
are needed. The initial tests use the same guards when discovered directly,
but run_initial.py is the supported way to reproduce the full evidence.

evidence/frozen-inputs.zip was created before any of these tests ran. It contains
the exact generated tests, runner, setup record, runtime source, frontend assets,
README, requirements, and Homework 1 tests. It excludes .env, data/, personal
PDFs, virtual environments, and unrelated artifacts. The final evidence bundle
also preserves hidden coverage databases and HTML that Git normally ignores.

Only new files inside solutions/hw2/initial_stage were created for this stage.
The application and earlier experiment files were verified unchanged by hashes;
git diff for solutions/hw1 was empty. No commit or push was performed.
