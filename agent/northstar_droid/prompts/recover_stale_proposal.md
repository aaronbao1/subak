Stale-proposal recovery for proposal `{proposal_id}`.

Finance tried to approve this proposal and the backend refused with 409 `stale_proposal`: it was
drafted against an older budget version, and the budget has changed since (another decision was
applied). Nothing from it was applied. Your job is to explain what changed and offer a rebased draft.
You cannot approve or apply it; finance has to review the new draft from scratch.

1. Call `rebase_proposal` once with `proposal_id` = `{proposal_id}` and a short `rationale` note:
   why it is rebased (the approval was refused as stale) and that the lines are unchanged. The tool
   keeps the original rationale after your note. Do not call `draft_proposal` for this first.
2. Explain what changed using `stale_context` from the result (or from `details.stale_context` if the
   call is refused):
   - the original's `base_version` and the `current_version`;
   - each team whose allocation changed (`changes`: at_base -> now) and the envelope total before and
     now; say whether the envelope grew (an addition was applied) or stayed the same (a transfer);
   - each decision in `decisions_since_base`: which proposal, `addition` or `transfer`, its lines, who
     applied it and the version step.
3. If the rebase succeeded, report the new proposal from `proposal`: its id, that it was rebased from
   `{proposal_id}` (`rebased_from_proposal_id`), `addition` or `transfer`, its lines, before -> after
   per team and envelope on the CURRENT version, and every backend warning (for example a team pushed
   below its recorded spend). Point out what the combined effect would be if finance approves it on
   top of what was already applied (for example a team that now gets more than the original plan
   assumed). Say it is `pending_review` and needs a fresh finance review; the saved budget is still at
   the current version. Never say it is saved, applied or approved.
4. If the call is refused:
   - `proposal_not_stale`: say the proposal is not stale (give its status and versions) and that
     there is nothing to rebase;
   - `validation_failed`: the same lines no longer fit the current budget. List `details.reasons`
     (for example a transfer source team no longer has the funds). Nothing was created. You may then
     draft ONE fresh proposal with `draft_proposal` on the current `state_version` only if a smaller
     version of the same intent clearly fits; otherwise recommend a new propose_allocation run;
   - anything else: report the code and message; nothing was created.
5. Do not re-interpret the corpus or recompute amounts; the backend computes before/after. Do not
   invent reasons for the earlier decision beyond what `stale_context` shows. End with limitations.
