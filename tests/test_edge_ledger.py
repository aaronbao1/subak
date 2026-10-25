"""Audit metadata integrity only; these tests do not certify domain coverage."""
import ast
import json
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


def ledger():
    return json.loads((ROOT / 'docs/implementation/edge-ledger.json').read_text())


def test_ledger_has_every_original_edge_once_with_unchanged_assertion():
    original = {}
    for path in (ROOT / 'docs/forecasting-research/edges').glob('*.json'):
        for case in json.loads(path.read_text()):
            assert case['id'] not in original
            original[case['id']] = case
    cases = ledger()['cases']
    assert len(cases) == len({case['id'] for case in cases}) == len(original) == 206
    assert {case['id'] for case in cases} == set(original)
    for case in cases:
        assert case['required_assertion'] == original[case['id']]['test_assertion']
        assert case['source_residual_limit'] == original[case['id']]['residual_limit']
        assert case['classification'] in ledger()['classification_definitions']
        assert case['remaining_limitation'] and case['capability_scope']


def test_ledger_references_real_tests_and_separates_pending_evidence():
    reports = {}
    for case in ledger()['cases']:
        for evidence in case['evidence']:
            path = ROOT / evidence['path']
            assert path.is_file(), (case['id'], path)
            functions = {node.name for node in ast.walk(ast.parse(path.read_text()))
                         if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
            assert evidence['function'] in functions, (case['id'], evidence)
            assert evidence['function'].startswith('test_')
            assert evidence['asserted_scope']
            assert evidence['path'] != 'tests/test_edge_ledger.py', 'metadata checks are not domain evidence'
        if case['classification'] in {'core_handled_tested', 'optional_unsupported_tested'}:
            assert case['evidence'], case['id']
            assert case['verification']['status'] == 'passed', case['id']
            assert case['verification']['command'] and case['verification']['result']
            report_path = case['verification']['report']
            if report_path not in reports:
                executed = {}
                for test in ET.parse(ROOT / report_path).getroot().iter('testcase'):
                    key = (test.attrib['classname'].replace('.', '/') + '.py',
                           test.attrib['name'].split('[')[0])
                    executed.setdefault(key, []).append(
                        all(test.find(tag) is None for tag in ('failure', 'error', 'skipped')))
                reports[report_path] = executed
            for evidence in case['evidence']:
                outcomes = reports[report_path].get((evidence['path'], evidence['function']))
                assert outcomes and all(outcomes), (case['id'], evidence)
        if case['classification'] == 'research_only_empirical_pending':
            assert case['verification']['status'] == 'empirical_pending'


def test_requirement_ledger_mentions_all_thirty_requirements():
    text = (ROOT / 'docs/implementation/requirements-and-capabilities.md').read_text()
    for number in range(1, 31):
        assert f'01-R{number:02}' in text
