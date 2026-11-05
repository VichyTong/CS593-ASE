Papertrail Homework 2 improvement round 2

Round 2 is a separately runnable HW2-only regression suite guided by the actual
round 1 execution notes and coverage. It retains all 45 round 1 method identities,
strengthens four provider/error methods in the local copies, and adds 10 provider
methods: 55 total. No application code or earlier experiment directory changed.
The tests exposing all three known defects remain unchanged and still fail.

Read experiment-notes.txt for actual execution, the three-stage comparison,
correctness review, gap-to-test mapping, and limitations. The user's actual
English guidance is in feedback-request.txt. design-and-setup.txt records the
coverage inputs, contracts, fixtures, and choices before the first execution.

Reproduce from /Users/tong172/Desktop/projects/593-ASE:

  solutions/hw1/.venv/bin/python -B solutions/hw2/round2_stage/run_round2.py --output solutions/hw2/round2_stage/reproduced/round2-only

Every output directory must be new. The runner refuses to overwrite evidence,
write outputs inside initial_stage or round1_stage, or run with changed frozen
inputs. It verifies both protected directory inventories and their file hashes.
The recorded run exits 1 because of the known application defects; this is not
a setup failure. Do not weaken assertions or annotate those cases as expected
failures just to obtain an exit code of zero.

The recorded experiment reused the existing Python 3.11.4 environment. A fresh
environment can be installed using these commands, which were not executed
during this round:

  python3 -m venv solutions/hw2/round2_stage/.venv
  solutions/hw2/round2_stage/.venv/bin/python -m pip install -r solutions/hw2/round2_stage/requirements-test.txt

Substitute that interpreter in the run command when using the new environment.

Test provenance and changes

The six Python files originally in round1_stage/tests were copied first:
  initial_support.py and pdf_fixtures_round1.py: unchanged
  test_pdf_round1.py and test_workflows.py: unchanged
  test_components.py: one method's request assertion strengthened
  test_validation.py: three methods' state/request/result assertions strengthened

New files are tests/test_providers_round2.py (10 methods) and the HTTP/time
fixture helper tests/provider_fixtures_round2.py. The original 45 method names
are retained. No wrong expected outcome was identified or corrected. The three
known-defect methods are source-identical; their hashes are in the frozen
manifest. evidence/retained-test-changes.diff shows all changes to retained tests.

Controlled time replaces only the provider's time reference. Mocked sleep
advances virtual monotonic time without real waiting. HTTP get/post boundaries
are mocked; actual search, cache decisions, throttle logic, download loops,
XML/JSON parsing, extraction, app routes, and SQLite logic run as applicable.
Download limits are not reduced. Synthetic PDFs are generated in memory.

Fixed comparison scope

The primary comparison is these original HW2-only measurements:
  solutions/hw2/initial_stage/evidence/initial-only
  solutions/hw2/round1_stage/evidence/round1-only
  solutions/hw2/round2_stage/evidence/round2-only

Initial and round 1 measurements were reused, not rerun. Hash-identical raw
reference copies are included in evidence/initial-comparison-reference and
evidence/round1-comparison-reference. No legacy HW1 methods or older experiments
are in these suites. The round 2 runner discovers only its five test_*.py files.

All measurements use exactly these application files:
  solutions/hw1/app.py
  solutions/hw1/database.py
  solutions/hw1/pdf_tools.py
  solutions/hw1/providers.py

Coverage settings are unchanged: coverage.py 7.17.0, branch=True,
config_file=False, explicit four-file include list, no omit list, tracing before
application import. The denominator stays 522 executable statements and 174
branch destinations. Tests, templates, JavaScript/CSS, dependencies, and tooling
are not measured targets. Guarded startup inside app.py remains in scope.

Separate line/branch counts and per-module comparisons are in comparison.json
and experiment-notes.txt. The text report's Cover column mixes statements and
branch destinations and therefore differs from the line-only percentage.

Safety and preserved evidence

Dotenv is disabled before app import, inherited configuration/credentials cleared,
and only dummy keys and temporary SQLite/PDF storage used. Real HTTP/socket
connections are blocked. The recorded run had zero blocked network attempts.
No live or paid service request or personal library access was needed.

evidence/pre-round2-provenance.json protects every original file in initial_stage
and round1_stage, plus older experiment artifacts. evidence/coverage-review-input.json
records the actual feedback sources and missed paths used to guide this round.
evidence/frozen-inputs.zip and its manifest preserve code and inputs before
execution. The original run output includes unittest text, diagnostics, native
.coverage data, coverage JSON/text, HTML, and outcome events/package versions.
No test code changed after that run. The final round2-evidence.zip bundles these
including coverage files normally ignored by Git.

Only round2_stage files were created or edited. The full earlier stages and
application source were verified unchanged. No additional improvement round,
application fix, final homework report, commit, or push was performed.
