# Forecast browser acceptance journey

The FP&A redesign was exercised in a local browser on October 25, 2026, using both the synthetic mock and an isolated FastAPI/SQLite backend with the deterministic fake Droid runner. The current validation record below supersedes the original sandbox limitation. The older publication-transition procedure remains below for reproducing those specific checks.

Use a normal local environment with the repository's Python and frontend dependencies installed. Use the real pinned frontend dependencies for visual acceptance. The cached compatibility webpack build described in the implementation verification notes does not establish Tailwind or font styling parity.


## October 25 FP&A redesign validation

The new Overview leads with matching-period spending, budget, expected spend and remaining budget. It shows one primary chart and a compact priority list. Sources, numerical assumptions, exact chart values and full proposal explanations are disclosed on request. Ramp’s official reporting and budgets layouts informed the outlined workspace structure; the implementation uses independent dark neutrals and a blue accent.

Local previews:
- `http://127.0.0.1:3000/overview`: deterministic Northstar mock. Recorded billable spend $95,000, weekly budget $200,000, issued weekly forecast $200,000. Included usage is not counted again. Mock scenarios deliberately have no fabricated modeled drivers or confidence intervals.
- `http://127.0.0.1:3001/overview`: production build connected to `http://127.0.0.1:8789/compat`, an isolated synthetic ledger with an engine-issued forecast and five supported drivers. `NEXT_PUBLIC_DEMO_MODE=true` labels the fixture and scripted assistant. No live Factory call, production data migration or deployment was made.

Executed browser journey (Codex in-app browser):
1. Read company summary, search Teams, open Research and Maya; inspect the same issued scope/period and current ledger totals.
2. Open Planning, select a project schedule, resolve “two weeks later” to November 16, and preview a separate scenario. The issued total and budget remain unchanged; moving the same work within the quarter correctly has zero quarter-total change while daily timing changes.
3. Open Usage, switch Spend/Tokens, select October 24 (350 tokens = 300 input + 50 output), then use ArrowDown and Enter for October 25 (recorded zero). Cached input 230 and reasoning 25 remain subsets. Unknown telemetry is shown as unavailable. Company observed spend is $558.29 in this small engine fixture.
4. Ask for $50 new funding, answer the team clarification, review exact amounts, use Revise to change the selected draft to $40, and apply only inside the isolated synthetic database. The receipt shows Research $60,000 → $60,040 and company envelope $200,000 → $200,040. Find the receipt in Decisions and filter by Applied/Research.
5. Search Evidence, expand Sources, open the approved research source, and return to the preserved search context.
6. Draft an explicit $50 Product → Research transfer: both lines retain the requested amount and the company envelope stays unchanged. After a reviewed draft is applied, a complete new request starts a fresh draft; amount-only revisions still require an open selection.
7. Inspect 1440px desktop, 1024px laptop and 390px phone layouts. The phone summary uses two columns, all money values fit, and the page has no horizontal overflow. Mobile navigation reaches all six destinations; daily usage selection is keyboard operable.

Final verification: the full backend run passed **999 tests**, with one opt-in upstream contract check skipped; the later closed-selection regressions passed in a focused **143-test** backend run. All **154 frontend tests** passed. The real backend integration passed, and ESLint, TypeScript, contract-export determinism, whitespace checks and the pinned production build passed. Logs are `backend-tests-final.log`, `intent-closed-selection-tests.log`, `frontend-tests-final.log`, `integration-root-final.log` and `production-build-final.log` in the evidence directory. The final preview uses a fresh fixture database, separate from the database used for approval tests.

Automated coverage includes exact target compatibility, all native provenance kinds, excluded informational/unpriced usage, UTC boundaries, missing/zero/partial/corrected usage, scope conservation, selected-draft semantics, negation and exact small amounts, immutable scenario parents, receipt-first save behavior, refresh failure, request deduplication, lost responses and interrupted acceptance. The real TypeScript client/store → FastAPI → SQLite → forecast worker → deterministic Droid integration is executable with:

```bash
FORECAST_TEST_PYTHON=.venv/bin/python node --test frontend/tests/forecast-backend.integration.mjs
```

Detailed test logs, screenshots and the isolated demo launcher are in `.coordination/fpna-redesign-20261025/evidence/`. Independent review findings and fix verification are in `.coordination/fpna-redesign-20261025/agents/independent-review.md`.

Limits: live Factory/SDK validation and sessions with nontechnical finance participants were not performed. Demo identity headers are not production authentication. Native agent work interrupted after execution starts retains the existing server recovery semantics; an unknown outcome is shown for reconciliation, not automatically resent. The new usage API does not invent source completeness receipts. These checks establish functional demo behavior, not forecasting accuracy or production readiness.

## Start an isolated, deterministic fixture

All commands start at the repository root. This fixture uses a new database, a frozen Monday noon UTC clock, deterministic synthetic history, and the fake Droid runner. It calls no live connectors or live model service. It deliberately starts with no connector drivers so that the queued-versus-included transition is observable. Leave normal user databases alone.

In terminal 1:

```bash
export FORECAST_JOURNEY_DIR="$(mktemp -d /tmp/forecast-browser-journey.XXXXXX)"
export PYTHONPATH="$PWD/src:$PWD/backend:$PWD/agent"
export FORECAST_JOURNEY_PYTHON="$PWD/backend/.venv/bin/python"
printf 'Artifact directory: %s\n' "$FORECAST_JOURNEY_DIR"
cat > "$FORECAST_JOURNEY_DIR/serve.py" <<'PY'
from datetime import datetime, timezone
from pathlib import Path
import os
import uvicorn
from app.config import Settings
from app.core.clock import FrozenClock, UuidIdFactory
from app.main import create_app
from app.seed.northstar import seed
from app.forecasting.fixtures import build_northstar_snapshot

clock = FrozenClock(datetime(2026, 10, 26, 12, tzinfo=timezone.utc))
settings = Settings(
    db_path=Path(os.environ['FORECAST_JOURNEY_DIR']) / 'app.db',
    forecast_provider='engine', forecast_demo=True, forecast_worker=True,
    droid_runner='fake',
)
app = create_app(settings, clock=clock, id_factory=UuidIdFactory())
def observed_inputs(*, now, tenant_id='northstar'):
    snapshot = build_northstar_snapshot(now=now, tenant_id=tenant_id)
    snapshot['drivers'] = []
    snapshot['evidence'] = []
    return snapshot
app.state.forecast_service.snapshot_factory = observed_inputs
with app.state.session_factory() as session:
    seed(session, clock=clock, ids=app.state.id_factory, include_spend=False)
    session.commit()
# Finish the one idempotent weekly job before the browser creates its manual baseline.
weekly = app.state.forecast_service.schedule_due()
app.state.forecast_worker.process_one(job_id=weekly['id'])
uvicorn.run(app, host='127.0.0.1', port=8787)
PY
"$FORECAST_JOURNEY_PYTHON" "$FORECAST_JOURNEY_DIR/serve.py"
```

In terminal 2, set `FORECAST_JOURNEY_DIR` to the exact directory printed above, and export the same `PYTHONPATH` and `FORECAST_JOURNEY_PYTHON`. Then start the frontend from its directory:

```bash
cd frontend
NEXT_PUBLIC_API_URL=http://127.0.0.1:8787/compat npm run dev -- --hostname 127.0.0.1
```

The `/compat` prefix is required for the existing company, people, budgets and chat endpoints. Canonical forecasting routes are also mounted under that prefix. Do not use mock mode for this backend integration journey. The mock is an intentionally simpler constant-rate UI illustration.

In terminal 3, export the three fixture environment variables as in terminal 1. Create these reusable API helpers:

```bash
cat > "$FORECAST_JOURNEY_DIR/check.py" <<'PY'
import json, os, time
from pathlib import Path
from urllib.request import Request, urlopen
ARTIFACTS = Path(os.environ['FORECAST_JOURNEY_DIR'])
BASE = 'http://127.0.0.1:8787'
def request(path, body=None, headers=None):
    data = None if body is None else json.dumps(body).encode()
    req = Request(BASE + path, data=data, headers={'Content-Type':'application/json', **(headers or {})})
    with urlopen(req, timeout=180) as response:
        return json.load(response)
def save(name, value):
    (ARTIFACTS / name).write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')
def load(name):
    return json.loads((ARTIFACTS / name).read_text())
def wait_job(job_id):
    for _ in range(300):
        job = request('/api/forecast-refreshes/' + job_id)
        if job['status'] == 'succeeded': return job
        if job['status'] == 'failed': raise RuntimeError(job)
        time.sleep(.2)
    raise TimeoutError('Job still queued/running: ' + job_id)
if __name__ == '__main__':
    job = request('/api/forecast-refreshes', {}, {'Idempotency-Key':'browser-journey-baseline'})
    wait_job(job['id'])
    baseline = request('/api/forecast-views')
    save('baseline.json', baseline)
    company = next(v for v in baseline['views'] if v['scope']['type'] == 'company')
    assert not company['included_drivers']
    print('Baseline issued run:', company['run_id'])
PY
"$FORECAST_JOURNEY_PYTHON" "$FORECAST_JOURNEY_DIR/check.py"
```

## Browser checkpoints

Open `http://127.0.0.1:3000/overview`. Keep DevTools Network open with requests preserved. Save screenshots into the fixture artifact directory and record the browser/version, viewport and commit in `browser-result.md`. A failure should include its request/response and console error; do not record a checkpoint as passed merely because the corresponding API check passed.

| Checkpoint | Browser action | Required observation |
| --- | --- | --- |
| Company / issued identity | Inspect **Company forecast** and compare its run ID to `baseline.json`. | Synthetic label, UTC issuance/cutoff, four-week subtotal, separate conditional quarter, explicit shared residuals. An unavailable quarter or incomplete late component remains unavailable. |
| Seven daily details | Leave **7 daily** selected. | Exactly seven daily rows from the publication's forecast start, not seven newly computed browser days. Null bounds remain **Unavailable**. |
| Partial four-week horizon | Select **4 weekly**. | Four buckets. The first begins at the manual run's next UTC day and ends on Monday; it is marked partial. No pre-origin prefix is called forecast spend. Dates show end-exclusive convention. |
| Cumulative fan | Switch **Scenario envelope**, then **Historical error**. | Base line is from the same issued paths. Descriptive scenario bounds are not labeled confidence or coverage. Historical intervals remain separate, default 80%, optional 95%, with sample/rank/date/qualification metadata or an explicit unavailable state. A partial scenario envelope is identified as conditional on base rates. |
| Team | Open Product through its forecast reconciliation link (or `/teams/product`). | Team run ID equals the company run. Its canonical daily/week/quarter numbers match the corresponding Product view in `baseline.json`. |
| Person | Open Owen Park from Product's people table (`/teams/product/people/owen`). | Person run ID equals the company/team run. Its canonical values match the Owen view. Shared residuals are not assigned to this person. |

Suggested screenshot names: `01-company.png`, `02-weekly.png`, `03-historical-error.png`, `04-team.png`, `05-person.png`.

## Deliver evidence; verify the issued run does not change

In terminal 3, ingest the checked-in synthetic connector envelopes and verify the immutable baseline before touching Refresh:

```bash
cat > "$FORECAST_JOURNEY_DIR/queue.py" <<'PY'
from check import request, save, load, wait_job
from app.forecasting.fixtures import northstar_evidence
baseline = load('baseline.json')
run = next(v for v in baseline['views'] if v['scope']['type'] == 'company')['run_id']
receipts = []
for envelope in northstar_evidence():
    receipt = request('/api/forecast-evidence', envelope)
    if receipt.get('status') != 'succeeded':
        wait_job(receipt['interpretation_job_id'])
    receipts.append(receipt)
save('evidence-receipts.json', receipts)
current = request('/api/forecast-views')
assert current['views'] == baseline['views'], 'Evidence ingestion changed an issued view'
assert request('/api/forecast-views?run_id=' + run)['views'] == baseline['views']
save('queued-evidence.json', request('/api/forecast-evidence'))
print('Evidence delivered; issued views unchanged:', run)
PY
"$FORECAST_JOURNEY_PYTHON" "$FORECAST_JOURNEY_DIR/queue.py"
```

Reload the overview to fetch evidence metadata. The run and all issued path numbers must still match `baseline.json`. The evidence list should show supported changes as **Queued**, and the release-only/ambiguous material as **Context only**. Neither state is **Included** in the old run. Open one queued item and confirm the exact source passage/revision/effective dates and numerical parameters; an uncomputed effect must not become a guessed amount. Save `06-queued-old-run.png`.

Click **Refresh forecast** once. The job status should become queued/running/succeeded as applicable; fast completion need not visibly render every intermediate state. The issued panel remains visible while waiting. Once succeeded, record the new run, then execute:

```bash
cat > "$FORECAST_JOURNEY_DIR/after-refresh.py" <<'PY'
from check import request, save, load
baseline = load('baseline.json')
after = request('/api/forecast-views')
old = next(v for v in baseline['views'] if v['scope']['type'] == 'company')
new = next(v for v in after['views'] if v['scope']['type'] == 'company')
assert new['run_id'] != old['run_id'], 'Manual refresh did not publish a new run'
assert new['included_drivers'], 'Supported fixture drivers were not included'
assert request('/api/forecast-views?run_id=' + old['run_id'])['views'] == baseline['views']
save('refreshed.json', after)
print('New run:', new['run_id'])
print('Included driver ids:', [d['id'] for d in new['included_drivers']])
PY
"$FORECAST_JOURNEY_PYTHON" "$FORECAST_JOURNEY_DIR/after-refresh.py"
```

The supported source items now show **Included**. At most two included evidence bubbles appear above each scope's full list. The model release and ambiguity remain **Context only**. Do not require every base number to change: a schedule can conserve quarter workload, transfers can conserve company totals, and an unavailable amount remains unavailable. Save `07-refreshed.png`.

## Source explanation and exact-run Droid

1. Open an **Included** item. Confirm its source quote, source revision, effective dates, numerical parameters and paired omission effect. The effect must refer to the selected scope; interacting effects need not add. Save `08-driver-source.png`.
2. Click **Ask Droid about this driver**. The assistant banner and visible prompt must retain the issued `run_id`, selected `scope_type`/`scope_id`, and exact `driver_id`.
3. Click **Send**. Inspect `POST /compat/api/threads/main/messages` in Network. Its `forecast_context` must contain those same IDs and `action: "explain"`; compare to `refreshed.json`. The fake runner must identify grounded fixture evidence. This does not validate a live Droid/model connection. Save the request payload and `09-droid-exact-run.png`.
4. Reopen a source drawer, refresh the forecast while it remains open, and wait for a new publication. The old drawer must close; it must not silently relabel an old source revision with the new run. Reopen the item to inspect the new publication explicitly.

## Isolated scenario and return path

1. On a team or person page, open an included driver and choose **Preview without this driver**. Inspect the scenario request: it must use the frozen issued run URL and the full same-run **company** included driver set minus only the selected driver. Unrelated team/pool drivers must remain present. No refresh endpoint is called by this action.
2. A fast response contains the isolated bundle. A pending response contains `job_id`, `scenario_id`, parent run, and queued/running status. The browser should poll `/forecast-refreshes/{job_id}`, then retrieve `/forecast-scenarios/{scenario_id}` after success. Pending/failed receipts must never replace issued views with empty arrays. On a deadline, **Check scenario status** resumes the existing job; **Retry preview** on terminal failure creates a new isolated attempt.
3. Confirm the preview banner names the omitted driver and its parent publication. Its values remain separate from the published store. If omitting a membership driver removes the selected team from the scenario, the UI must show **Scenario scope unavailable** and retain **Return to issued forecast**; do not require a fabricated zero.
4. Save `10-scenario.png`, click **Return to issued forecast**, and confirm the exact issued run/values return. Then reload the page: the isolated preview is gone, and the publication is unchanged.

For a controlled pending-state exercise, use DevTools network interception on a disposable run to hold an actual queued scenario response or slow a genuine worker. Record the intervention separately. Do not treat an invented success response as evidence of backend job persistence. Automated unit checks cover queued/running/succeeded, failure/deadline and identity mismatch; a real transient browser run remains a distinct checkpoint.

## Record the result and stop

Write a pass/fail/not-run row for every checkpoint in `browser-result.md`, with artifact names, exact issued/parent/scenario IDs and material errors. Keep synthetic labels visible in screenshots. Stop the frontend and backend with Ctrl-C when finished. The fresh database and captures remain in the printed artifact directory for inspection.

The original sandbox checkpoint used the following source checks (superseded by the October 25 validation above):

```bash
node --test frontend/src/components/dashboard/forecast-derive.test.mjs frontend/src/lib/data/*test.mjs frontend/src/lib/store.test.mjs
cd frontend
./node_modules/.bin/next typegen
./node_modules/.bin/tsc --noEmit
./node_modules/.bin/eslint
```

Historical result: **21 Node checks passed; route type generation, TypeScript and full ESLint passed** using the documented cached compatibility runtime. At that earlier checkpoint the pinned production build and browser procedure were unverified. The October 25 record above documents the subsequently executed pinned build and browser checks.
