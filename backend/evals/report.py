"""Write eval results: `results/<runner>.json` (machine-readable) and `results/<runner>.md` (summary)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from evals.harness import SuiteResult
from evals.scenarios import RunCtx


def fixture_dict(ctx: RunCtx) -> dict[str, Any]:
    run = ctx.run
    out = run.get("output") or {}
    usage = out.get("usage") or {}
    return {
        "fixture": ctx.fixture, "ran": ctx.ran, "skip_reason": ctx.skip_reason, "error": ctx.error,
        "http_status": ctx.http_status, "request": ctx.request, "setup": ctx.setup,
        "run_id": run.get("id"), "runner_kind": run.get("runner_kind"), "status": run.get("status"),
        "run_error": (run.get("error") or "")[:1000] or None,
        "duration_s": ctx.duration_s,
        "tools_called": ctx.tools_called(),
        "warning_codes": sorted(ctx.warning_codes()),
        "warnings": [{k: (str(v)[:300] if isinstance(v, str) else v) for k, v in (e.get("data") or {}).items()
                      if k in ("code", "tool", "message")}
                     for e in run.get("events", []) if e.get("type") in ("warning", "error")][:20],
        "signals": [{"id": s["id"], "team": s.get("team"), "status": s["status"], "change_type": s.get("change_type"),
                     "cites": sorted({f"{c['doc_key']}@v{c['version']}" for c in s.get("citations", [])})}
                    for s in ctx.run_signals()],
        "proposals": [{"id": p["id"], "action_type": p["action_type"], "status": p["status"],
                       "base_version": p["base_version"], "envelope_increase": p.get("envelope_increase"),
                       "after": p["after"], "rebased_from_proposal_id": p.get("rebased_from_proposal_id")}
                      for p in ctx.proposals],
        "budget_version": {"before": ctx.budget_before.get("state_version"),
                           "after": ctx.budget_after.get("state_version")},
        "summary": (run.get("summary") or "")[:6000] or None,
        "usage": {"provider_reported": usage.get("provider_reported"), "subtype": usage.get("subtype"),
                  "duration_s": usage.get("duration_s"),
                  "permission_allowed": usage.get("permission_allowed"),
                  "permission_cancelled": usage.get("permission_cancelled")} if usage else None,
    }


def result_dict(res: SuiteResult) -> dict[str, Any]:
    return {
        "runner": res.runner, "generated_at": res.generated_at, "counts": res.counts,
        "live_runs_used": res.live_runs_used, "live_log_total": res.live_log_total, "notes": res.notes,
        "scenarios": res.scenarios,
        "fixtures": {n: fixture_dict(c) for n, c in res.fixtures.items()},
    }


def markdown(res: SuiteResult) -> str:
    c = res.counts
    lines = [f"# Droid eval results: `{res.runner}` runner", "",
             f"Generated {res.generated_at} by `python -m evals.run --runner {res.runner}`. "
             f"Answer key: [`../answer_key.md`](../answer_key.md).", "",
             f"**{c['pass']} pass, {c['fail']} fail, {c['not_run']} not run** "
             f"(of {len(res.scenarios)} scenarios).", ""]
    if res.runner == "sdk":
        lines += [f"Live Droid runs used by this invocation: {res.live_runs_used}. "
                  f"Total lines in `backend/data/live_runs.log` afterwards: {res.live_log_total}.", ""]
    else:
        lines += ["FakeDroidRunner is a deterministic scripted playbook, not a model: passing here shows the "
                  "harness, the backend guards and the reference behaviour agree, not that a model behaves.", ""]
    for n in res.notes:
        lines += [f"- {n}"]
    if res.notes:
        lines.append("")
    lines += ["| Scenario | Result | Fixture(s) | Reasons |", "|---|---|---|---|"]
    for s in res.scenarios:
        reasons = "<br>".join(r.replace("|", "\\|") for r in s["reasons"])[:900]
        lines.append(f"| `{s['id']}` {s['title']} | **{s['status']}** | {', '.join(s['fixtures'])} | {reasons} |")
    lines += ["", "## Runs", "", "| Fixture | Run | Status | Duration | Tools | Drafts | Signals | Credits |",
              "|---|---|---|---|---|---|---|---|"]
    for name, ctx in res.fixtures.items():
        f = fixture_dict(ctx)
        if not ctx.ran:
            lines.append(f"| {name} | - | not run: {ctx.skip_reason or ctx.error} | - | - | - | - | - |")
            continue
        credits = ((f["usage"] or {}).get("provider_reported") or {}).get("factory_credits", "-") if f["usage"] else "-"
        drafts = ", ".join(f"{p['action_type']} {p['status']}" for p in f["proposals"]) or "none"
        lines.append(f"| {name} | `{f['run_id']}` | {f['status']} | {f['duration_s']} s | {len(f['tools_called'])} | "
                     f"{drafts} | {len(f['signals'])} | {credits} |")
    lines += ["", "## Check detail", ""]
    for s in res.scenarios:
        lines.append(f"### `{s['id']}`: {s['status']}")
        if s.get("note"):
            lines.append(f"_{s['note']}_")
        for chk in s["checks"]:
            mark = "pass" if chk["passed"] else "FAIL"
            lines.append(f"- {mark} `{chk['name']}`: {chk['reason']}")
        if not s["checks"]:
            lines += [f"- {r}" for r in s["reasons"]]
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write(res: SuiteResult, out_dir: Path, *, stem: str | None = None) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = stem or res.runner
    jp, mp = out_dir / f"{stem}.json", out_dir / f"{stem}.md"
    jp.write_text(json.dumps(result_dict(res), indent=2, default=str) + "\n", encoding="utf-8")
    mp.write_text(markdown(res), encoding="utf-8")
    return jp, mp
