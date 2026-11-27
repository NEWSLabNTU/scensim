# 200: `scensim-sample coverage` crashes on a JSONL row that names its record by id

**Status:** fixed in 092 E1a's landing: the test came first, then the check in
`coverage.outcomes_from_jsonl` (139, 2026-11-28). **Severity:** low. The report was never wrong,
because the command stopped before reporting. **Found:** 2026-11-28, 139, by E1a's coverage
example, on the output of the search runner (`search_run.py`).

## What happens

`coverage.outcomes_from_jsonl` reads `{record, outcome}` rows. It checked that both keys were
present but not what `record` held. A search runner's `outcomes.jsonl` names each record by its
id, a string, so the row passed the check. `report()` then indexed the string:

```
File ".../scensim_sampler/coverage.py", line 257, in <setcomp>
    observed = sorted({r["category"] for r, _ in items})
TypeError: string indices must be integers
```

The traceback names neither the file nor the row, nor what was expected.

## The fix

A row whose `record` is not an object is now refused with its file and line, and the message
names what is expected:

```
scensim-sample: outcomes.jsonl: line 1: {record, outcome} with the sample record itself,
not str 'ff0149fd6ed25905'
```

The test is `test_coverage.py`'s
`Inputs.test_a_row_naming_its_record_by_id_is_refused_with_the_shape_expected`. To report on a
search stage, join its records to the runner's outcomes first. The sampling examples'
`join_outcomes.py` does this (docs/tutorials/10-coverage.md).

## Effect on landed results

None. No landed coverage report read a runner's outcomes, and K11's tests build their
`(record, outcome)` pairs in memory (`test_search.py`).
