# Uber corpus: what the live interpret CLI should read (probe notes, 2026-10-24)

Probe for `python -m app.interpret` (plan: live interpretation of the Uber corpus with a credit cap).
Dataset: `python3 datagen/generate.py --quiet` (default seed), loaded with
`datagen/load_backend.py --db /tmp/uber_probe.db --reset`: 249 corpus documents, 331,732 usage
records, periods Q1-Q4 2026, Q4 (2026-10-01 .. 2026-12-31) current, as-of 2026-10-24.
No live Droid run was made. Holdout files were not read.

## Corpus inventory (249 documents)

| | |
|---|---|
| Integrations | slack 102, asana 61, email 46, monday 40 (Teams messages arrive as `slack`, Outlook/Gmail as `email`) |
| Origin / type | slack_export 102, upload 101, email_export 46; correspondence 148, update 101 |
| `authored_at` by month | Jan 9, Feb 22, Mar 30, Apr 28, May 22, Jun 29, Jul 16, Aug 32, Sep 16, Oct 45 (latest 2026-10-23, none after the as-of date) |
| Effective window | every doc has `effective_from`; 10 have no `effective_to` (open-ended: offboardings, policy/price changes, Copilot retirement) |
| Size | 621-1,537 chars, mean 831 |
| Tags | `team_tags` always set; company-wide notices carry all 16 team ids; `person_tags` use people ids (`rider-app-keiko-ibrahim`) that match the `people` table |
| Supersession | none: no `supersedes` links in this corpus |

`doc_key` is stable (`uber-msg-0036`, `uber-task-0024`); the backend `id` (`doc_<uuid>`) is new on every
load, so batch plans and idempotency must be keyed by `doc_key` (+ version), resolved to ids at run time.

Most storylines come as a pair: a Slack/Teams/email message plus an Asana/monday task for the same
event (same team, same effective window). Pairs must land in the same batch.

## Selection rule ("Q4-relevant")

Period P = the current planning period resolved from the clock (Q4: 2026-10-01 .. 2026-12-31).

```sql
SELECT * FROM corpus_documents
WHERE superseded_by_document_id IS NULL
  AND (date(authored_at) >= :since                                   -- default 2026-09-01
       OR (:include_announced
           AND effective_to IS NOT NULL
           AND effective_from <= :period_end
           AND effective_to   >= :period_start))                     -- announced earlier, window overlaps P
```

- `--since 2026-09-01` alone: **61** documents.
- `--since 2026-09-01 --include-announced`: **64** documents. The 3 extra are:
  `uber-msg-0040` (hiring freeze Aug 17 - Oct 4, authored Aug 13), `uber-msg-0030` and
  `uber-task-0008` (Support Reply Drafting rollout Sep 1 - Dec 18, authored Aug 24; one of the
  planted Q4 overrun drivers).
- Open-ended docs authored before `since` (offboardings, Gemini policy Jun 1, GPT-5.5 mini price Aug 1)
  are deliberately excluded: they took effect before Q4 and are already in the spend history the
  forecast learns from. No pre-`since` doc has `effective_from` inside Q4.
- 4 of the 61 are dated >= since but their window ended before Oct 1 (Labor Day Sep 7, two
  out-of-office auto-replies ending Sep 24 / Oct 1, Reviewer tooling GA ending Sep 15). Kept by the
  rule (cheap, and the interpreter may record nothing for them); 40 of the 61 take effect after the
  as-of date (the announced future events).
- Mix of the 64: slack 25, asana 15, monday 13, email 11; 57 carry `person_tags`.

## Batching plan (7 batches, ~10 docs, grouped by team then time)

Rule: group by team-tag set; company-wide and multi-team docs first; then pack whole teams greedily
up to 10 (allow 11 rather than split a team or a message/task pair); inside a batch order by
`authored_at`. Result for the default dataset:

| # | Docs | Teams | Content |
|---|---|---|---|
| 1 | 9 | company-wide (7) + Copilot retirement (2, 7 teams) | Labor Day, Haiku 5.5 price cut, Thanksgiving, year-end shutdown, Build Week, Fable 5.1 pilot + pricing; Copilot -> Cursor Oct 1 |
| 2 | 10 | ai-labs + safety-trust | Fable pilot tasks (2), Jun OOO pair, Esther OOO/auto-replies, Trip Audio Review pair, Reviewer GA |
| 3 | 10 | support-automation, infra-sre, security, marketing-comms | Reply Drafting rollout pair, Malik OOO pair, Ticket Auto-Triage v2 pair; Omar OOO pair; Kavya joins; Holiday Campaign |
| 4 | 11 | rider-app, maps-routing, marketplace-pricing | Pickup Spot v3 pair, Mateo/Keiko OOO pairs; Ines OOO pair; Matching Latency (3) |
| 5 | 9 | driver-app, eats-delivery | Driver Assist expansion, Earnings Explainer pair, Luis OOO pair; Anya/Amara OOO pairs |
| 6 | 9 | people-recruiting, finance-legal | Hiring freeze + lift, Luis/Dmitri OOO pairs; Oct close, Contract Clause Extraction pair |
| 7 | 6 | freight, payments-risk | Shipper Quote pair, AI Dispatch v2 pair (from Nov 2); Fraud Rules Migration hold pair |

Without `--include-announced` batch 3 loses the rollout pair and batch 6 the freeze notice (61 docs).

Credit estimate: the Northstar `interpret_corpus` runs (13 docs, ~4.9k chars) cost 49,921-72,548
`factory_credits`; an Uber batch is ~4.3k chars of content, so expect ~50-75k per batch, ~350-525k
for all 7. With `--credit-cap 600000` the CLI should stop before a batch when
`spent + max(largest batch so far, 75000) > cap`, so it may stop after 6 batches if batches run high.
Credits come from `output.usage.provider_reported.factory_credits` (SDK only; the fake reports none).

## Scoping `interpret_corpus` to a subset: what exists today

- `build_task` rejects any params on `interpret_corpus` (`422 unexpected_params`), so scoping needs a
  new, validated `params.document_ids` (existing current documents only, at most 20).
- `search_corpus` returns at most `MAX_SEARCH_RESULTS = 20` items (`total_matches` gives the rest), and
  the prompt's step 1 is "list every document with an empty query". On the 249-doc corpus an unscoped
  run sees only the first 20 rows in table order, so scoping is needed for correctness, not only cost.
- Proposed scope, mirroring `rebase_target`: `BackendToolbox(doc_scope=set_of_ids)`; `search_corpus`
  filters to the scope, `read_document` and citations in `record_signal` outside it are refused with a
  new `document_out_of_scope` code (stricter, nothing in the gate or authority rules is relaxed). The
  SDK prompt appends the scope list and "interpret only these documents". Unscoped runs (Northstar,
  evals) are unchanged.
- Per-run budgets fit a 10-doc batch: `MAX_TOOL_CALLS = 80` (1 search + 10 reads + list_people +
  <=20 record_signal + retries), `MAX_SIGNALS = 20`. Identical signals are already reused by the
  toolbox, so a re-run does not duplicate them.
- Idempotency: a doc yielding no signal leaves no citation, so "already interpreted" should be
  "`doc_key`+version appears in `params.document_ids` of a `succeeded` interpret_corpus run with the
  same runner kind" (signal citations alone would re-run empty docs every time).

## FakeDroidRunner on the Uber corpus (measured)

Unscoped `interpret_corpus` against a copy of the scratch DB (`wait=true`): `succeeded` in 2.4 s,
read 20 documents (the search cap), **0 signals**, warnings: 20 `document_not_interpreted` (outside
the playbook) and 11 `expected_document_missing` (Northstar keys absent). No crash. Summary text:
"Read 20 documents; recorded 0 cited signals (0 current)." For scoped runs the fake should read every
scoped doc, record nothing, and emit one `document_not_interpreted` warning per doc; the 11
`expected_document_missing` warnings should be skipped when a scope is given (they are noise there).
That is the "produces nothing, clearly labeled fake" behaviour the CLI tests can assert.

## Caveat found while probing

Two agents generating into the shared `datagen/out/` at once truncate each other's files (the loader
then fails with a missing billing CSV). For parallel work use `generate.py --out <private dir>` and
`load_backend.py --out-dir <private dir>`.
