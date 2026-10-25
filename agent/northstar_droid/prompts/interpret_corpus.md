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
3. Check `superseded_by` / `supersedes` on every document. When an older document conflicts with a
   newer one (for example different timelines for the same project), surface the conflict and say
   which document is current and why. Do not merge them silently, and do not let an older timeline
   leak into the current signal's summary.
4. `record_signal` for each relevant finding:
   - Every citation quotes the stored `content` of a specific document version EXACTLY. Copy the
     characters; keep line breaks that are inside the quote; include `char_start`/`char_end` computed
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
