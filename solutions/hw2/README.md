# Homework 2: Test Generation and Improvement Using Coding Agents

This submission evaluates Codex-generated tests for the Papertrail application from Homework 1. It includes initial generation, two separately guided improvement rounds, conversation records, coverage measurements, and the final report.

- [Final PDF report](docs/hw2-report.pdf)
- [Editable LaTeX source](docs/overleaf-report.tex)
- [Overleaf project](https://www.overleaf.com/project/6ac7d8e49907ab7405d67d38)
- [Final test suite](round2_stage/tests/)
- [Final evaluation notes](round2_stage/experiment-notes.txt)
- [Three-stage machine-readable comparison](round2_stage/evidence/comparison.json)

## Recorded results

All rows measure the same application snapshot and the same four Python modules: `app.py`, `database.py`, `pdf_tools.py`, and `providers.py`. Each comparison excludes the 14 legacy Homework 1 tests and older experiments.

| HW2-only suite | Test methods | Passed | Failed methods | Failure events | Line coverage | Branch coverage |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Initial | 37 | 35 | 2 | 3 | 474/522 (90.80%) | 135/174 (77.59%) |
| Round 1 | 45 | 42 | 3 | 4 | 505/522 (96.74%) | 151/174 (86.78%) |
| Round 2, final | 55 | 52 | 3 | 4 | 514/522 (98.47%) | 160/174 (91.95%) |

Every recorded suite has zero test errors and zero skips. Round 1 adds eight PDF-focused methods. Round 2 adds ten provider methods and strengthens four retained methods.

The final suite returns **exit code 1** because it continues to expose three application defects:

1. Analysis `kind=[]` and `kind={}` return HTTP 500 instead of a validation 400. These are two failing subcases with one root cause.
2. Search `page=²` returns HTTP 500 instead of a validation 400.
3. A continuation of a two-line PDF title is persisted as an extra author.

The application was kept unchanged during the test-quality comparison. The report explains each defect, its detecting test, and the distinction between three failed methods and four failure events. No known failure is skipped or marked as an expected failure.

## Install dependencies

Run the following POSIX-shell commands from the repository root with Python 3.11 or newer:

```bash
python3 -m venv /tmp/papertrail-hw2-venv
TASK_PY=/tmp/papertrail-hw2-venv/bin/python
"$TASK_PY" -m pip install -r solutions/hw2/round2_stage/requirements-test.txt
```

The recorded runs used Python 3.11.4 and coverage.py 7.17.0. Application dependencies are pinned in `solutions/hw1/requirements.txt`.

## Run the final tests and reproduce coverage

Use a new output directory for each run:

```bash
"$TASK_PY" -B solutions/hw2/round2_stage/run_round2.py \
  --output /tmp/papertrail-hw2-final-run
```

The runner writes:

- `results.json`: method outcomes, failure events, versions, coverage counts, and source hashes.
- `test-output.txt` and `diagnostics.txt`: actual assertions and application diagnostics.
- `coverage.json` and `coverage.txt`: machine-readable and text coverage.
- `.coverage` and `coverage-html/index.html`: native data and browsable coverage.

The text report's `Cover` column combines line and branch metrics. Use the separate line/branch counts in `results.json` or `coverage.json` when comparing with the table above.

The runner uses temporary SQLite/PDF storage, dummy credentials, disabled dotenv loading, mocked external services, and blocked live connections. No model key, paid request, or personal library is needed.

## Frozen evidence and repository contents

The final runner verifies source hashes and the complete inventories of earlier stages. This repository therefore includes the normally ignored native coverage and HTML evidence needed by those checks. Keep the frozen stage files intact and place virtual environments and new run outputs outside the earlier stage directories.

| Directory | Role |
| --- | --- |
| `initial_stage/` | The initial 37-method HW2 suite, actual initial request, execution results, and frozen evidence. |
| `round1_stage/` | The 45-method PDF-focused improvement, recorded feedback, results, and evidence. |
| `round2_stage/` | The final 55-method suite, recorded feedback, strengthened assertions, results, and evidence. |
| `docs/` | Final PDF report and the Overleaf-compatible LaTeX source. |
| `tests/`, `evidence/`, and `run_experiment.py` at this directory's top level | Earlier artifacts excluded from the reported experiment; retained because the frozen manifests protect them. |

Each stage includes `README.txt`, experiment notes, its original raw run outputs, integrity records, and a ZIP evidence bundle. The exact test changes from round 1 to round 2 are in [retained-test-changes.diff](round2_stage/evidence/retained-test-changes.diff).

The final report also provides a code-only `unittest`/coverage recipe for running the tests without historical-inventory checks.

## Scope

These measurements cover the Python backend. They do not establish browser behavior, accessibility, real provider availability, or actual LLM answer quality. The report discusses these limitations and the lack of a mutation-testing experiment.
