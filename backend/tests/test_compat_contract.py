"""Current checked-out contracts (never an obsolete vendored snapshot). Drift check: app/compat/schemas.py must mirror the frontend's TypeScript contract field for field.

`tests/vendored/frontend_contracts.ts` is a verbatim copy of `frontend/src/lib/contracts/index.ts` from
the checked-out frontend contract. Set COMPAT_UPSTREAM_CHECK=1 to also check against the live
`git show origin/main:frontend/src/lib/contracts/index.ts` (opt-in so a teammate's push cannot turn this
suite red without anyone touching the backend).
"""

from __future__ import annotations

import os
import re
import subprocess
import types
import typing
from pathlib import Path

import pytest

from app.compat import schemas as S

VENDORED = Path(__file__).resolve().parents[2] / "frontend" / "src" / "lib" / "contracts" / "index.ts"
UPSTREAM_PATH = "frontend/src/lib/contracts/index.ts"

_IFACE = re.compile(r"export interface (\w+) \{(.*?)\n\}", re.S)
_ALIAS = re.compile(r"export type (\w+)\s*=\s*([^;]+);")
_FIELD = re.compile(r"^\s*(\w+)(\?)?:\s*([^;]+);", re.M)
_LITERALS = re.compile(r'"([^"]+)"')


def parse_ts(text: str) -> tuple[dict[str, dict[str, tuple[bool, str]]], dict[str, set[str]]]:
    """-> ({interface: {field: (optional, type_text)}}, {alias: {string literals}})."""
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    text = re.sub(r"//[^\n]*", "", text)
    # Only a literal-union alias is an enum. Object types may contain their own literal fields.
    aliases = {name: set(_LITERALS.findall(body)) for name, body in _ALIAS.findall(text)
               if "{" not in body and "import(" not in body}
    interfaces = {name: {f: (bool(opt), t.strip()) for f, opt, t in _FIELD.findall(body)}
                  for name, body in _IFACE.findall(text)}
    return interfaces, aliases


def _unwrap(annotation):
    args = [a for a in typing.get_args(annotation) if a is not type(None)]
    origin = typing.get_origin(annotation)
    if origin in (typing.Union, types.UnionType) and len(args) == 1:
        return _unwrap(args[0])
    return annotation


def _literals(annotation) -> set[str] | None:
    a = _unwrap(annotation)
    if typing.get_origin(a) is list:  # `Integration[]` -> the element's literals
        a = _unwrap(typing.get_args(a)[0])
    if typing.get_origin(a) is typing.Literal:
        return set(typing.get_args(a))
    return None


def _check(text: str) -> list[str]:
    interfaces, aliases = parse_ts(text)
    problems: list[str] = []
    for name, lits in aliases.items():
        if lits and name in S.CONTRACT_ALIASES and set(typing.get_args(S.CONTRACT_ALIASES[name])) != lits:
            problems.append(f"type {name}: TS {sorted(lits)} != compat {sorted(typing.get_args(S.CONTRACT_ALIASES[name]))}")
    for name, fields in interfaces.items():
        model = S.CONTRACT_MODELS.get(name)
        if model is None:
            problems.append(f"interface {name} has no compat model")
            continue
        ours = model.model_fields
        for f in set(fields) - set(ours):
            problems.append(f"{name}.{f} missing in compat model")
        for f in set(ours) - set(fields):
            problems.append(f"{name}.{f} not in the TS contract")
        for f, (optional, ts_type) in fields.items():
            if f not in ours:
                continue
            if optional == ours[f].is_required():
                problems.append(f"{name}.{f}: TS optional={optional}, compat required={ours[f].is_required()}")
            ts_lits = ((set(_LITERALS.findall(ts_type)) if "import(" not in ts_type and "{" not in ts_type else set())
                       or aliases.get(ts_type.strip().removesuffix("[]"), set()))
            if ts_lits:
                mine = _literals(ours[f].annotation)
                if mine != ts_lits:
                    problems.append(f"{name}.{f}: TS literals {sorted(ts_lits)} != compat {sorted(mine or [])}")
    for name in set(S.CONTRACT_MODELS) - set(interfaces):
        problems.append(f"compat model {name} has no TS interface")
    return problems


def test_parser_sees_the_whole_contract():
    interfaces, aliases = parse_ts(VENDORED.read_text())
    assert len(interfaces) == len(S.CONTRACT_MODELS) == 18
    assert {"Unit", "CostComponent", "Provenance", "ContextKind", "ClaimType", "ProposalKind", "Integration",
            "SignalKind"} <= set(aliases)
    assert len(aliases["SignalKind"]) == 10  # a multi-line union is parsed whole
    assert interfaces["Person"]["integrations"] == (True, "Integration[]")
    assert interfaces["Forecast"]["daily"] == (True, "ForecastDailyPoint[]")
    assert interfaces["Forecast"]["low"] == (True, "number")
    assert interfaces["SpendingRecord"]["complete"] == (False, "boolean")


def test_compat_schemas_match_current_typescript_contract():
    assert _check(VENDORED.read_text()) == []


def test_drift_is_detected():
    text = VENDORED.read_text().replace("  complete: boolean;", "  complete: boolean;\n  newField: string;")
    text = text.replace('"reported_charge" | "estimate" | "usage_only"', '"reported_charge" | "estimate"')
    problems = _check(text)
    assert "SpendingRecord.newField missing in compat model" in problems
    assert any(p.startswith("type Provenance") for p in problems)
    text = VENDORED.read_text().replace('| "project_paused";', '| "project_paused"\n  | "vacation";')
    problems = _check(text)
    assert any(p.startswith("type SignalKind") for p in problems)


@pytest.mark.skipif(os.environ.get("COMPAT_UPSTREAM_CHECK") != "1", reason="opt-in: COMPAT_UPSTREAM_CHECK=1")
def test_compat_schemas_match_upstream_typescript_contract():
    repo = Path(__file__).resolve().parents[2]
    try:
        text = subprocess.run(["git", "show", f"origin/main:{UPSTREAM_PATH}"], cwd=repo, check=True,
                              capture_output=True, text=True, timeout=20).stdout
    except (OSError, subprocess.SubprocessError) as exc:
        pytest.skip(f"origin/main not available: {exc}")
    assert _check(text) == []
