#!/usr/bin/env python3
"""Run a cumulative stage with real coverage and machine-readable evidence."""
import argparse
from contextlib import ExitStack
from datetime import datetime
import hashlib
import importlib.metadata
import io
import json
import logging
import os
from pathlib import Path
import platform
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile
from zoneinfo import ZoneInfo

import coverage

ROOT = Path(__file__).resolve().parent
APP = ROOT.parent / 'hw1'
MODULES = ('app.py', 'database.py', 'pdf_tools.py', 'providers.py')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class EvidenceResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.events = []

    def addSuccess(self, test):
        super().addSuccess(test)
        self.events.append({'test': test.id(), 'outcome': 'passed'})

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self.events.append({'test': test.id(), 'outcome': 'failed', 'detail': self._exc_info_to_string(err, test)})

    def addError(self, test, err):
        super().addError(test, err)
        self.events.append({'test': test.id(), 'outcome': 'error', 'detail': self._exc_info_to_string(err, test)})

    def addSubTest(self, test, subtest, err):
        super().addSubTest(test, subtest, err)
        if err:
            self.events.append({'test': test.id(), 'subtest': str(subtest),
                'outcome': 'failed', 'detail': self._exc_info_to_string(err, test)})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', choices=('initial', 'round1', 'round2', 'legacy'), default='round2')
    parser.add_argument('--source', choices=('working', 'baseline'), default='working')
    parser.add_argument('--output', type=Path, default=ROOT / 'reproduced' / 'final')
    parser.add_argument('--html', action='store_true')
    args = parser.parse_args()
    output = args.output.resolve()
    if (output / 'results.json').exists():
        parser.error('Output already contains evidence. Use a new directory to preserve previous runs.')
    output.mkdir(parents=True, exist_ok=True)

    with ExitStack() as stack:
        if args.source == 'baseline':
            src = Path(stack.enter_context(tempfile.TemporaryDirectory(prefix='papertrail-baseline-')))
            with zipfile.ZipFile(ROOT / 'evidence' / 'baseline-source.zip') as archive:
                for name in MODULES:
                    (src / name).write_bytes(archive.read(name))
            for name in ('templates', 'static'):
                shutil.copytree(APP / name, src / name)
        else:
            src = APP
        sys.path[:0] = [str(src), str(ROOT / 'tests')]
        stack.enter_context(patch('dotenv.load_dotenv', return_value=False))
        stack.enter_context(patch.dict(os.environ, {
            'LLM_API_KEY': '', 'OPENAI_API_KEY': '', 'LLM_MODEL': 'test-model',
            'LLM_BASE_URL': 'https://provider.example.invalid/v1',
            'LLM_MAX_OUTPUT_TOKENS': '1800', 'LLM_TIMEOUT': '2',
            'LLM_REASONING_EFFORT': '', 'APP_USERNAME': '', 'APP_PASSWORD': '',
        }))
        stack.enter_context(patch('requests.sessions.Session.request',
            side_effect=AssertionError('Live network access is forbidden in the HW2 suite.')))
        errors = io.StringIO()
        handler = logging.StreamHandler(errors)
        logger = logging.getLogger('app')
        logger.addHandler(handler)
        logger.propagate = False
        stack.callback(logger.removeHandler, handler)

        cov = coverage.Coverage(branch=True, data_file=str(output / '.coverage'),
                                include=[str(src / name) for name in MODULES], config_file=False)
        cov.start()
        loader = unittest.TestLoader()
        suite = unittest.TestSuite()
        if args.stage == 'legacy':
            suite.addTests(loader.discover(str(APP / 'tests'), pattern='test_app.py'))
        else:
            stages = ['initial', 'round1', 'round2']
            for stage in stages[:stages.index(args.stage) + 1]:
                suite.addTests(loader.discover(str(ROOT / 'tests'), pattern=f'test_{stage}.py'))
        stream = io.StringIO()
        result = unittest.TextTestRunner(stream=stream, verbosity=2, resultclass=EvidenceResult).run(suite)
        cov.stop()
        cov.save()
        cov.json_report(outfile=str(output / 'coverage.json'))
        report = io.StringIO()
        cov.report(file=report, show_missing=True)
        if args.html:
            cov.html_report(directory=str(output / 'coverage-html'))
        raw = json.loads((output / 'coverage.json').read_text())
        raw['files'] = {Path(name).name: info for name, info in raw['files'].items()}
        (output / 'coverage.json').write_text(json.dumps(raw, indent=2) + '\n')
        totals = raw['totals']
        failing = {e['test'] for e in result.events if e['outcome'] in ('failed', 'error')}
        packages = {name: importlib.metadata.version(name) for name in
                    ('Flask', 'pypdf', 'requests', 'python-dotenv', 'coverage')}
        evidence = {
            'stage': args.stage, 'source': args.source,
            'timestamp': datetime.now(ZoneInfo('America/Chicago')).isoformat(),
            'python': platform.python_version(), 'packages': packages,
            'tests_run': result.testsRun, 'passed_test_methods': result.testsRun - len(failing),
            'failed_test_methods': len(failing), 'failure_events': len(result.failures),
            'errors': len(result.errors), 'skipped': len(result.skipped),
            'successful': result.wasSuccessful(),
            'line_coverage': round(100 * totals['covered_lines'] / totals['num_statements'], 2),
            'branch_coverage': round(100 * totals['covered_branches'] / totals['num_branches'], 2),
            'coverage_totals': totals,
            'source_sha256': {name: digest(src / name) for name in MODULES},
            'test_sha256': {p.name: digest(p) for p in sorted((ROOT / 'tests').glob('*.py'))},
            'network': 'Session.request blocked; provider boundaries explicitly mocked.',
            'events': result.events,
        }
        (output / 'results.json').write_text(json.dumps(evidence, indent=2) + '\n')
        (output / 'test-output.txt').write_text(stream.getvalue())
        (output / 'server-errors.txt').write_text(errors.getvalue())
        (output / 'coverage.txt').write_text(report.getvalue())
        print(stream.getvalue())
        print(report.getvalue())
        print(f"Line coverage: {evidence['line_coverage']}%; branch coverage: {evidence['branch_coverage']}%")
        print(f'Evidence: {output}')
        return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    raise SystemExit(main())
