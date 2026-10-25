# Verification evidence

Reports and logs preserve the review sequence, including initial failures and later corrections. The final accepted code is identified in [the verification record](../verification.json); [the final rereview](final-rereview.md) records the scoped approval. Historical failures are not current failures.

Files under `final-fix-before/` are before-fix snapshots for reproducing the reported defects, not application modules. Trailing whitespace was removed from the two copied failure logs (`final-fix-red.txt` and `final-fix-first-green.txt`) for repository formatting; their messages and results are unchanged. Original raw logs remain in the local coordination evidence.
