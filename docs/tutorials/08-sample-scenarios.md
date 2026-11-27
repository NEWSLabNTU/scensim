# Tutorial 8: Sample scenarios

**Goal**: draw 200 concrete variants of a pedestrian dart-out scenario from a parameter
distribution, verify each variant's sample record, reproduce the draw from its seed, and
draw a weighted variant set from an importance proposal.

```
$ scensim-sample draw walker_dartout_dist.xosc -n 200 --seed 7 -o samples.jsonl
scensim-sample: 200 records to samples.jsonl, 2 draws rejected
  2 x van_offset > 0.5
```

## You will learn

- what a sample record holds, and why it is sufficient to rerun a variant on any executor;
- that a seed determines a draw bit for bit;
- how a constraint rejects draws, and how an importance proposal weights them;
- how to ask whether a scenario compiles for a batch executor.

## Before you start

- A scensim source checkout, built as in
  [Install, from source](../getting-started/install.md), with `install/setup.bash` sourced.
  The sampler is pure Python. This tutorial needs no simulator and no GPU.
- About 5 minutes.

```bash
cd ~/scensim/src/scensim_sampler/examples/walker_dartout
```

The scenario is CS1 of the scenario descriptions: a pedestrian steps out from behind a parked
van. `walker_dartout.xosc` declares the parameters. `walker_dartout_dist.xosc` gives their
joint distribution, through the model file `models/walker_dartout.yaml`. The model's values
are invented for illustration. They are not fitted to data.

## 1. Draw

```bash
scensim-sample draw walker_dartout_dist.xosc -n 200 --seed 7 -o samples.jsonl
head -n 1 samples.jsonl | python3 -m json.tool
```

Each line is one sample record:

- `values` holds the parameter values, and `derived` names the values computed from others
  (`trigger_distance = ego_speed * ttc_entry`);
- `category` and `cell` place the variant in the risk taxonomy;
- `seeds` holds the scenario's, the world's and each pilot's seed;
- `scenario` and `base` give the files' SHA-256, so that a record names exactly what it was
  drawn from.

**Check**: the command reports 200 records and 2 rejected draws, both by the constraint
`van_offset > 0.5`. The first record's `category` is `R2.walker_crossing.dart_out`.

## 2. Verify and reproduce

```bash
scensim-sample check samples.jsonl --scenario walker_dartout.xosc
scensim-sample draw walker_dartout_dist.xosc -n 200 --seed 7 -o again.jsonl
cmp samples.jsonl again.jsonl && echo identical
```

**Check**: `200 records, 0 problems`, then `identical`. Each record's id is a hash of its
content, so identical files mean identical variants.

## 3. Weight toward the critical region

`walker_dartout_importance.xosc` draws the same parameters from a proposal concentrated on
short entry gaps (`proposals/near_ttc_short.yaml`). Each record's `weight` is the base density
over the proposal density at its values.

```bash
scensim-sample draw walker_dartout_importance.xosc -n 200 --seed 7 -o weighted.jsonl
python3 -c "
import json
w = [json.loads(l)['weight'] for l in open('weighted.jsonl')]
print('n_eff/n', round(sum(w) ** 2 / sum(x * x for x in w) / len(w), 3))"
```

**Check**: every record has a `proposal` and a positive `weight`, and `n_eff/n` is 0.131. The
proposal spends 200 draws where failures are likely, at the cost of an effective sample size
of about 26.

## 4. Ask whether it compiles for a batch

```bash
scensim-sample compilable walker_dartout.xosc --ego seats
scensim-sample compilable ../cases/cs1_walker_gap_acceptance_k11c.xosc
```

**Check**: the first scenario compiles if the batch provides a slot camera for its
illumination knob and SSv2's default traffic behaviour. The second compiles with the ego
replaced by the batch's policy and its walker as a batched behaviour model. Tutorial 9 runs
the second.

## What happened

A distribution file and a model turned into records that are self-contained. Each record
names the files it came from by hash, its values, its cell and every seed. Any executor that
reads the record can therefore rerun the variant: a CARLA or Isaac seat, a batch, or another
simulator. Rejection sampling enforced the constraints. The proposal changed where the draws
fell without changing what they estimate: the weights restore the base distribution.

## Exercises

1. **Easy.** Draw with `--seed 8`. Check: `cmp` now reports a difference at the first record.
2. **Medium.** Pass `--knob speed_limit=8.0`. Check: more draws are rejected, by
   `ego_speed <= 1.2 * speed_limit`, and no record's `ego_speed` exceeds 9.6.
3. **Open.** Feed `samples.jsonl` to your own simulator through the Python interface in the
   sampler's README. Check: your runner reads `values` and `seeds` without scensim.

## If it does not work

| Symptom | Fix |
|---|---|
| `scensim-sample: command not found` | source the checkout's `install/setup.bash` |
| `check` reports a hash mismatch | the scenario or model file changed after the draw: draw again |
| `a fitted model must give name, dataset, version and licence` | a model file of your own needs its `header` |

## Next

[Tutorial 9: search for failures](09-search-for-failures.md).
