"""The live SDK tool advertises and enforces the backend's signal input contract; no sessions."""
import asyncio
import json
from typing import get_args

import pytest
from pydantic import ValidationError

from app.agent.tools import TOOLS
from app.schemas.signals import ChangeType, CitationIn, SignalScope, SignalStatus
from northstar_droid.sdk_tools import tool_functions


def _tool(toolbox):
    sdk_mcp = pytest.importorskip('droid_sdk.mcp')
    name, description, function = next(item for item in tool_functions(toolbox) if item[0] == 'record_signal')
    return sdk_mcp.tool(name, description)(function)


def test_sdk_signal_schema_preserves_backend_enums_and_citation_fields():
    tool = _tool(object())
    schema = tool.input_schema
    props = schema['properties']
    assert list(props['change_type']['enum']) == list(get_args(ChangeType))
    assert list(props['status']['enum']) == list(get_args(SignalStatus))
    assert list(props['scope']['enum']) == list(get_args(SignalScope))
    citation_ref = props['citations']['items']['$ref'].split('/')[-1]
    citation = schema['$defs'][citation_ref]
    assert set(citation['properties']) == set(CitationIn.model_fields)
    assert citation['additionalProperties'] is False
    assert list(citation['required']) == ['document_id', 'quote']
    description = next(item.description for item in TOOLS if item.name == 'record_signal')
    assert all(value in description for value in get_args(ChangeType))
    assert 'version' in description and 'response-only' in description


@pytest.mark.parametrize('invalid', [
    {'change_type': 'decrease'},
    {'change_type': 'increase'},
    {'citations': [{'document_id': 'document-1', 'quote': 'Exact source wording.', 'version': 1}]},
])
def test_sdk_signal_rejects_invalid_contract_before_backend_write(invalid):
    class MustNotRun:
        def call(self, *args, **kwargs):
            pytest.fail('invalid SDK arguments reached the backend')
    tool = _tool(MustNotRun())
    args = {'summary': 'Reduced workload.', 'change_type': 'reduction', 'status': 'current',
            'uncertainty': 'Exact usage remains unknown.', 'team': 'research',
            'citations': [{'document_id': 'document-1', 'quote': 'Exact source wording.'}], **invalid}
    with pytest.raises(ValidationError):
        asyncio.run(tool.handler(args))


def test_sdk_signal_valid_citation_round_trips_through_real_toolbox(seeded):
    from test_agent import _toolbox
    tools = _toolbox(seeded)
    doc = next(item for item in tools.search_corpus('')['items'] if item['doc_key'] == 'research-eval-plan')
    source = tools.read_document(doc['id'])
    quote = 'This plan expands model-evaluation work during the current planning period.'
    assert quote in source['content']
    output = json.loads(asyncio.run(_tool(tools).handler({
        'summary': 'Research evaluation expands.', 'change_type': 'expansion', 'status': 'current',
        'uncertainty': 'Exact token volumes are unknown.', 'team': 'research',
        'citations': [{'document_id': source['id'], 'quote': quote}],
    })))
    assert output['change_type'] == 'expansion'
    assert output['citations'][0]['document_id'] == source['id']
    assert output['citations'][0]['version'] == source['version']
    assert output['citations'][0]['quote'] == quote
