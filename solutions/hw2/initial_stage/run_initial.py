#!/usr/bin/env python3
"""Run only the frozen initial-stage experiment and save actual evidence.

Examples from the repository root:
  solutions/hw1/.venv/bin/python -B solutions/hw2/initial_stage/run_initial.py \
      --suite initial --output solutions/hw2/initial_stage/reproduced/initial-1

There are no improvement-round modes. Every output directory must be new.
"""
import argparse
from contextlib import ExitStack, redirect_stderr, redirect_stdout
from datetime import datetime
import hashlib
import importlib.metadata
import io
import json
import logging
import os
from pathlib import Path
import platform
import sys
import tempfile
import unittest
from unittest.mock import patch
from zoneinfo import ZoneInfo

import coverage

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[2]
APP = REPO / 'solutions' / 'hw1'
MODULES = ('app.py', 'database.py', 'pdf_tools.py', 'providers.py')
INITIAL_FILES = ('initial_support.py', 'test_components.py', 'test_validation.py', 'test_workflows.py')


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_frozen():
    manifest = json.loads((ROOT / 'evidence' / 'frozen-manifest.json').read_text())
    mismatches = [name for name, expected in manifest['frozen_inputs'].items()
                  if not (REPO / name).is_file() or sha256(REPO / name) != expected]
    if mismatches:
        raise RuntimeError('Frozen inputs changed: ' + ', '.join(mismatches))
    return manifest


def test_ids(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from test_ids(item)
        else:
            yield item.id()


class EvidenceResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.events = []

    def addSuccess(self, test):
        super().addSuccess(test)
        self.events.append({'test': test.id(), 'outcome': 'passed'})

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self.events.append({'test': test.id(), 'outcome': 'failed',
                            'traceback': self._exc_info_to_string(err, test)})

    def addError(self, test, err):
        super().addError(test, err)
        self.events.append({'test': test.id(), 'outcome': 'error',
                            'traceback': self._exc_info_to_string(err, test)})

    def addSubTest(self, test, subtest, err):
        super().addSubTest(test, subtest, err)
        event = {'test': test.id(), 'subtest': str(subtest),
                 'outcome': 'passed_subtest' if err is None else 'failed_subtest'}
        if err is not None:
            event['traceback'] = self._exc_info_to_string(err, test)
        self.events.append(event)

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self.events.append({'test': test.id(), 'outcome': 'skipped', 'reason': reason})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--suite', choices=('legacy', 'initial', 'combined'), required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    manifest = check_frozen()
    output = args.output.resolve()
    if output.exists():
        parser.error('Evidence is never overwritten. Choose a new output directory.')
    output.mkdir(parents=True)

    network_attempts = []

    def forbid_http(*request_args, **kwargs):
        network_attempts.append({'boundary': 'requests.Session.request'})
        raise AssertionError('Live HTTP requests are forbidden in this experiment')

    forbid_http._papertrail_initial_guard = True

    def forbid_socket(*request_args, **kwargs):
        network_attempts.append({'boundary': 'socket connection'})
        raise AssertionError('Live socket connections are forbidden in this experiment')

    selected_suites = []
    started = datetime.now(ZoneInfo('America/Chicago')).isoformat()
    stream, diagnostics = io.StringIO(), io.StringIO()
    with ExitStack() as stack:
        temporary = stack.enter_context(tempfile.TemporaryDirectory(prefix='papertrail-run-'))
        stack.enter_context(patch.dict(os.environ, {
            'PATH': os.environ.get('PATH', ''), 'DATA_DIR': temporary,
            'LLM_API_KEY': '', 'OPENAI_API_KEY': '', 'LLM_MODEL': 'unit-test-model',
            'LLM_BASE_URL': 'https://llm.example.invalid/v1',
            'LLM_MAX_OUTPUT_TOKENS': '1800', 'LLM_TIMEOUT': '2',
            'LLM_REASONING_EFFORT': '', 'APP_USERNAME': '', 'APP_PASSWORD': '',
            'PYTHONDONTWRITEBYTECODE': '1',
        }, clear=True))
        stack.enter_context(patch('dotenv.load_dotenv', return_value=False))
        stack.enter_context(patch('requests.sessions.Session.request', new=forbid_http))
        stack.enter_context(patch('socket.socket.connect', new=forbid_socket))
        stack.enter_context(patch('socket.socket.connect_ex', new=forbid_socket))
        stack.enter_context(patch('socket.create_connection', new=forbid_socket))
        root_logger = logging.getLogger()
        old_handlers, old_level = root_logger.handlers[:], root_logger.level
        root_logger.handlers = [logging.StreamHandler(diagnostics)]
        root_logger.setLevel(logging.WARNING)
        stack.callback(setattr, root_logger, 'handlers', old_handlers)
        stack.callback(root_logger.setLevel, old_level)
        sys.path[:0] = [str(APP), str(ROOT / 'tests')]

        cov = coverage.Coverage(
            branch=True, config_file=False, data_file=str(output / '.coverage'),
            include=[str(APP / module) for module in MODULES],
        )
        with redirect_stderr(diagnostics), redirect_stdout(diagnostics):
            cov.start()
            suite = unittest.TestSuite()
            if args.suite in ('legacy', 'combined'):
                suite.addTests(unittest.TestLoader().discover(str(APP / 'tests'), pattern='test_app.py'))
                selected_suites.append('solutions/hw1/tests/test_app.py')
            if args.suite in ('initial', 'combined'):
                suite.addTests(unittest.TestLoader().discover(str(ROOT / 'tests'), pattern='test_*.py'))
                selected_suites.extend('solutions/hw2/initial_stage/tests/' + filename
                                       for filename in INITIAL_FILES if filename.startswith('test_'))
            discovered_ids = list(test_ids(suite))
            result = unittest.TextTestRunner(
                stream=stream, verbosity=2, resultclass=EvidenceResult,
            ).run(suite)
            cov.stop()
            cov.save()
        cov.json_report(outfile=str(output / 'coverage.json'))
        report = io.StringIO()
        cov.report(file=report, show_missing=True)
        cov.html_report(directory=str(output / 'coverage-html'))
        raw = json.loads((output / 'coverage.json').read_text())
        totals = raw['totals']
        failed_methods = {event['test'] for event in result.events
                          if event['outcome'] in ('failed', 'error', 'failed_subtest')}
        passed_methods = {event['test'] for event in result.events if event['outcome'] == 'passed'}
        check_frozen()
        scope = ['solutions/hw1/' + name for name in MODULES]
        evidence = {
            'stage': 'initial generation and evaluation only', 'suite': args.suite,
            'started_at': started,
            'finished_at': datetime.now(ZoneInfo('America/Chicago')).isoformat(),
            'command_arguments': sys.argv, 'working_directory': str(Path.cwd()),
            'python': platform.python_version(), 'python_executable': sys.executable,
            'packages': {name: importlib.metadata.version(name) for name in (
                'Flask', 'pypdf', 'requests', 'python-dotenv', 'gunicorn', 'coverage',
            )},
            'measured_application_files': scope,
            'included_test_files': selected_suites,
            'excluded_tests': ['solutions/hw2/tests/test_initial.py',
                               'solutions/hw2/tests/test_round1.py'],
            'coverage_configuration': {'branch': True, 'config_file': False,
                                       'include': scope, 'omit': []},
            'tests_run': result.testsRun, 'discovered_test_ids': discovered_ids,
            'passed_test_methods': len(passed_methods),
            'failed_test_methods': len(failed_methods),
            'failure_events': len(result.failures), 'error_events': len(result.errors),
            'skipped': len(result.skipped), 'successful': result.wasSuccessful(),
            'line_coverage_percent': 100 * totals['covered_lines'] / totals['num_statements'],
            'branch_coverage_percent': 100 * totals['covered_branches'] / totals['num_branches'],
            'coverage_py_combined_percent': totals['percent_covered'],
            'coverage_totals': totals,
            'source_sha256': {name: manifest['frozen_inputs'][name] for name in scope},
            'frozen_manifest_sha256': sha256(ROOT / 'evidence' / 'frozen-manifest.json'),
            'frozen_inputs_verified_after_run': True,
            'network_attempts': network_attempts,
            'isolation': 'dotenv disabled; environment cleared; temporary SQLite/PDF storage; '
                         'dummy credentials only; Session.request and socket connections blocked',
            'events': result.events,
        }
        (output / 'results.json').write_text(json.dumps(evidence, indent=2) + '\n')
        (output / 'test-output.txt').write_text(stream.getvalue())
        (output / 'diagnostics.txt').write_text(diagnostics.getvalue())
        (output / 'coverage.txt').write_text(report.getvalue())
    print(stream.getvalue())
    print(report.getvalue())
    print(f"Lines: {totals['covered_lines']}/{totals['num_statements']} "
          f"({evidence['line_coverage_percent']:.2f}%)")
    print(f"Branches: {totals['covered_branches']}/{totals['num_branches']} "
          f"({evidence['branch_coverage_percent']:.2f}%)")
    print(f'Evidence: {output}')
    return 0 if result.wasSuccessful() and not network_attempts else 1


if __name__ == '__main__':
    raise SystemExit(main())
