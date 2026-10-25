# Frontend integration design (branch `devin/frontend-integration`)

Status: design, to be implemented on top of `main` at `e90b7f1`. The source of truth for decisions is the
approved plan ("Connect the backend to the full frontend"). This page says exactly how to build each
item in it. Only `backend/` and `agent/` change. `frontend/` is read-only (its contracts are frozen).

Fixed facts used throughout:

- Period `2026-P1` runs 2026-10-01..2026-12-31. Data as-of is **2026-10-20**: the last day that has
  usage records. Oct 1 is a Thursday, Oct 19 and Oct 26 are Mondays, and Nov 2 is a Monday.
- Recorded spend to date is research 45,000.00, product 20,000.00 and engineering 30,000.00 (95,000.00).
  Placeholder full-period projections are 85,000 / 50,000 / 65,000. Allocations v1 are 60k / 80k / 60k.
- Backend money stays `Decimal` everywhere. Only `app/compat/mappers.num` turns money into JSON numbers.
- Authority rules do not change. There is no apply, approve or reject tool. Approval still needs the
  approver role, blocks self-approval, checks for stale versions and runs exactly once.

---

## 1. DataClient method -> compat route -> backend service

All routes live under `/compat/api` (the frontend uses `NEXT_PUBLIC_API_URL=http://localhost:8787/compat`).
The store loads 10 GETs with `Promise.all`, so a single non-200 response means nothing renders.

| DataClient | Route | Service(s) | Change |
|---|---|---|---|
| `getCompany` | GET `/company` | `routes_meta.meta` | none. On an unseeded DB it returns 503 `not_seeded` with "The database is not seeded yet; run `python -m app.seed`." (today it is a 404) |
| `getTeams` | GET `/teams` | `Team` rows | adds `lead` (derived, see 1.1) |
| `getPeople` | GET `/people` | **new** `services/people.list_people` | **new route** |
| `getSpending` | GET `/spending` | `spending_svc.list_records` + coverage | adds `personId` and a grouping key that includes the person |
| `getBudgets` | GET `/budgets` | `budget_svc.budget_state` | none |
| `getForecasts` | GET `/forecasts` | `forecast_svc.forecast_for_period` (+ attribution) | team and person forecasts in one list, with `daily` |
| `getContext` | GET `/context?teamId=` | `signal_svc.list_signals` | `scope`, `personIds`, `signal`, `title`, new `expectedEffect`/`claimType` rules, and company items |
| `getDocuments` / `getDocument` | GET `/documents[/{id}]` | `corpus_svc` | `personIds`, `integration`, origin label |
| `getProposals` / `getProposal` | GET `/proposals[/{id}]` | `proposal_svc.proposal_out` | `forecastsReviewed` holds team-level forecasts only |
| `getDecisions` | GET `/decisions` | `decision_svc.decision_out` | readable `appliedBy` |
| `getThread` | GET `/threads/{id}` | `compat/threads` | none |
| `sendMessage` | POST `/threads/{id}/messages` | `intent.parse` + `agent_runs.start_run(wait=True)` | stays synchronous; chat speed settings (§8) |
| `applyProposal` | POST `/proposals/{id}/apply` | `decision_svc.decide(approve)` | error text (§6) |
| `rejectProposal` | POST `/proposals/{id}/reject` | `decision_svc.decide(reject)` | **accepts `stale`** (§6) |

**Unseeded or empty DB.** Every list route answers `200 []` when there is no period, no envelope or no
rows: teams, people, spending, budgets, forecasts, context, documents, proposals, decisions and threads.
To do this, a `_period_or_none` helper replaces `_period` in the list routes. Only `/company` refuses,
because a `Company` cannot be built without `currentPeriod`.
On a freshly seeded DB (with or without seed-time signals), all 10 GETs return 200.

### 1.1 Field mappings (new and changed fields only)

**Person** (`GET /people`, ordered by `team_id, name`; only `active` people)

| TS field | Source | Production |
|---|---|---|
| `id` | `people.id` | slug string, e.g. `research-ava-chen` |
| `teamId` | `people.team_id` | always a team that `/teams` lists |
| `name` | `people.name` | string |
| `role` | `people.role` | omitted if null |
| `email` | `people.email` | omitted if null |
| `integrations` | `people.integrations` (JSON list) | omitted if empty; values are from `Integration` |
| `primaryTool` | `people.primary_tool` | omitted if null |

**Team.lead** (derived, documented): the `name` of the first active person on the team, by id, whose
`role` ends with ` lead`. It is omitted if there is none.

**SpendingRecord**

- Group key becomes `(team or "unattributed", person_id or None, day, component, provider)`.
- `id`:
  - person rows: `"{team}:{person}:{date}:{component}:{provider}"`
  - team-level rows: unchanged, `"{team}:{date}:{component}:{provider}"`
- `personId`: `usage_records.person_id`. It is omitted (`None`, then `exclude_none`) for team-level rows.
- `spending.record_out` adds `"person": r.person_id`. The core `/api/spending/records` gains this
  additive field (contract fixtures are regenerated).
- Every other field keeps its current rule:
  - `amount = num(sum)`; included usage is always `0`;
  - `provenance` is unchanged (G7);
  - `complete` comes from team coverage.
- Filters `teamId`, `from` and `to` are unchanged.

**Forecast**

- Team items are unchanged except:
  - `daily` (from `TeamProjection.daily`) is added;
  - assumptions add `"Sum of {n} individual placeholder projections"` and, if any, `"Includes
    {money_text(P0)} of team-level spend not attributed to a person"`.
- Person items, one per person in `ForecastResult.person_projections`:
  - `id = "fc-{team}-{period}-{person}"`;
  - `teamId`, `personId`, `period` (same as the team), `status: "available"`, `basis: "full_period"`,
    `kind: "forecast"`, `origin: "placeholder"`;
  - `projected = num(amount)`, `daily = [{date, projected: num(amount)}]`, `unit: "usd"`;
  - `assumptions = ["Share of the team placeholder in proportion to recorded spend to date
    ({share_pct}% of team spend)", "Full-period total, includes spend to date"]`;
  - `limitations = [method_label, "simulated projection for the demo company; not a forecast of real
    spend", "person split is proportional to spend to date; not a person-level model"]`;
  - `generatedAt` is the same as the team.
- `low`/`high` are omitted (G6 stays open).
- When a team's projection is missing, every active person on that team gets `status: "unavailable"`
  with the team's `unavailableReason`, `assumptions: []` and the same limitations. No number is filled in.
- Order: all team forecasts (sorted by team), then person forecasts (sorted by team, then person id).
- `share_pct` is the share rounded half-even to one decimal place and formatted as text. It is not a
  money field.

**ContextItem**

- `scope`: `context_signals.scope` (`person | team | company`). It is always sent.
- `personIds`: `context_signals.person_ids` for `person` scope; `[]` for the other scopes. It is always sent.
- `signal`: `context_signals.signal_kind`. Omitted when null.
- `teamIds`:
  - `person`/`team` scope: `[team]`, or `[]` when team is null (the marketing idea);
  - `company` scope: every active team id, sorted.
- `title`: `context_signals.title` when set. Otherwise the existing `derived_title(summary)`. This closes
  the title half of G5.
- `expectedEffect`, in order:
  1. `change_type == timing_shift` and `signal_kind == project_deferred` -> `decrease`;
  2. `timing_shift` with `project_accelerated` -> `increase`;
  3. otherwise the existing `EFFECT` map.

  This closes the `timing_shift` half of G5: the product launch shift becomes `decrease`, as in the
  frontend fixture.
- `claimType`: `observed_event` when `signal_kind == onboarding`. Otherwise the existing rule
  (`stated_plan` for current/superseded/cancelled signals whose first cited doc is plan/update, else
  `interpretation`).
- `sources[]`: `mappers.source_ref` adds:
  - `integration`: `doc_integration(doc)` (below), always sent when the doc exists;
  - `author`: `corpus_documents.author`, omitted if null.
- `/context?teamId=X` returns the signals of team X **plus every company-scope signal**. Company signals
  have `team_id NULL`, so `list_signals` gets `include_company=True` from compat.

**SourceRef / CompanyDocument integration**

`doc_integration(doc) = doc.integration or {"email_export": "email", "slack_export": "slack"}.get(doc.origin, "document")`.
The existing corpus therefore maps as: 02 -> `email`, 06 -> `slack`, everything else -> `document`.

**CompanyDocument**

- `personIds = list(doc.person_tags)`, always sent (`[]` if none).
- `integration = doc_integration(doc)`.
- `origin` label: `{"slack": "Slack export", "asana": "Asana export", "monday": "monday.com export",
  "email": "Email export"}[integration]` if the integration is one of those, otherwise
  `DOC_ORIGIN[doc.origin]`. Then `" (simulated)"` is appended when `is_simulated`, as today.

**Decision.appliedBy**

`APPROVER_LABELS = {"dashboard-approver": "Finance approver (demo)"}`, with `.get(actor_id, actor_id)`.
A header-supplied `X-Actor-Id` is still shown as given. A rejection made through Dismiss is labeled the
same way. The receipt's `note` keeps the stored rationale. The decision log text already says "by …",
and the "(demo)" suffix is the honesty label: identity is not authenticated (G9 is unchanged).

**AllocationProposal.forecastsReviewed / Decision.forecastsReviewed**

These carry **team-level forecasts only**: `_snapshot_forecasts` drops items with `personId`. The reason
is that `proposal-review.tsx` looks up the reviewed projection with `find(f => f.teamId === teamId)`, so
a person item could shadow the team item. The decision log would also list 15 extra rows.

### 1.2 New compat schemas (`app/compat/schemas.py`)

- Add the literals `Integration`, `SignalKind` and `Scope = Literal["person","team","company"]`.
- Add the models `Person` and `ForecastDailyPoint{date, projected, low?, high?}`.
- Add the optional fields:
  - `SpendingRecord.personId`;
  - `Forecast.personId` and `Forecast.daily`;
  - `SourceRef.integration` and `SourceRef.author`;
  - `ContextItem.personIds`, `ContextItem.scope` and `ContextItem.signal`;
  - `CompanyDocument.personIds` and `CompanyDocument.integration`.
- Replace `tests/vendored/frontend_contracts.ts` with a verbatim copy of
  `frontend/src/lib/contracts/index.ts` at `e90b7f1` (update the "copied at" line in the test docstring).
  The drift test then has to pass both vendored and with `COMPAT_UPSTREAM_CHECK=1`.

---

## 2. Database and schema changes

There is no migrations framework. `create_all` does not add columns to an existing SQLite file, so:

- **New guard** `app/db/base.py::check_schema(engine)`, called from `create_app` and `app.seed` right after
  `create_all`. It compares `PRAGMA table_info` for every mapped table with `Base.metadata`. If a column
  is missing it raises `SchemaOutdated("backend/data/app.db predates this backend (missing
  usage_records.person_id, ...). Delete it and run `python -m app.seed`.")`. Without the guard, a stale
  DB would fail later as an opaque 500 error.
- Migration path: delete `backend/data/app.db` and run `python -m app.seed` again (or
  `POST /api/admin/reset` with `BACKEND_ALLOW_RESET=1` on a DB that already has the new schema). Tests
  build fresh temporary DBs, so they need no migration.

### 2.1 `people` (new table, `m.Person`)

| column | type | rule |
|---|---|---|
| `id` | String(64) PK | lowercase slug `^[a-z0-9][a-z0-9._-]{0,63}$`; CHECK `id <> 'unattributed'` |
| `team_id` | FK teams.id, NOT NULL | |
| `name` | String(200) NOT NULL | |
| `role` | String(200) NULL | |
| `email` | String(320) NULL, UNIQUE | stored lowercase |
| `primary_tool` | String(100) NULL | |
| `integrations` | JSON NOT NULL default `[]` | subset of `INTEGRATIONS = ("slack","asana","monday","email","document")`, validated in the service |
| `is_simulated` | Boolean NOT NULL default false | |
| `active` | Boolean NOT NULL default true | |
| `created_at` | UTCDateTime | |

- Service: `app/services/people.py` with `list_people(session, team=None)`, `get_person`, `person_out`
  and `create_people(session, rows)` (used by the seed).
- Core read route `GET /api/people` (`routes_people.py`, `PersonOut`). It goes into `openapi.json`, and
  the contract fixtures are regenerated.

### 2.2 `usage_records.person_id`

- `person_id: FK people.id NULL`, with index `ix_usage_records_team_person_period(team_id, person_id, period_id)`.
- Person attribution follows the same rule as team attribution: it comes **only** from a known
  directory, never from the export alone.
  - The `northstar_billing` CSV/JSON parser accepts a new optional column `user_email` (in `OPTIONAL`;
    lowercased, at most 320 chars, must contain `@`, otherwise a row error `invalid_user_email`). It is
    stored on `ParsedRecord.user_ref`. It is **not** part of `ATTRIBUTION_COLUMNS`.
  - `imports.run_import` resolves `user_ref -> Person` by email. It sets `person_id` only when the person
    exists, is active, and `person.team_id == the team the mapping resolved`.
  - Otherwise `person_id` stays NULL and the parse stats count `person_unresolved` (reported in the batch
    result). An email never moves spend to another team.
  - Unmapped records (team NULL) never get a person.
- `codex_sessions` is unchanged (no person).
- A finance re-mapping (planted P3b) keeps `person_id` only if the person is on the new team. Otherwise
  it clears `person_id`.

### 2.3 `corpus_documents`

- `integration: String(16) NULL`, CHECK `integration IS NULL OR integration IN INTEGRATIONS`.
- `person_tags: JSON NOT NULL default []`.
- `DocumentIn` gains:
  - `integration: Integration | None = None`;
  - `person_tags: list[str] = []` (slugs via `_slugs`).
- `ingest_document` checks that every tag is an existing person, otherwise 422 `unknown_person` with
  reasons.
- The front-matter parser needs no change: it already handles `key: [a, b]` lists and plain values.
- `DocumentOut`/summary add `integration` (raw column) and `person_tags`. `read_document` therefore
  shows Droid who a document is about.

### 2.4 `context_signals`

| column | type | rule |
|---|---|---|
| `scope` | String(16) NOT NULL default `'team'` | CHECK IN (`person`,`team`,`company`); CHECK `scope <> 'company' OR team_id IS NULL` |
| `person_ids` | JSON NOT NULL default `[]` | |
| `signal_kind` | String(32) NULL | CHECK IN `SIGNAL_KINDS` = the frontend `SignalKind` set |
| `title` | String(120) NULL | |

`ContextSignalIn` gains these fields:

- `scope: Literal[...] = "team"` (the default keeps every existing caller valid);
- `person_ids: list[slug] = []` (at most 10, deduplicated);
- `signal_kind: SignalKind | None = None`;
- `title: str | None` (1..120 chars, stripped).

Validation runs in the model validator and in `create_signal`. Every failure is 422 `validation_failed`
with `reasons[].code`:

- `person` scope: `person_ids` must not be empty (`person_ids_required`). Every id must be an active
  person (`unknown_person`). All of them must share one team (`person_team_mismatch`). If `team` is
  given, it must equal that team (`person_team_mismatch`). If `team` is omitted, the backend sets it.
- `team` scope: `person_ids` must be empty (`person_ids_not_allowed`). `team` may be null.
- `company` scope: `team` must be null (`team_not_allowed`) and `person_ids` empty.

`ContextSignalOut` adds `scope`, `person_ids`, `signal_kind` and `title`.

`list_signals(session, team=None, status=None, project=None, scope=None, person=None, include_company=False)`:

- `person=X` matches when `X` is in `person_ids`. This filter runs in Python, because the JSON contains
  check stays portable that way.
- `include_company` ORs in `scope='company'` when `team` is set.

`toolbox._same_signal` adds scope, sorted `person_ids`, `signal_kind` and `title` to the dedupe key.

---

## 3. Deterministic daily per-person spend (`app/seed/daily_spend.py`)

The 8 lump rows are replaced by a generated daily export that runs through the **normal import
pipeline**. Team attribution still comes from mappings, and person attribution from `user_email`.

### 3.1 Files and determinism

- `daily_spend.rows() -> list[dict]` is pure. It uses no randomness and no clock, only the tables below.
  `daily_spend.render_csv(rows) -> bytes` uses LF line endings, a fixed column order, and rows sorted by
  `record_id`.
- `python -m app.seed.daily_spend --write` writes three files:
  1. `app/seed/spend/northstar_export.csv`, the seed;
  2. `backend/seed/planted/01_duplicate_billing_export.csv`, byte-identical to (1), so P1 stays "the same
     file";
  3. `backend/seed/planted/02_reexported_billing_export.csv`: the same records with columns in reverse
     order, rows in reverse order, and CRLF line endings (P1b).
- `--check` exits 1 if any committed file differs. A test runs `--check`.
  These three committed files are always generated by the script and never edited by hand.
- Columns: `record_id,occurred_at,source_account,user_email,provider,model,cost_category,value_kind,amount,unit,notional_value,input_tokens,output_tokens,description`.
- `record_id = "ns-2026p1-{yyyymmdd}-{person_id or team}-{cost_category}"`.
- `occurred_at = "{date}T00:00:00Z"`, `value_kind = simulated`, `unit = USD`.
- Amounts are **whole dollars**, written as `"123.00"`. Included-usage rows have an empty `amount` and
  a whole-dollar `notional_value`.

### 3.2 Targets (exactly today's per-team, per-category split)

| team | account | provider | category | model | target | tokens in/out | who |
|---|---|---|---|---|---|---|---|
| research | ws-research | anthropic | subscription_fee | – | 5000 | – | every person |
| research | ws-research | anthropic | direct_api | claude | 40000 | 1,000,000 / 200,000 | every person |
| research | ws-research | anthropic | included_usage | claude | notional 3000 | 500,000 / 100,000 | **team-level** |
| product | ws-product | openai | subscription_fee | – | 4000 | – | every person |
| product | ws-product | openai | billable_overage | gpt | 16000 | – | every person |
| engineering | ws-engineering | anthropic | subscription_fee | – | 4000 | – | every person |
| engineering | ws-engineering | anthropic | included_usage | claude | notional 2500 | 400,000 / 80,000 | **team-level** |
| engineering | ws-engineering | anthropic | direct_api | claude | 26000 | – | every person |

Counted spend is therefore exactly 45,000 / 20,000 / 30,000, and the notional values stay 3,000 / 2,500.

**Team-level rows are the included-usage rows.** Their realistic story: providers report pooled seat
usage at workspace level. They exercise the "no `personId`" path but count toward no spend: compat sends
amount 0 and `counts_toward_spend` is false. As a result, **person spend sums exactly to team spend** on
every screen, and the forecast split has no team-level bucket in the seed (§4).

### 3.3 People (`app/seed/northstar.py::PEOPLE`, all `is_simulated=True`, email `first.last@northstar.example`)

| id | team | name | role | primary_tool | integrations | usage base | trend |
|---|---|---|---|---|---|---|---|
| research-ava-chen | research | Ava Chen | Research lead | Claude Code | slack, asana | 10 | – |
| research-omar-haddad | research | Omar Haddad | Research scientist | Anthropic API | slack, asana | 30 | 50% from 2026-10-19 |
| research-leila-novak | research | Leila Novak | Research engineer | Claude Code | slack, asana | 15 | 40% from 2026-10-14 |
| research-theo-brandt | research | Theo Brandt | Research scientist | Anthropic API | slack, monday | 20 | – |
| research-yuki-tanaka | research | Yuki Tanaka | Research engineer | Claude Code | slack | 10 | – |
| research-ines-moreau | research | Ines Moreau | Data scientist | Anthropic API | slack, asana | 15 | – |
| product-maya-patel | product | Maya Patel | Product lead | Codex | slack, monday | 15 | – |
| product-noah-kim | product | Noah Kim | Product manager | Codex | slack, monday | 25 | – |
| product-zara-ali | product | Zara Ali | Designer | Codex | slack | 20 | – |
| product-felix-weber | product | Felix Weber | Product engineer | Codex | slack, monday | 40 | – |
| engineering-arjun-rao | engineering | Arjun Rao | Engineering lead | Claude Code | slack, monday | 10 | – |
| engineering-sofia-reyes | engineering | Sofia Reyes | Platform engineer | Claude Code | slack, monday | 30 | – |
| engineering-mateo-silva | engineering | Mateo Silva | Engineer | Cursor | slack | 20 | – |
| engineering-hana-sato | engineering | Hana Sato | Engineer | Claude Code | slack | 15 | active from 2026-10-13 |
| engineering-lucas-meyer | engineering | Lucas Meyer | Staff engineer | Anthropic API | slack, monday | 25 | – |

That is 15 people (6 / 4 / 5). People are seeded in `seed_reference`, after teams and mappings and
before the corpus and spend, because emails and person tags have to resolve.

### 3.4 Algorithm (exact)

```
DATES   = 2026-10-01 .. 2026-10-20 (20 days)
dow(C,d)    = 1 if C == subscription_fee else (3 if d is Mon-Fri else 1)
trend(p,d)  = percent from the table (100 default; e.g. omar 100 before Oct 19, 50 from Oct 19)
active(p,d) = 0 before the person's start date (hana < Oct 13), else 1
seat(p)     = 1  (subscription base), usage base from the table (direct_api / billable_overage)
w(p,d,C)    = base(p,C) * trend(p,d) * dow(C,d) * active(p,d)     # integer
team-level: w(d,C) = dow(C,d)
cells       = every (d, p) with w > 0, ordered by (date, person_id)
split(T, cells) = largest remainder, quantum 1 dollar:
    q_i = T * w_i / W (exact Fraction); a_i = floor(q_i); r = T - sum(a_i)
    give +1 to the r cells with the largest (q_i - a_i); ties -> earlier (date, person_id)
```

- Dollar targets use `split(T)`. Token totals use the same `split` on the same weights, one call per
  token field.
- Cells with weight 0 produce no row. A cell with weight > 0 is always written, even if it rounds to
  `0.00`; a test asserts that every amount in the seed is > 0.
- `description` = the original category description (e.g. `evaluation harness API usage`) +
  `" (simulated daily export)"`.
- Row count: research 120 + 120 + 20 = 260; product 80 + 80 = 160; engineering 88 + 88 + 20 = 196
  (Hana has no rows Oct 1-12). That is **616 records**.
- `planted.py` takes `EXPECTED_SEED_RECORDS = len(daily_spend.rows())` for P1b's `skipped_duplicates`.
  `seed/answer_key.md` P1b changes 8 -> 616, and its header wording changes "8 lump records" -> "616
  daily records".
- The trends make the past spend agree with the person signals (§5): Leila's and Omar's
  week-over-week change is visibly down, and Hana appears from Oct 13. Signals that describe the future
  (Theo out of office from Oct 26, Sofia from Oct 22, Felix from Oct 21, the company change from Nov 2)
  do not touch the past spend.

---

## 4. Per-person placeholder split and daily points (`app/providers/forecast.py`)

### 4.1 Interface (additive)

```python
@dataclass(frozen=True)
class TeamAttribution:
    team: str
    people: dict[str, Decimal]      # active member id -> counted spend to date (0 if none)
    team_level: Decimal             # counted spend with person_id NULL
@dataclass(frozen=True)
class Attribution:
    as_of: date | None              # max occurred_at date of counted records in the period
    period_start: date; period_end: date
    teams: dict[str, TeamAttribution]
```

- `forecast_svc.forecast_for_period` builds the `Attribution` from `usage_records` (`counts_toward_spend`,
  this period) and `people`.
- It passes the attribution only if `getattr(provider, "supports_attribution", False)`. The placeholder
  sets this to True, so injected test providers keep the 2-argument signature.
- Schemas (`schemas/forecasts.py`, all optional, so the change is backward compatible):
  - `DailyProjection{date, amount: MoneyStr}`;
  - `TeamProjection.daily: list[DailyProjection] | None = None`;
  - `PersonProjection{person, team, amount, spent_to_date, share: str, daily, assumptions, uncertainty}`;
  - `ForecastResult.person_projections: list[PersonProjection] = []` and `ForecastResult.as_of: date | None`.
- `_sanitize` keeps person projections for a team only if all of the following hold:
  - the team projection was kept;
  - every person is a member of that team;
  - `sum(person amounts) + team_level_projection == team amount`;
  - the daily sums reconcile.

  Otherwise it drops that team's person projections and adds the reason `person split did not
  reconcile for {team}`. It never "fixes" the numbers.
- Snapshots store the full result. The `get_forecast` **tool** strips every `daily` array before it
  returns the result to Droid (that is 72 × 18 points) and keeps the amounts, `spent_to_date` and `share`.

### 4.2 Algorithm (per team t with placeholder P)

```
S   = sum(people.values()) + team_level          # 45000.00 research
R   = P - S                                       # 40000.00
if R < 0: emit team projection (+ limitation "placeholder is below recorded spend"), no person split
weights = {p: cents(S_p) for p in members} + {BUCKET: cents(team_level)} (bucket only if > 0)
if sum(weights) == 0: weights = {p: 1 for p in members}   (no bucket); if no members: no split
F = floor(R) (whole dollars), c = R - F (cents, 0 in the seed)
R_k = largest-remainder split of F over weights, quantum 1 dollar,
      ties -> person id ascending, BUCKET last
c is added to the key with the largest weight (ties -> id ascending)
P_p = S_p + R_p        (person projection, full_period)
P_0 = team_level + R_0 (bucket; never emitted as a person forecast)
invariant: sum(P_p) + P_0 == P  exactly (Decimal)   -> seed: P_0 == 0, so sum(P_p) == P
```

**Daily points.**

- Days: `D = as_of + 1 .. period_end`. In the seed that is 2026-10-21..2026-12-31, **72 days**. If
  `as_of` is None, `D` starts at `period_start`. If `as_of >= period_end`, `daily` is omitted.
- Weights: `3` Mon-Fri and `1` Sat/Sun. The split is by spend share only: signals are not used,
  because that would make it a model.
- For each key k: `daily_k` = largest-remainder split of `floor(R_k)` dollars over D (ties -> earlier
  date). The cents `R_k - floor(R_k)` go to the first day.
- Team daily: `daily_t[d] = sum_p daily_p[d] + daily_0[d]`. The team series is built by summing, never
  split on its own, so per-day person sums equal the team exactly.
- Guarantees, tested in `Decimal` and again on the compat JSON numbers (all integers in the seed):
  - `sum(daily_p) == R_p`;
  - `spent_to_date_p + sum(daily_p) == P_p`;
  - `S + sum(daily_t) == P`.
- Oct 20 counts as a complete day (the export closes at the end of the day), so no partial-day point
  exists, and the frontend rule "complete-days spend + daily = projected" holds.
- Assumptions on each person projection name the share. The method label stays "shared placeholder (not
  a forecast model)", and every person item carries the placeholder limitation.

---

## 5. Person and company corpus, signals and evals

### 5.1 New documents (`app/seed/corpus/07..13`, `is_simulated: true`)

Each block below is the full file. Every quote is an exact substring, and a test checks that.

**07-research-harness-asana.md**
```
---
doc_key: research-harness-asana
title: "Asana: Eval harness v2 - implementation"
origin: seed
doc_type: update
plan_status: approved
authored_at: 2026-10-14
effective_from: 2026-10-14
effective_to: 2026-11-03
team_tags: [research]
project_tags: [model-evaluation]
person_tags: [research-leila-novak]
integration: asana
author: Ava Chen (Research lead)
is_simulated: true
---
# Eval harness v2 - implementation

**Assignee:** Leila Novak · **Status:** On hold · **Project:** Model evaluation

**Ava Chen** commented on 2026-10-14:
Leila, please stay on the design doc longer and hold the harness build until the design review signs off on 2026-11-03.

**Leila Novak** replied:
Understood. I will pause the implementation branch and keep my API runs to the design spikes.
```
- Quotes: `Leila, please stay on the design doc longer and hold the harness build until the design review signs off on 2026-11-03.` and `I will pause the implementation branch and keep my API runs to the design spikes.`
- Signal: person, `[research-leila-novak]`, research, `project_deferred`, change_type `reduction`,
  2026-10-14..2026-11-03, current.

**08-research-model-switch-slack.md**
- Front matter: `doc_key: research-model-switch-slack`, `title: "Slack #research-evals: moving sweeps to a smaller model tier"`,
  `origin: slack_export`, `doc_type: correspondence`, `plan_status: n/a`, `authored_at: 2026-10-16`,
  `effective_from: 2026-10-19`, `team_tags: [research]`, `project_tags: [model-evaluation]`,
  `person_tags: [research-omar-haddad]`, `integration: slack`, `author: Omar Haddad`.
- Body:
```
**#research-evals** · Slack export (simulated)

**Omar Haddad** 2026-10-16 10:42
Heads up: from Monday 2026-10-19 I'm moving the nightly eval sweeps from the large model to the smaller model tier.

**Omar Haddad** 2026-10-16 10:43
Same prompts and the same sweep schedule, just the cheaper tier for everything except the final comparison runs.

**Ava Chen** 2026-10-16 10:51
Sounds good, keep the final comparison runs on the large model.
```
- Quotes: `from Monday 2026-10-19 I'm moving the nightly eval sweeps from the large model to the smaller model tier.` and `just the cheaper tier for everything except the final comparison runs.`
- Signal: person `[research-omar-haddad]`, `model_change`, `reduction`, from 2026-10-19, current.

**09-research-availability-monday.md**
- Front matter: `doc_key: research-availability-monday`, `title: "monday.com: Research availability board"`,
  `origin: seed`, `doc_type: update`, `plan_status: n/a`, `authored_at: 2026-10-18`,
  `effective_from: 2026-10-26`, `effective_to: 2026-10-30`, `team_tags: [research]`, `project_tags: []`,
  `person_tags: [research-theo-brandt]`, `integration: monday`, `author: Theo Brandt`.
- Body:
```
# Research availability (monday.com board, simulated export)

| Person | Status | Dates | Note |
|---|---|---|---|
| Theo Brandt | Out of office | 2026-10-26 to 2026-10-30 | Conference travel |
| Ava Chen | Available | - | - |

Item update by Theo Brandt on 2026-10-18: Out of office 2026-10-26 to 2026-10-30, no eval runs scheduled while I am away.
```
- Quote: `Out of office 2026-10-26 to 2026-10-30, no eval runs scheduled while I am away.`
- Signal: person `[research-theo-brandt]`, `out_of_office`, `reduction`, 2026-10-26..2026-10-30, current.

**10-engineering-cutover-monday.md**
- Front matter: `doc_key: engineering-cutover-monday`, `title: "monday.com: Platform cutover moved up"`,
  `origin: seed`, `doc_type: update`, `plan_status: approved`, `authored_at: 2026-10-19`,
  `effective_from: 2026-10-22`, `team_tags: [engineering]`, `project_tags: [platform]`,
  `person_tags: [engineering-sofia-reyes]`, `integration: monday`, `author: Arjun Rao (Engineering lead)`.
- Body:
```
# Platform cutover (monday.com item, simulated export)

**Owner:** Sofia Reyes · **Status:** Moved up · **Board:** Engineering platform

Arjun Rao changed the start date on 2026-10-19: the cutover regression suite now starts 2026-10-22 instead of mid-November.
Sofia Reyes will run the full regression suite with Claude Code daily until the cutover completes.
```
- Quotes: `the cutover regression suite now starts 2026-10-22 instead of mid-November.` and `Sofia Reyes will run the full regression suite with Claude Code daily until the cutover completes.`
- Signal: person `[engineering-sofia-reyes]`, `project_accelerated`, `expansion`, from 2026-10-22, current.
- Uncertainty names the team note (2026-10-12) that says the migration continues at the current pace.
  This item moves one person's work earlier and does not say that the team total changes.

**11-engineering-welcome-slack.md**
- Front matter: `doc_key: engineering-welcome-slack`, `title: "Slack #eng-platform: welcome Hana"`,
  `origin: slack_export`, `doc_type: correspondence`, `plan_status: n/a`, `authored_at: 2026-10-13`,
  `effective_from: 2026-10-13`, `team_tags: [engineering]`, `project_tags: [platform]`,
  `person_tags: [engineering-hana-sato]`, `integration: slack`, `author: Arjun Rao (Engineering lead)`.
- Body:
```
**#eng-platform** · Slack export (simulated)

**Arjun Rao** 2026-10-13 09:05
Welcome Hana Sato, who joined the platform team today; her Claude Code seat and API key are active from 2026-10-13.

**Hana Sato** 2026-10-13 09:12
Thanks! Pairing with Sofia on the migration backlog this week.
```
- Quote: `Welcome Hana Sato, who joined the platform team today; her Claude Code seat and API key are active from 2026-10-13.`
- Signal: person `[engineering-hana-sato]`, `onboarding`, `expansion`, from 2026-10-13, current
  (claimType `observed_event`).

**12-product-tool-switch-slack.md**
- Front matter: `doc_key: product-tool-switch-slack`, `title: "Slack #product-launch: tuning scripts move to the API"`,
  `origin: slack_export`, `doc_type: correspondence`, `plan_status: n/a`, `authored_at: 2026-10-19`,
  `effective_from: 2026-10-21`, `team_tags: [product]`, `project_tags: [workspace-launch]`,
  `person_tags: [product-felix-weber]`, `integration: slack`, `author: Felix Weber`.
- Body:
```
**#product-launch** · Slack export (simulated)

**Felix Weber** 2026-10-19 16:20
From 2026-10-21 I'm moving my launch-tuning scripts off my Codex seat and onto the OpenAI API directly.

**Felix Weber** 2026-10-19 16:21
The work itself doesn't change; it will show up as API usage instead of seat overage.

**Maya Patel** 2026-10-19 16:30
OK, flag it in the finance channel when the first API invoice lands.
```
- Quotes: `From 2026-10-21 I'm moving my launch-tuning scripts off my Codex seat and onto the OpenAI API directly.` and `it will show up as API usage instead of seat overage.`
- Signal: person `[product-felix-weber]`, `tool_change`, `continuation` (neutral), from 2026-10-21, current.

**13-company-model-announcement-slack.md**
- Front matter: `doc_key: company-model-announcement-slack`, `title: "Slack #announcements: new default model"`,
  `origin: slack_export`, `doc_type: correspondence`, `plan_status: n/a`, `authored_at: 2026-10-20`,
  `effective_from: 2026-11-02`, `team_tags: [research, product, engineering]`, `project_tags: []`,
  `person_tags: []`, `integration: slack`, `author: Arjun Rao (Engineering lead)`.
- Body:
```
**#announcements** · Slack export (simulated)

**Arjun Rao** 2026-10-20 11:00
Starting 2026-11-02, every team's default model moves to the new mid-tier model that platform approved this week.

**Arjun Rao** 2026-10-20 11:02
Per-token prices are lower than today's default, but long-context runs use more tokens, so the net effect on each team's bill is not known yet.
```
- Quotes: `Starting 2026-11-02, every team's default model moves to the new mid-tier model that platform approved this week.` and `the net effect on each team's bill is not known yet.`
- Signal: **company**, team null, `person_ids []`, `model_change`, change_type `other` (`unknown`),
  from 2026-11-02, current.

Text constraints: plain ASCII apostrophes, no `next period` and no `this period` phrase. That keeps the
existing `_NEXT`/`_THIS` conflict detector quiet. Only the `·` middle dot is used, matching corpus 06.

### 5.2 Titles and summaries recorded by the stand-in (`PLAYBOOK` additions)

| doc_key | title | summary (no number beyond dates in the quotes) |
|---|---|---|
| research-harness-asana | Leila Novak's harness build deferred to Nov 3 | Ava Chen asked Leila Novak (Asana, 2026-10-14) to stay on the design doc and hold the eval-harness build until the design review on 2026-11-03; Leila is pausing the implementation branch. |
| research-model-switch-slack | Omar Haddad moving eval sweeps to a cheaper model tier | Omar Haddad said (Slack, 2026-10-16) that from 2026-10-19 his nightly eval sweeps move to the smaller, cheaper model tier, except the final comparison runs. |
| research-availability-monday | Theo Brandt out of office Oct 26-30 | Theo Brandt is out of office 2026-10-26 to 2026-10-30 (monday.com), with no eval runs scheduled while away. |
| engineering-cutover-monday | Sofia Reyes's cutover regression runs start Oct 22 | Arjun Rao moved the platform cutover regression suite up to 2026-10-22 from mid-November (monday.com); Sofia Reyes runs it daily with Claude Code until cutover. |
| engineering-welcome-slack | Hana Sato joined the platform team | Hana Sato joined engineering on 2026-10-13 (Slack); her Claude Code seat and API key are active from that date. |
| product-tool-switch-slack | Felix Weber moving tuning scripts to the OpenAI API | Felix Weber said (Slack, 2026-10-19) that from 2026-10-21 his launch-tuning scripts move from his Codex seat to the OpenAI API; the work is unchanged and shows up as API usage instead of seat overage. |
| company-model-announcement-slack | Company-wide default model change from Nov 2 | From 2026-11-02 every team's default model moves to a new mid-tier model (Slack #announcements); per-token prices are lower but long-context runs use more tokens, and the net effect is not known. |

Each entry also sets `uncertainty` (what the text does not establish: volumes, prices, whether dates hold).

Existing entries gain `scope: "team"`, `signal_kind` and `title`:

| doc_key | signal_kind | title |
|---|---|---|
| research-eval-plan | project_accelerated | Research model-evaluation expansion moves into the current period |
| research-timeline-thread | project_deferred | Older thread: research expansion pushed to next period |
| product-launch-plan | project_deferred | Product GA launch moves to the following period |
| engineering-platform-note | steady | Engineering platform migration continues at the current pace |
| marketing-ideas-slack | (none) | Marketing idea: personalized AI demo videos |

### 5.3 How the signals are produced

- **New read tool `list_people`.** Added in `tools.py`, `toolbox`, `sdk_tools`, `NORTHSTAR_TOOL_IDS`,
  the regenerated `tool_manifest.json`, and `evals.scenarios.READ_TOOLS`. Input `{team?: str}`; output
  `{count, items: [PersonOut]}`. Droid needs it to turn names into person ids.
- **`record_signal`.** The input schema is `ContextSignalIn` without `agent_run_id`, so it carries the new
  fields automatically. The description adds: "scope person (person_ids from list_people, all on one
  team), team, or company (team null, every team affected); signal_kind is one of …; title ≤ 120 chars."
- **`FakeDroidRunner._interpret`.**
  1. It calls `list_people()` once.
  2. It walks the ordered keys: existing 4, then the 6 person docs, then the company doc.
  3. For person rules, `person_ids = doc["person_tags"]`, filtered to people whose team equals
     `rules["team"]` **and whose `name` occurs in the document content**. A dropped tag adds the warning
     `person_not_confirmed`. If none remain, the signal is skipped with a warning and never guessed.
  4. The status rule is unchanged (approved/n/a -> current).
  5. `_signal` passes `scope`, `person_ids`, `signal_kind` and `title`.
  6. The `signal_recorded` event adds `scope`, `person_ids` and `signal_kind`.
  7. That totals 12 signals, within `MAX_SIGNALS = 20`. No document stays outside the playbook, so
     there is no `document_not_interpreted` warning on the seed corpus.
- **`prompts/interpret_corpus.md`.** It gains step 2b:
  - for documents with `person_tags` or a named individual, call `list_people`, record `scope: person`
    with those ids and the matching `signal_kind`;
  - company-wide announcements are `scope: company` with no team;
  - team plans stay `scope: team`;
  - never infer a person who is not named in the text;
  - give a short `title`.

  It also lists the `SignalKind` meanings, copied from the TS comments. Then
  `python -m app.agent.tools` regenerates the manifest.

### 5.4 New eval scenarios (`evals/scenarios.py`, `answer_key.md`, `evals/README.md`)

- `RunCtx` gains `people: list[dict]`, read via `GET /api/people` in the harness.
- **`person_signals_cited`** (fixture `interpret`). It checks all of the following:
  1. For each of the 6 person docs, exactly one `current` signal with `scope == "person"` cites that
     doc_key.
  2. Its `person_ids == doc.person_tags`, its `team` is that person's team, and its `signal_kind` is the
     one in the §5.1 table.
  3. Every `person_ids` entry is a real person on `team`.
  4. The company doc yields exactly one current signal with `scope == "company"`, `team is None`,
     `person_ids == []` and `signal_kind == "model_change"`.
  5. No team-scope signal carries `person_ids`.
  6. No person or company summary contains a `$` amount or a `%` value absent from its cited text
     (`textcheck`).
- **`propose_reuses_signals`** (new fixture `addition_50k_after_interpret`: setup runs `interpret_corpus`,
  then `propose_allocation` addition 50k prioritizing research). It checks:
  - the propose run's steps contain **no** `search_corpus`/`read_document`;
  - every `evidence_refs` signal id exists and is `current`;
  - the proposal is `pending_review`.
- Existing scenarios keep passing. If a scorer hard-codes a signal count, change it to filter
  `scope == "team"` rather than loosening its intent.

---

## 6. Reject on stale or failed, and decision recording

- `decision_svc.decide`, reject branch only:
  - allowed from statuses `("pending_review", "stale")`;
  - `claim_status(..., "rejected", from_statuses=("pending_review","stale"))`.
- Approve stays `pending_review`-only, with all existing checks in the same order: role, idempotency,
  self-approval (approve only), status, stale lock.
- The `Decision` row is `outcome=rejected`, `from_version` = current `state_version`,
  `to_version=NULL`, `before` = current figures, `after=NULL`. Allocations, the envelope version and
  snapshots are untouched (DB CHECK `version_transition` already enforces this).
- `revised`, `applied` and `rejected` still answer 409 `proposal_not_pending`.
- A dismissed stale proposal is `rejected` and can no longer be rebased (`rebase` requires `stale`).
  This is intended: dismissal means "not used".
- This also changes core `POST /api/proposals/{id}/decision`: a stale proposal can now be rejected
  there. That is the same rule, and it is recorded in design.md §5.
- Compat `/reject`:
  - `_guard_settled` as today;
  - rationale = `DISMISS_NOTE = "Dismissed from the dashboard: the budget changed after this proposal
    was drafted"` when `proposal_out.is_stale`, else `REJECT_NOTE`;
  - idempotency key `compat-reject-{id}`;
  - returns the proposal (`status: "rejected"`).
- **`failed`** is never produced, because the backend validates at draft time. The UI's Dismiss on
  `failed` is therefore unreachable. If a later change emits `failed`, it must map to a backend status
  that reject accepts.
- Readable errors (`compat/errors.MESSAGES`), shown verbatim by the UI:
  - `already_applied`: "This proposal was already applied; it cannot be applied or rejected again."
  - `already_rejected`: "This proposal was already rejected."
  - `stale_proposal`: "The budget changed after this proposal was drafted, so it was not applied. Ask
    the assistant for a refreshed proposal, or dismiss this one."
  - `self_approval_forbidden`, `role_forbidden` and `not_found`: one plain sentence each.

  The UI then calls `refreshBudgets`, picks up `status: "stale"`, and shows Dismiss.

---

## 7. Seed-time interpretation and `--live-signals`

- `seed(...)` (the library function) gains `interpret: Literal["none","fake","live"] = "none"`. The
  default stays none, so tests, evals, `--check-planted` and the contract export are unchanged.
- `app/seed/interpret.py::interpret_at_seed(session_factory, *, settings, clock, ids, mode)`:
  - It builds a `SimpleNamespace` app state with `settings = replace(settings, droid_runner="fake"|"sdk")`
    and `droid_runner = FakeDroidRunner()` for fake (`None` for live, so `load_runner("sdk")` runs).
    It also sets `forecast_provider`.
  - It calls `agent_runs.start_run(state, AgentRunCreate(task_type="interpret_corpus", wait=True),
    actor=Actor("seed-interpreter", "finance_analyst"))`.
  - The run is a normal audited `AgentRun`. Its signals are labeled `produced_by: droid_fake` (or
    `droid_sdk`).
- CLI `python -m app.seed` takes a mutually exclusive choice: `--live-signals`, `--no-signals`, or the
  default fake.
  - The default on a fresh DB seeds, then runs the fake interpretation, and prints
    `signals: 12 recorded by droid_fake (run <id>)`.
  - `--live-signals` first runs a **preflight**, `load_runner("sdk")`, before touching the DB. If the
    runner is unavailable, it prints `--live-signals needs the real Droid: <reason>. Nothing was seeded.`
    and exits 2. There is no fallback to fake.
  - If the live run then ends `failed`/`unavailable`, it prints the run id and error plus "the
    database is seeded without Droid signals" and exits 1.
  - On an already seeded DB, both flags print `already seeded; signals are only interpreted on a fresh
    seed (delete the DB or use /api/admin/reset)`. With `--live-signals` the exit code is 1; with the
    default it is 0.
  - Env vars and keys are never printed.
- `reset_database` (admin reset) seeds with `interpret="fake"`, so a demo reset shows context cards
  again.

---

## 8. Chat speed and signal reuse

**Verified against `backend/.venv/.../droid_sdk` 0.5.0 (`_high_level/session.py`).**

- The signature is `Session(*, cwd=None, model: str | None = None, reasoning_effort: ReasoningEffort |
  None = None, config: SessionConfig | None = None, interactions=None, runtime=None, api_key=None)`.
- `droid_sdk.ReasoningEffort` values: `none, dynamic, off, minimal, low, medium, high, xhigh, max`.
- `SessionConfig` only has `spec_model`/`spec_reasoning_effort`, which are for spec mode and not used here.

Implementation in `SdkDroidRunner`:

- `from_env` reads `DROID_CHAT_MODEL` and `DROID_CHAT_REASONING_EFFORT`, both optional and stripped.
  An effort value outside the enum's values raises `RunnerUnavailable(reason="bad_config")` with the
  allowed list. The value itself is printed; it is not a secret.
- `CHAT_TASKS = {"answer_question", "propose_allocation"}`. Stale recovery is a `propose_allocation`, so
  it counts as chat.
- `_settings_for(task)`: for chat tasks, `model = chat_model or self.model` and `effort = chat_effort`.
  For `interpret_corpus`, it uses `self.model` with no effort (the default).
- The `sdk.Session(...)` call passes `reasoning_effort=sdk.ReasoningEffort(effort)` **only when set**, so
  an older SDK or the test double without the kwarg still works.
- `tools.emit("runner_config", {"task_type", "model", "reasoning_effort"})` uses `source="backend"`, so
  the run log shows the settings. No secrets are included.
- `tests/fake_droid_sdk.py`:
  - `Session.__init__` accepts `reasoning_effort=None` and stores it;
  - add `class ReasoningEffort(str, Enum)` with the same values.
- Recommended demo setting: `DROID_CHAT_REASONING_EFFORT=low`. `DROID_CHAT_MODEL` is unset by default;
  the docs name no model id.

Signal reuse in `propose_allocation`:

- `SdkDroidRunner._run` pre-reads `tools.list_signals(status="current")` for non-stale propose tasks. It is
  a normal recorded step, so it stays visible.
- `task_prompt(task, current_signals)` then embeds a compact table of the current signals: id, team,
  scope, signal_kind, title, and their cited quotes with doc_key/version.
- The full `interpret_corpus.md` is appended **only** when no current signal exists for the prioritized
  team. Otherwise the prompt adds: "Current signals are listed above; cite them by id in evidence_refs
  and do not call search_corpus or read_document unless a signal you need is missing."
- `prompts/propose_allocation.md`, step 1 is reworded to match. The rule that only current signals may
  justify moving money is unchanged.
- The fake runner already reuses signals (`_propose` interprets only when the prioritized team has no
  current signal). The new eval checks that.
- Separate deliverable `backend/docs/frontend-streaming-note.md`: `POST /api/agent/runs {wait:false}` +
  SSE `/api/agent/runs/{id}/events`, proposed to the teammate as a frontend change. No frontend edit is
  made here.

---

## 9. Test plan per module

| Module | Tests |
|---|---|
| `db/models`, `db/base.check_schema` | Person CHECKs (no `unattributed` id, unique email); signal CHECK company => team NULL; `check_schema` raises `SchemaOutdated` naming the missing column on a DB created with the old `usage_records` |
| `seed/daily_spend` | `--check` equals the committed CSV and planted 01/02; 616 rows; per team x category sums exactly equal §3.2 (amount, notional, tokens); every amount > 0; no Hana rows before Oct 13; Leila's and Omar's daily API averages drop after their dates; deterministic (two calls equal) |
| `parsers/northstar_csv`, `services/imports` | `user_email` resolves to a person on the mapped team; unknown or other-team email -> `person_id NULL` + `person_unresolved` stat; invalid email -> row error; the team never comes from an email |
| `seed/northstar` | 15 people (6/4/5); spend 45k/20k/30k; person sum == team counted spend; included rows are team-level; corpus is 13 docs with person tags resolved; `seed()` default records no signals; `seed(interpret="fake")` records 12 signals `produced_by droid_fake` |
| `seed/__main__` | default fresh seed prints the signal count; `--no-signals`; `--live-signals` without a key exits 2 and leaves the DB file untouched (missing or empty); already seeded messages and exit codes |
| `seed/planted` | `--check-planted` 12/12 with P1b = 616 |
| `providers/forecast`, `services/forecasts` | split invariants (`sum(P_p)+P_0 == P`, daily sums, `S + sum(daily_t) == P`) for the seed and for property cases: zero spend, a single person, a team-level bucket, cents in P, `R < 0`, `as_of` None or at period end; 72 daily dates Oct 21..Dec 31 with weekday weight 3; ties stable; a provider without `supports_attribution` still works; `_sanitize` drops a non-reconciling person split with a reason; `get_forecast` tool output has no `daily` |
| `schemas/signals`, `services/signals` | scope validation codes (`person_ids_required`, `unknown_person`, `person_team_mismatch`, `team_not_allowed`, `person_ids_not_allowed`); team derived for person scope; `list_signals(person=…, include_company=True)`; dedupe includes the new fields |
| `services/corpus` | `integration`/`person_tags` front matter parsed and stored; `unknown_person` 422; the exact-quote test for all §5.1 quotes |
| `services/decisions` | reject of `stale` -> `rejected` decision, allocations, version and snapshots unchanged; reject of stale-but-pending works; `revised`/`applied`/`rejected` still 409; approve of stale still 409 `stale_proposal`; role and self-approval tests unchanged |
| `agent/tools`, `toolbox`, `sdk_tools` | manifest in sync (incl. `list_people`); no forbidden tool words; `record_signal` accepts person/company scope and refuses invalid ones as `ToolError` |
| `agent/fake_runner` | interpret records exactly the 12 signals with §5.2 kinds and titles; `person_not_confirmed` when a tag's name is absent (corpus fixture with a bad tag); propose after interpret makes no read_document calls |
| `northstar_droid/sdk_runner` (fake sdk) | chat tasks pass `DROID_CHAT_MODEL` / `reasoning_effort` to `Session`; interpret uses `DROID_MODEL` and no effort; a bad effort -> `RunnerUnavailable(bad_config)`; the `runner_config` event; the propose prompt omits the interpret steps when current signals exist and includes them when they do not; the pre-read `list_signals` step is recorded; the permission gate tests are unchanged |
| `compat` mappers/router | `/people` shape; `/spending` personId and ids, person sums == team totals; `/forecasts` team + person items, person `projected` sums == team, `spent(complete days) + sum(daily) == projected` on the JSON numbers, unavailable propagation; `/context` scope/personIds/signal/title/effect/claimType, company item in every `teamId` filter, `sources[].integration/author`; `/documents` personIds/integration/origin label; `forecastsReviewed` has no personId; `appliedBy == "Finance approver (demo)"`; dismiss of a stale proposal records a rejected decision with DISMISS_NOTE and leaves budgets; all 10 GETs 200 on a fresh seeded DB **and** list routes `200 []` on an unseeded DB; `/company` 503 unseeded |
| `test_compat_contract` | vendored TS updated to `e90b7f1`; passes with `COMPAT_UPSTREAM_CHECK=1` |
| `contract/export` | regenerate with `python -m app.contract.export`; `--check` green; never hand-edit fixtures |
| `evals` | `python -m evals.run --runner fake` passes everything incl. `person_signals_cited` and `propose_reuses_signals`; restore `results/fake.*` if only the timestamp changed |

Gates before each commit: `.venv/bin/pytest -q`, `python -m evals.run --runner fake`,
`python -m app.seed --check-planted` (12/12) and `python -m app.contract.export --check`.
There are no live Droid runs in this workflow.

### Suggested commit order

1. people + schema guard
2. daily spend generator + import `user_email` + planted regeneration
3. forecast split
4. corpus/signal fields + `list_people` + fake runner + prompts + evals
5. reject-on-stale
6. compat catch-up + drift test
7. seed-time interpretation
8. chat speed settings + signal reuse
9. docs (`frontend-alignment.md`, README, streaming note)

---

## 10. Contract ambiguities resolved here

1. **Person sums vs team-level rows.** The only team-level rows are included usage, which is 0 dollars
   in compat. Person spend and projections therefore reconcile exactly to the team. For priced
   team-level spend, a general bucket keeps `sum(P_p) + P_0 == P` and is disclosed in the team's
   assumptions.
2. **`daily` start.** Points start the day after the data as-of (Oct 21). Oct 20 is complete, so there
   is no partial-day point.
3. **`forecastsReviewed`** is team-level only, because of the `find` by `teamId` in proposal-review.
4. **Company scope**: `teamIds` = all active teams, team null in the DB, and the item is included in every
   `/context?teamId=` result.
5. **`failed`** is never emitted. Dismiss maps to reject, which now accepts `stale`.
6. **`integration`** falls back from the document origin when it is not set. **`origin`** is labeled
   from the integration.
7. **`expectedEffect`** for `timing_shift` comes from `signal_kind`. **`claimType`** is `observed_event`
   for onboarding.
8. **Whole-dollar quantum** for the seed and the placeholder split, so the JSON numbers sum exactly in
   JavaScript. Leftover cents are placed deterministically.
9. **`Team.lead`** is derived from the role suffix ` lead`. **`appliedBy`** is a labeled demo identity,
   not an authenticated one.
10. **Unseeded DB**: list routes return `200 []` and `/company` returns 503 with a seeding hint.
