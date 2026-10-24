Interpret the company corpus for the current planning period.

1. `search_corpus` with an empty query to list every document, then `read_document` each one.
2. For each document decide what is planned or changing, which team/project it concerns, when it
   applies, and how certain it is. Keep these distinct: an approved plan, an update to a plan, an
   informal suggestion (Slack/email brainstorm), and anything cancelled.
3. Check `superseded_by` / `supersedes` on every document. When an older document conflicts with a
   newer one (for example different timelines for the same project), surface the conflict and say
   which document is current and why. Do not merge them silently.
4. `record_signal` for each relevant finding. Every citation quotes the stored `content` of a specific
   document version EXACTLY (copy the characters; include char_start/char_end from the text). Use
   status `current` only for signals backed by a current document; record the older timeline as
   `superseded` (and pass `supersedes_signal_id` on the newer signal), informal ideas as `informal`, cancelled plans as `cancelled`.
   `uncertainty` is required: say what the documents do not establish.
5. Finish with a short summary that names the documents you relied on and the one you did not.
