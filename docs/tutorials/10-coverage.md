# Tutorial 10: Coverage

**Goal**: report what the search of Tutorial 9 covered against the catalogue of a study: which
risk categories have runs, which combinations of conditions were tested, and the failure
rate per cell with its interval.

```
$ scensim-sample coverage fresh.joined.jsonl --catalogue catalogue.yaml
...
2. conditions (t = 2)
R2.walker_crossing.dart_out  2  3  12  25.0%  catalogue
```

## You will learn

- the three layers of a coverage report: categories, t-wise conditions and criticality;
- why a catalogue, not the runs, defines what should have been covered;
- how a weighted rate is reported, and the limit of its interval.

## Before you start

- [Tutorial 9](09-search-for-failures.md), with its `search` and `runs` directories in
  `~/scensim/src/scensim_examples/sampling`.
- About 2 minutes.

## 1. Pair the records with their outcomes

The runner's `outcomes.jsonl` names each record by its id. A coverage report needs the
records themselves, for their category, cell and weight. `join_outcomes.py` pairs them, and
it refuses a stage with a record missing or an outcome without its record.

```bash
python3 join_outcomes.py search/fresh.jsonl runs/fresh/outcomes.jsonl \
    -o fresh.joined.jsonl
```

**Check**: `200 records joined to fresh.joined.jsonl`.

## 2. The report without a catalogue

```bash
scensim-sample coverage fresh.joined.jsonl
```

**Check**: layer 1 lists one category, `R2.walker_crossing.dart_out`, as covered. Layer 3
gives the cell `illumination=day,occluder=van,surface=dry` a rate of 2.7 % [1.6 %, 3.7 %],
marked weighted with n_eff/n 0.12: the search's estimate of Tutorial 9.

Without a catalogue, the report can judge the runs only against the levels the runs
themselves contain, so every condition it knows of appears covered.

## 3. The report against the study's catalogue

`catalogue.yaml` declares what a study of dart-outs means to cover:

- two categories;
- for the dart-out, two levels each of illumination, surface and occluder;
- pairwise (t = 2) combinations.

```bash
scensim-sample coverage fresh.joined.jsonl --catalogue catalogue.yaml --json cov.json
```

**Check**: layer 1 marks `R1.rear_end.lead_brakes` as `NO`, with 0 runs. Layer 2 covers 3 of
the dart-out's 12 level pairs (25 %), and it lists the nine missing, for example
`illumination=night, occluder=van`. `cov.json` holds the same, as `scensim.coverage/1`.

## What happened

**What the search established.** It estimated one rate precisely, in one cell, under its base
distribution. The catalogue shows how little of the study that is. The search has no runs at
night, on a wet surface or without the van, and none in the second category.

**The layers.** Layer 2 counts level pairs, not cells. A suite that covered all 12 pairs could
still leave some of the eight cells without runs, and with them their rates.

**The interval.** The weighted interval is approximate. Under heavy weights it covers the true
rate less often than its nominal 95 %: 0.61 to 0.94 in the sampler's measurements. For that
reason the report prints n_eff/n beside it.

## Exercises

1. **Easy.** Add `exposure: {R2.walker_crossing.dart_out: 1, R1.rear_end.lead_brakes: 3}` to
   the catalogue. Check: `overall: refused (no rate for R1.rear_end.lead_brakes (no runs))`.
   An exposure-weighted rate needs every category's rate.
2. **Medium.** Draw Tutorial 8's 200 records (`walker_dartout_dist.xosc`, seed 7) and write
   each with an outcome `{"failed": false}` into a JSONL. Run the coverage report on it with
   this catalogue. Check: layer 2 covers 8 of 12 pairs (66.7 %). The four missing pairs all
   have `occluder=none`, which the scenario fixes to `van`.
3. **Open.** Point `scensim-sample coverage` at a directory of `scensim run` results from a
   seat, for example Tutorial 5's suite. Check: the report reads each run's verdict and sample
   record from its run directory.

## If it does not work

| Symptom | Fix |
|---|---|
| `line 1: {record, outcome} with the sample record itself, not str ...` | the input is the runner's `outcomes.jsonl`: join it first (step 1) |
| `N records without an outcome` from `join_outcomes.py` | the stage's run was interrupted: rerun that stage |

## Next

[Tutorial 1](01-first-drive.md) runs a scenario on a seat. A seat is where a batch failure is
checked against a full simulator and autopilot.
