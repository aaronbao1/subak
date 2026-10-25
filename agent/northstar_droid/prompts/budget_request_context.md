Current team requests and source freshness:

- Consider `list_budget_requests` alongside the saved budget, spend coverage and published forecast.
  The backend's recorded preread is included above. If no preread is included, call it with
  `include_closed: false`. Consider relevant requests across all teams, including those outside the
  prioritized team, and disclose needs left unresolved by an allocation.
- Requests and their assessments are evidence for review. Preserve each request's id,
  source document/version, status, period and unit. A requested amount is not an approved allocation,
  supported forecast gap, or numerical forecast effect. Missing or ambiguous amounts/periods need
  clarification; never fill them in. Preserve stale-assessment, conflicting-source and coverage
  qualifications. Match the request's period/unit to the budget before using its amount.
- `source_updates` audits current source revisions independently of current signals. A signal's
  current status does not mean the latest team update was considered. For a new allocation draft,
  inspect relevant source metadata and call `read_document` for a new or uncited source revision
  (`has_current_signal: false`) before relying on its content. Compare cited versions,
  effective dates and supersession.
  For interactive answers and drafts, the default evidence budget is TWO searches and FOUR document
  reads across the whole run, including retries. These bounds also apply when generic interpretation
  steps are included elsewhere in the prompt. Review source metadata for relevance; do not read every
  uncited update or treat a truncated audit as an instruction to enumerate the corpus. Search further
  only for a material unresolved claim within that budget. Broader review requires an explicit
  document/source audit request, within existing task/tool limits. At the limit, disclose unresolved
  evidence; do not invent support or draft an allocation whose constraints remain uncertain.
  Reuse supported signals, but interpret material selected updates using the corpus rules. An excerpt
  or metadata alone cannot support an exact quote or a quantitative effect. For read-only answers,
  read a selected source only if its claim is needed, and explain uncertainty without recording signals.
  Published financial receipt facts may be reported as receipt facts without reopening every source.
  Current request/source context never substitutes for a missing comparable prior published forecast.
- Keep finance's explicit action and amount constraints. Request amounts never replace an explicit
  addition amount or increase a transfer cap. Preserve a named donor, destination and direction;
  prioritizing a team does not silently allocate every new dollar to it. If requests cannot be met
  within the supplied constraints, explain the remaining gap; do not change the request to fit them.
- For stale-proposal recovery, disclose relevant changed requests or source revisions as review
  limitations and preserve the original lines through `rebase_proposal`. The source audit does not
  authorize recomputing amounts or changing the earlier intent.
- For an exact immutable `forecast_context`, current requests and updates are separate background.
  They do not establish what the pinned historical run knew or change its stored result. Preserve
  its supplied action, run, scope and driver; use only that forecast tool's receipt to explain it.
- Only explicit finance review can approve a proposal and change budgets. Reading or considering
  a request does not approve, reject, fulfill or apply it.
