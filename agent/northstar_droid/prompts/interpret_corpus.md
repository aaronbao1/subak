Interpret the company corpus for the current planning period.

1. `search_corpus` with an empty query to list every document, then `read_document` each one. Do not
   rely on a search snippet; quote only from the full `content` returned by `read_document`.
2. For each document decide what is planned or changing, which team/project it concerns, when it
   applies, and how certain it is. Classify the document before recording anything:
   - approved plan or approved update (`plan_status` approved/active) -> can back a `current` signal;
   - older version or document that a newer one supersedes -> `superseded`;
   - two current documents that disagree with no supersedes link -> `conflicting` on both, and say
     that finance has to resolve it;
   - Slack/email brainstorm, draft, "just an idea", "not approved" -> `informal`;
   - a plan marked cancelled, or text saying the work is cancelled/stopped -> `cancelled`.
2b. Decide the scope of each finding:
   - A document with `person_tags`, or one that names an individual whose own work changes (a
     manager deferring someone's task, a person switching model or tool, someone out of office, a
     new joiner): call `list_people` once and record `scope: "person"` with those people's ids in
     `person_ids`. All of them must be on one team; `team` may be omitted (the backend derives it).
     Only use ids of people the cited text actually names. Never infer a person who is not named.
   - A company-wide announcement that affects every team (for example a new default model): record
     `scope: "company"` with `team` null and no `person_ids`.
   - A team plan or team note stays `scope: "team"` with no `person_ids`.
   - Set `signal_kind` to the one that says why usage moves:
     - `project_deferred`: work is pushed back (e.g. "stay on the design doc longer");
     - `project_accelerated`: work is moved earlier or expanded into the current period;
     - `model_change`: moving to a different model or model tier;
     - `tool_change`: moving between tools or billing paths (seat to API, one assistant to another);
     - `out_of_office`: away for given dates;
     - `onboarding`: a new person, seat or key becomes active;
     - `steady`: work continues at the current pace.
     Leave it out when none fits (for example an informal idea).
   - Give every signal a short `title` (at most 120 characters) that names who and what.
3. Check `superseded_by` / `supersedes` on every document. When an older document conflicts with a
   newer one (for example different timelines for the same project), surface the conflict and say
   which document is current and why. Do not merge them silently, and do not let an older timeline
   leak into the current signal's summary.
4. `record_signal` for each relevant finding:
   - Use flat tool arguments, not a nested `signal` object. Required fields are `summary`,
     `change_type`, `status`, `uncertainty`, and `citations`. `change_type` must be exactly:
     `expansion` (more work/usage), `reduction` (less), `continuation` (steady), `timing_shift`
     (a changed schedule), or `other`. Never send `increase` or `decrease`.
   - A citation input has only `document_id` and `quote`, optionally both `char_start` and `char_end`.
     Do not copy response-only `version`, `doc_key`, `title`, citation `id` or currency fields into it.
     The document id already identifies the exact stored version. Prefer omitting both offsets;
     the backend locates the exact quote and returns verified offsets and version metadata.
   - Every citation quotes the stored `content` of a specific document version EXACTLY. Copy the
     characters; keep line breaks that are inside the quote. If offsets are provided, compute them
     from that same text. Prefer one or two short complete sentences per citation. The backend
     rejects a quote that is not verbatim; if that happens, re-read the document and copy again.
   - Status `current` only for signals backed by a current, non-cancelled document. Record the older
     timeline as `superseded` first, then pass its id as `supersedes_signal_id` on the newer signal.
     Informal ideas are `informal`; cancelled plans are `cancelled`; unresolved disagreements are
     `conflicting`.
   - A timing shift cites both the new wording and the older wording it replaces.
   - `uncertainty` is required: say what the documents do not establish (exact token volumes, costs,
     dates, approval). Never put a number in a summary that is not in the cited text.
5. Finish with a short summary: the documents you relied on, the ones you did not and why
   (superseded, informal, cancelled), every conflict you found and how it resolves, and the
   limitations (what the corpus does not say). Recording signals changes no budget; say so if asked.
