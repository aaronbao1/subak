# Northstar seed data

All data here is **simulated** (fictional Northstar Software, USD, planning period `2026-P1`).

- **Default seed**: lives in the importable package at `app/seed/`. That is
  `app/seed/spend/northstar_export.csv` (allocations 60k/80k/60k, spend 45k/20k/30k = 95k, included
  usage notional only) and `app/seed/corpus/*.md` (six documents: approved research plan, superseded
  September research thread, product launch plan v1 -> v2, engineering note, informal marketing Slack).
  Load it with `python -m app.seed`. Loading is idempotent, and the contract fixtures are generated
  from it.
- **Planted-error pack** (`planted/`, this folder): a duplicate export and a re-export, a
  cumulative-counter Codex session, an unmapped provider project, a proposal drafted on outdated
  budgets, and two extra documents (an informal Slack restatement of the superseded timeline, and an AP
  late-invoice / accrual email). With them the corpus has eight documents. The expected handling for
  each item is in [`answer_key.md`](answer_key.md).

```bash
cd backend
.venv/bin/python -m app.seed                   # default seed only
.venv/bin/python -m app.seed --with-planted    # default seed + planted data traps (company 96,800.00, coverage partial)
.venv/bin/python -m app.seed --check-planted   # replay the pack on a throwaway DB and compare with the answer key
```

The planted files are read from this folder by path (`app/seed/planted.py`), so they work from a source
checkout or an editable install. They are not packaged as package data.
