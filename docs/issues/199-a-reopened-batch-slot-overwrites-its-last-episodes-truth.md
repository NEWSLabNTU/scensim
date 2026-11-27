# 199: a batch slot reopened after its episode ended overwrites that episode's truth export

**Status:** open; the fix rides in 092 K11f's landing (241, 2026-11-27, for 133). **Severity:**
low. No landed export is affected (below); a future caller that resets finished slots would lose
every episode but each slot's last, silently. **Found:** 2026-11-27, 241, by K11f's
random-trajectory test (`test_score.py`), which compares the batch's in-batch score with
`slot_outcomes` on `TruthRecorder`'s export of the same steps.

## What happens

`scensim_batch.truth.TruthRecorder` numbers each slot's episodes. `begin(obs, mask)` starts an
episode for the slots in `mask`, and moves a slot's episode number on only when the slot is
still open:

```python
for k in torch.nonzero(mask).flatten().tolist():
    if self.open[k]:
        self._close(k, len(self.rows) - 2, "running")
        self.episode[k] += 1
```

A slot whose episode ended by its outcome was already closed in `record()`, and its number was
not moved on. When `begin` reopens it, the new episode takes the same number. `write()` then
writes both episodes to the same `slot_<k>_ep<e>/`: the second overwrites the first. The export
holds one episode fewer and nothing says so.

## Effect on landed results

None. Every caller begins once, at the reset (`search_run.py`, `agreement_run.py`,
`test_storyboard.py`), and closes slots only by their outcome or at `write`. So no slot is ever
reopened in K10's, K11c's, K11d's or K11e's exports, and their episode counts and outcomes stand.
K11f's check 3 reads those exports unchanged.

**Who it would hit:** the first caller that resets finished slots and keeps recording, the
normal loop of a batch that runs more episodes than slots, such as an RL evaluation or a search
generation larger than the slot count.

## The fix

`begin` moves the episode number on for any slot that has had an episode, closed or open, so
each episode keeps its own directory. K11f's `ClosestGap` numbers episodes the same way. The test
comes first: a slot closed by its outcome and reopened by `begin` must give `slot_k_ep0` and
`slot_k_ep1`, both complete, each with its own frames.
