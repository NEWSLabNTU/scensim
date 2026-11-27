# Tutorial 9: Search for failures

**Goal**: estimate how often an automatic emergency brake hits a pedestrian who steps out from
behind a parked van, when failures are too rare to find by drawing at random. The tool is an
adaptive search that runs each generation of variants in a batch on the CPU.

```
$ scensim-sample search report search
search e1_cs1_straight: done, stopped: the level reached the threshold
  ...
  failures 74 of 200: rate 0.0265 (se 0.00521), interval [0.0163, 0.0367] ...
```

## You will learn

- how the cross-entropy method moves a proposal toward the failure region;
- why the estimate comes from a fresh stage, and how its interval is read;
- what makes a score searchable;
- that a failure found in the batch is a sample record, which reruns exactly.

## Before you start

- [Tutorial 8](08-sample-scenarios.md): sample records, weights and seeds.
- The scensim source checkout of Tutorial 8, with PyTorch importable (`python3 -c "import
  torch"`). No GPU is needed.
- About 5 minutes. The search took about 30 s on a 32-thread workstation.

```bash
cd ~/scensim/src/scensim_examples/sampling
mkdir -p runs
```

The directory holds:

- `cs1_walker_search.xosc`: the scenario;
- `cs1_search.yaml`: the search;
- `straight_world.json`: the world;
- `make_straight_world.py`: the script that wrote the world.

**The scenario.** An ego approaches at `ego_speed`. A walker waits behind a van until the ego's
time to the crossing falls to `ttc_entry`. It then decides whether to take the gap, through a
published gap-acceptance model.

**The ego.** It is a point mass braking on time to collision (`aeb_ttc`), an invented pilot.

**The world.** It is a straight three-lane road, so no map data is needed.

The base distribution of the five searched variables is invented. One of them, `accept_u`, is
the walker's own decision draw.

## 1. Start the search

```bash
scensim-sample search init cs1_search.yaml -o search
```

The command draws generation 0, 200 records, from the base distribution and writes
`search/g0.jsonl`.

**Check**: the command names `search/g0.jsonl` and says what to run next.

## 2. Run each generation, then let the search draw the next

```bash
stage=search/g0.jsonl
while [ -n "$stage" ]; do
  run=runs/$(basename "$stage" .jsonl)
  python3 ../../scensim_batch/scripts/search_run.py --records "$stage" \
      --scenario cs1_walker_search.xosc --world straight_world.json \
      --margin-k 1.0 --out "$run" > "$run.json"
  stage=$(scensim-sample search next search --outcomes "$run/outcomes.jsonl" \
      | grep -o 'search/[a-z0-9]*\.jsonl' | tail -1)
done
```

**`search_run.py`** runs one generation as one batch, one slot per record. Each record gets a
score: the closest gap between ego and walker, in metres. A score of 0 or less is a contact,
which is a failure.

**`search next`** reads the scores. It refits the proposal to the elite (the 10 % with the
lowest scores) and draws the next generation, until the elite's level reaches 0. It then draws
a **fresh stage** from the final proposal, and the estimate comes from that stage alone.

**Check**: the loop ends by itself after a few generations. `runs/` holds `g0` up to about
`g6`, and `fresh`.

## 3. Read the estimate

```bash
scensim-sample search report search
```

**Check**: the report says `stopped: the level reached the threshold`. The level falls from
about 1.0 at g0 to 0 by g6. The fresh stage has 74 failures of 200: a rate of 0.0265, with an
interval of [0.0163, 0.0367] and n_eff 24.

The rate is the base distribution's failure probability. Each fresh record's weight (base
over proposal, capped at 10) corrects for having drawn where failures are frequent. The
interval is approximate. The exact upper bound below it is loose, because it charges every
failure the largest weight.

## 4. Rerun one failure

```bash
python3 -c "
import json
for o in open('runs/fresh/outcomes.jsonl'):
    o = json.loads(o)
    if o['outcome']['failed']:
        print(o['record']); break" > one.txt
grep -F -f one.txt search/fresh.jsonl > one.jsonl
python3 ../../scensim_batch/scripts/search_run.py --records one.jsonl \
    --scenario cs1_walker_search.xosc --world straight_world.json \
    --margin-k 1.0 --out runs/one > runs/one.json
```

**Check**: the one row of `runs/one/outcomes.jsonl` has the same score, to the last digit,
as that record's row in `runs/fresh/outcomes.jsonl`. The record's values and seeds determine
the run.

## What happened

The search is importance sampling with a proposal that it learns. Each generation moved the
proposal toward lower scores until the elite reached contact. The fresh stage then measured
the rate under that proposal and reweighted it to the base.

**What makes it searchable.** The search advances only if the score orders the draws by how
near they came to failing. Most draws end with the walker waiting, at a similar gap whether
it nearly went or not. Two changes from roadmap 092's earlier Town01 searches (K11c, K11d)
give the score an order:

- `accept_u`, the walker's decision draw, is searched as a variable;
- the score is sloped on the waiting branch (`--margin-k 1.0`): a walker that waited adds the
  margin by which it declined, in metres per logit.

With neither change, the elite's level stays near 0.55 here for 13 generations, as K11c's did.
With `accept_u` alone, it stays near 0.55 for six generations before reaching 0. With both,
it falls from 1.0 to 0.65 by g2 (K11e).

**The runner is interim.** `search_run.py` stands in for the batch command `scensim bench`. When
that command exists, this step will use it.

## Exercises

1. **Easy.** Change `seed: 11` to `seed: 12` in `cs1_search.yaml`, remove `search` and `runs`,
   and run again. Check: another estimate and interval. Compare the two intervals.
2. **Medium.** Run step 2 without `--margin-k 1.0`. Check: g0 to g5's levels stay near 0.55,
   and the level reaches 0 at g6.
3. **Open.** Replay the fresh stage's failures on a CARLA seat with `scensim run --replay`
   (Tutorial 1's testbench, on Town01). Check: whether they still fail there is the
   batch-to-seats gap.

## If it does not work

| Symptom | Fix |
|---|---|
| `ModuleNotFoundError: torch` | install PyTorch for the system Python; a CPU build suffices |
| `<dir>: not empty` from `search_run.py` | a generation was run twice: remove `runs/<stage>` and run step 2 again |
| `cs1_search.yaml: changed since the search started` | the spec was edited during a search: start again in a new directory |

## Next

[Tutorial 10: coverage](10-coverage.md), which reports what this search did and did not
cover.
