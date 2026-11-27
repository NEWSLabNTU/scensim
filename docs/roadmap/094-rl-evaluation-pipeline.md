# Phase 094: A real RL pipeline, measured

Train real policies end to end on phase 092's components, and measure two things: the
**throughput** of the pipeline, and the **learning efficiency** of training on it. Then
evaluate the trained policies on seats, where an autopilot is evaluated today. The pipeline
is built from a working reference project, not invented.

**Status**: planned 2026-11-21 (user: "After you finish the infra, build and run a real RL
pipeline for evaluation to measure the throughput and the RL learning efficiency. I suggest
to find a working project or take it for ref."); revised the same day to run stock
WheeledLab and ours side by side (user: "run both stock WheelLab and ours for comparison.
Measure the efficiency on both sides."). Starts when 092's K2 (the Isaac Lab adapter)
reaches K2.2; steps P0 and P1 need no scensim component and start earlier.

**Depends on**: 092 S1 (sample record), S2 (compilable subset), S3 (batched control
component), S4/K4 (truth stream), K1 (sampler), K2 (Isaac Lab adapter), K3 (replay), K7
(coverage report); 091's RoboRacer field and car.

## References

| Project | What it is | What we take |
|---|---|---|
| [WheeledLab](https://github.com/UWRobotLearning/WheeledLab) ([arXiv 2502.07380](https://arxiv.org/abs/2502.07380)) | Isaac Lab tasks for 1/10 wheeled robots (MuSHR, and an F1TENTH drift task without a published curve), drifting, elevation and visual navigation, trained massively parallel and run on real cars | **the reference pipeline**: the stock side of every comparison: its tasks, rewards, PPO settings and learning curves, ported to Isaac Lab 3.0.0 / Isaac Sim 6.2, against the same task built on our components |
| [CaRL](https://github.com/autonomousvision/CaRL) ([arXiv 2504.17838](https://arxiv.org/abs/2504.17838), CoRL 2025) | PPO planning policies in CARLA and nuPlan with a reward built on route completion alone, scaled to 300 M samples on one 8-GPU node | **the driving reward and the evaluation discipline**: route completion with multiplicative infraction penalties, which keeps PPO stable at large mini-batches; scores on a fixed route benchmark |
| [GPUDrive](https://arxiv.org/abs/2408.01584) (ICLR 2025) | multi-agent driving on Madrona, over 1 M simulator steps/s; PPO at about 30 M steps of experience per hour on a consumer GPU | **a throughput reference** for what training (not only simulation) reaches on one GPU |
| [f1tenth_gym](https://github.com/f1tenth/f1tenth_gym) | CPU lidar racing environment with PPO baselines | **a low-fidelity baseline**: the same lidar task on a 2D simulator, for the fidelity/throughput trade-off |

## Two sides, measured the same way

Every task runs on **both sides**, and both are measured with the same harness:

- **Stock**: WheeledLab with the smallest port to Isaac Lab 3.0.0 and Isaac Sim 6.2, on the
  NEWSLabNTU fork (branch `isaaclab-3.0`, upstream's base commit named). Its unmodified form
  was dropped on 2026-11-21: Isaac Sim 4.5 does not support the RTX 5090, and Isaac Sim 5.0 and
  5.1 crash at renderer start on driver 610 (241), so the only host able to run it was 139, and
  the user chose to move every host to 6.2 and remove 5.x instead (user: "switch to Isaac Sim
  6.2 on all agents. Remove old 6.1 and 5.0"). The port's every change is listed in the fork,
  so the version's effect is described, not measured.
- **Ours**: the same task built from scensim's components: the car as a spec and its rig,
  the field, the episode as a compiled scenario with sampled records, the control component
  through the batched form, truth per slot, through K2's environment. Rewards, observations,
  actions and the PPO settings are copied from stock.

Fairness rules, for every comparison:

- the same host and GPU, checked idle of other jobs before each run; the same driver;
- the same number of environments, iterations, seeds, PPO settings and network;
- logging reduced to the same scalars on both sides; the first iterations (warm-up,
  compilation) reported apart, not in the rates;
- the car's values equal on both sides: ours uses a spec written from stock's MuSHR asset
  (geometry, mass, wheels, actuators), and any value stock lacks is named, not invented;
- runs alternated between sides, not all of one then all of the other.

Which engine "ours" runs on shapes every rate comparison (092 K2.2, batch-executor.md section
5). Engine A, N copies of aib's PhysX vehicle (seats' car), is CPU physics by nature: PhysX's
vehicle constraints are not GPU-compatible, and its direct-GPU pipeline refuses them. Only
engine B, an articulation car like WheeledLab's, runs on the GPU pipeline. So a throughput
comparison with stock is B against stock; A is reported as what seats fidelity costs, never
as ours' rate.

**The tyre's 1.154 (issue 108).** Every aib PhysX vehicle before issue 108's fix had 1.154 times
its spec's grip. PhysX's default tyre load filter put it there, and aib.tyre_friction's
FILTER_GRIP now divides it out. 094's runs stay on their pinned pre-fix aib so that P4's rows
compare on one plant (133, 2026-11-23): P1, P4 ours seeds 3 to 5, 139's ECU-B and P2 row (b),
118's row (a) seed 5, and 139's engine A reruns after issue 113. Engine A is aib's PhysX vehicle,
so its numbers carry the 1.154. Engine B (an articulation car) and stock do not use PhysX's
vehicle tyre. A 094 number cited next to a post-108 Isaac result names its aib pin and the
factor.

### An exclusive GPU (found 2026-11-21, 241)

A benchmark needs a GPU no other process is using. Idle CPUs are not enough. On 241, another
user's training job held GPU0 at 100 %. A one-element kernel plus a device synchronisation
then took 2.32 ms at the median, against 0.008 ms on a free GPU, because every synchronising
call waits for the other context's time slice. Isaac Lab's articulation step makes several
synchronising tensor calls per physics substep: the actuators' `set_dof_actuation_forces`,
`set_dof_position_targets` and `set_dof_velocity_targets`, the joint-state reads, and the
events' root writes. Probed at 256 envs, these took 2.3 to 4.6 ms each, `sim.step` 13 ms and
`env.step` 155 ms. The drift task ran at about 180 ms per env step, flat from 64 to 1024 envs
(about 310 samples/s at 64), roughly 100 times slower than it should. On the same GPU at the
same time, Isaac Lab's Cartpole (`Isaac-Cartpole-Direct`, `scripts/benchmarks/training.py`)
still made 86,374 samples/s at 4096 envs, because it makes few such calls. py-spy put 74 % of
the drift run in `env.step`, 38 % in the actuator setters alone. The physics was on the GPU
throughout: `sim.device` cuda:0, PhysX, warp arrays on cuda:0.

So the harness's launcher (`wheeledlab_bench.launch`) probes the kernel-plus-sync latency
before a run, and refuses above 0.05 ms unless `--allow-shared` is given, which marks the run
as a smoke. It records the probe in the run's settings and, every few iterations, in the CSV
(`sync_p50_ms`), beside the host's load and the GPU's other processes. The probe can pass on
a GPU whose other user is busy only in bursts, so a measurement also gives `--require-idle`.

### P3's throughput on a shared GPU: paired runs (fixed 2026-11-22, before the first pair)

The comparison host is 243 (AMD Ryzen 9 9950X, one RTX 5090, driver 580.105.08), whose GPU
carries another user's queue of jobs with gaps of one to five minutes, so no exclusive window
comes. An absolute sweep there would carry that user's load. Adjacent runs of stock and ours
share it, so P3 reports ours against stock as ratios of paired runs, decided as follows before
the first pair.

- Code: the harness at WheeledLab b491b13 for both sides, Isaac Sim 6.2.0 and Isaac Lab 3.0.0.
  Stock is `bench/p1/run_p1.sh`'s sweep point with cameras off; ours is
  `src/scensim_batch/scripts/run_p2.sh`'s sweep at scensim 12e0d1db, rows b and a, starts
  stock. Each run is that script's command for the point, with the gate below in place of its
  own.
- Points: 256, 1024 and 4096 envs with timers sync, and 1024 with timers off, in that order.
- Order: per point, three blocks, each one run of stock (S), ours row b (B) and ours row a (A),
  rotated from block to block (S B A, B A S, A S B), so that each side takes every position once.
- Gate: the continuous CPU gate on every run (`--clean-rows 40 --max-rows 160`, the CPU outside
  the run's own tree within 0.5 x the cores), 20 warm-up iterations. Another context on the GPU
  does not stop a run (`--allow-shared`); it is recorded instead. Each row has the harness's
  `other_procs`, `other_mib`, `gpu_util_pct` and `sync_p50_ms` (every 10 iterations), and a
  side log keeps the full GPU table (pid, type, memory, utilisation) every 2 s, joined to the
  rows by time.
- Measure: per run, the median `samples_per_s` over its clean rows, and each stage's median.
  Per block, the ratios B/S and A/S. Per point, the geometric mean of the three block ratios,
  a 95 % t interval on their logarithms (two degrees of freedom) and their range; the stages'
  costs likewise.
- Contention: the other context slows each synchronising call (above), and the two sides may
  make different numbers of them, so a ratio under a busy GPU is not the exclusive ratio. The
  report gives each ratio with its runs' `sync_p50_ms` and the other context's utilisation, and
  apart for the rows where that context was idle and where it was busy.
- A run that ends with exit 7 (no 40 clean rows in 160) is run once more in its slot; a block
  still missing a run is reported as such, not dropped.

If an exclusive window comes later, the absolute sweep runs as well, as a second table.

### P3's idle-gap table (measured 2026-11-22 and 23, 243)

The paired design above, run only while the other user's GPU processes were idle: a window
opened after five consecutive minutes at 0 % SM in `nvidia-smi pmon`, and each row was counted
only when the harness's per-row sync probe stayed within 0.05 ms (harness WheeledLab f70379b,
`--clean-sync 0.05`). Ours at scensim 9e114870, rows b and a; stock as above. Two windows
(2026-11-22 22:24 to 23:48, 2026-11-23 03:23 to 07:06) completed every point. A run is counted
only when the harness closed it with its clean-row verdict complete. The runs, their GPU log and
the driver with its hashes are on the NAS at `autoveh/logs/094-p3/243/pairs-v4-idle-gap/`.

Throughput, ours over stock: the geometric mean of the three blocks, its 95 % t interval and the
blocks' range.

| point | runs idle | row b / stock | row a / stock |
|---|---|---|---|
| 256 envs, timers sync | 9 of 9 | 0.864 [0.811, 0.921], 0.84 to 0.89 | 0.404 [0.276, 0.591], 0.34 to 0.45 |
| 1024 envs, timers sync | 6 of 9 | not measured idle | not measured idle |
| 4096 envs, timers sync | 9 of 9 | 0.663 [0.476, 0.923], 0.57 to 0.72 | 0.547 [0.321, 0.929], 0.45 to 0.69 |
| 1024 envs, timers off | 8 of 9 | 0.753 [0.707, 0.802], 0.73 to 0.77 | 0.385 [0.256, 0.580], 0.34 to 0.47 |

1024 envs with timers sync is not measured idle: three of its nine runs had rows over the sync
limit (their counted rows were clean, but the run was not idle throughout), its runs' throughput
spread from 8.6k to 64k samples/s, and row b's block ratios from 0.21 to 1.92. A quiet window
would be needed to measure it.

Each stage's cost, ours over stock (the geometric mean of the blocks; timers sync, idle points):

| stage | row b, 256 | row b, 4096 | row a, 256 | row a, 4096 |
|---|---|---|---|---|
| env step | 1.18 | 1.53 | 2.70 | 1.87 |
| physics | 1.06 | 1.20 | 1.19 | 1.08 |
| actions | 0.99 | 1.18 | 10.39 | 8.30 |
| observations | 1.06 | 1.11 | 1.16 | 1.01 |
| rewards | 0.71 | 0.74 | 0.77 | 0.63 |
| terminations | 2.31 | 4.55 | 7.14 | 6.27 |
| resets | 1.72 | 4.45 | 3.42 | 4.50 |
| scene | 1.26 | 1.43 | 1.33 | 1.18 |
| inference | 1.14 | 1.15 | 1.27 | 1.06 |
| update | 1.06 | 1.04 | 1.15 | 1.05 |

The reading: the gap is our per-step Python stages (row a's actions, terminations and resets),
not PhysX, whose cost is within 1.06 to 1.20 of stock's on both rows. Row a's actions are its
control component's step; row b, the component bypassed, costs about stock's there.

Follow-up, named and not started: profile and vectorise terminations and resets, then row a's
component step, and measure again with the same driver (`pairs5.sh`, the idle-gap gate).

### P3's contended table (measured 2026-11-22 and 23, 243)

The same paired design with no idle window: each run started whenever the previous one ended,
under whatever load the other user had on the GPU. A run is counted only when the harness closed
it with its clean-row verdict complete, as above; a run is called busy when any of its rows' sync
probe exceeded 0.05 ms. Two versions of ours: v2 at scensim 4c5d7a7a (139's P3 fixes, before the
optimisations), all four points; v3 at 9e114870 (the idle-gap table's version), 256 and 4096 envs
with timers sync. Stock and the harness (WheeledLab b491b13) as above. The runs and their logs are
on 243's host under `/var/tmp/aeon/p3-243/pairs-v2/` and `pairs-v3/`, each with its `ratios.json`.

Throughput, ours over stock: the geometric mean of the three blocks, its 95 % t interval and the
blocks' range.

| version | point | runs busy | row b / stock | row a / stock |
|---|---|---|---|---|
| v2 | 256 envs, timers sync | 9 of 9 | 0.674 [0.164, 2.764], 0.44 to 1.29 | 0.565 [0.343, 0.930], 0.49 to 0.71 |
| v2 | 1024 envs, timers sync | 4 of 9 | 0.778 [0.140, 4.335], 0.36 to 1.41 | 0.589 [0.230, 1.511], 0.46 to 0.91 |
| v2 | 4096 envs, timers sync | 7 of 9 | 0.619 [0.126, 3.036], 0.33 to 1.19 | 0.747 [0.129, 4.328], 0.40 to 1.61 |
| v2 | 1024 envs, timers off | 6 of 9 | 0.897 [0.317, 2.543], 0.62 to 1.41 | 0.661 [0.162, 2.696], 0.47 to 1.27 |
| v3 | 256 envs, timers sync | 2 of 9 | 1.377 [0.452, 4.199], 0.82 to 1.87 | 0.714 [0.225, 2.270], 0.42 to 0.97 |
| v3 | 4096 envs, timers sync | 3 of 9 | 0.857 [0.684, 1.075], 0.79 to 0.95 | 0.750 [0.587, 0.958], 0.70 to 0.84 |

v2 cannot be read: 26 of its 36 runs were busy, every interval but one spans 1, and stock's own
throughput at 1024 envs swung from 13k to 54k samples/s between blocks. v3 at 4096 envs is the
one reading that holds: row a runs at about 0.75 of stock's throughput (its interval below 1),
and row b cannot be told apart from stock. v3 at 256 envs spans 1 on both rows.

Against the idle-gap table at 4096 envs (row b 0.663, row a 0.547), the contended gap is smaller.
A reading, not a result: the shared GPU slows stock more than ours. Stock's blocks ran at 73k to
80k samples/s here against 102k to 130k in the idle windows, ours at 53k to 69k against 58k to
90k, though the sync probe called six of the nine v3 runs at 4096 envs idle; the probe's 0.05 ms
limit does not see the load that the idle windows' 0 % SM gate excluded.

### Run notes: training on a shared GPU (139's host, fixed 2026-11-24 by 133)

139's GPU0 (an RTX 5090, 32607 MiB) is shared with other users' jobs. The rules for 094's
training runs on it, in place of the per-seed guards before them:

- **Start**: a run starts only when GPU0's total, plus the new run's expected share (about
  3.5 GB for an engine A seed of P4, about 3.1 GB for a P2 seed), stays at or under 26 GB for
  10 minutes, and the host keeps 12 GB of RAM available after it starts. So we do not crowd
  the card.
- **Stop**: one guard (`gpuguard.sh`) over all our runs protects the card from running out of
  memory, which hurts every user of it, not our share of it. When GPU0's total is above
  32000 MiB on two consecutive samples 30 s apart, it stops our youngest run (least elapsed),
  one at a time, re-checking after each. Other users' processes are never touched.
- **Arming**: any guard first reads the value it watches and refuses to arm if its stop
  condition already holds; it says so and waits.

Why, as it happened. Engine A seeds 2 to 5 of P4's ECU row (scensim e178f268) each had a guard
that stopped the seed when GPU0's total passed 26 GB. Another user's jobs took the total to
26.5 to 30.7 GB on 2026-11-24, and the guards stopped seeds 5 and 4 at 03:03 (iterations 4 and 20
of 1500) and seeds 3 and 2 at 03:15 (117 and 171). Those are **guard stops caused by another
user's load, not training failures**: 29 to 36 GB of RAM was available at each stop, and the card did not run out.
Their outputs are kept as `seedN-gpustop` with a STOPPED.txt, not counted, and all four rerun
from scratch. The first replacement guard then stopped P2 row b's seed 2 (scensim 4c5d7a7a,
iteration 1956 of 5000, 12 h in) the moment it armed, at 04:37, with the total already at
31381 MiB from the other user's job (about 24.5 GB of it) and ours (6.8 GB). Two errors: **a rule
error**, the stop line of 31000 MiB set too low, below where one other job plus our runs already
sat (133's); and **arming without a check**, the guard armed without reading the total first
(139's). Seed 2 is kept as `seed2-gpustop` (WheeledLab's `p2-b-stock-seeds-seed2-gpustop`),
not counted, and reruns from scratch, its second rerun after the OOM kill of 2026-11-23.

## Measures

The same on both sides, from one harness (P0):

- **Throughput**: simulator steps/s, and training samples/s end to end, split by stage
  (physics, control component, scenario conditions, resets, observation and transfer, policy
  inference, PPO update); at N = 256, 1024 and 4096 environments; peak GPU memory.
- **Learning efficiency**: samples and wall-clock time to reach a fixed threshold (set from
  stock's published result before training), the final return and task metric, the learning
  curve's area; at least 5 seeds per side, reported with their spread.
- **Cross-evaluation**: each side's trained policy run in the other side's environment, so a
  difference in learning can be told apart from a difference in the task.
- **Evaluation on seats**: every trained policy, from both sides, run on seats (the Isaac
  world server with SSv2, and CARLA by replay) on sampled scenarios, with the coverage
  report's per-cell rates. The gap between batch and seats is a result in itself.

Every number names its hardware, driver, releases and seeds.

### P1's pass bar (scensim's, fixed before training)

The paper (arXiv 2502.07380v2, CoRL 2025) reports no result in simulation: no learning
curve, seed count or spread for the drift task. Its numbers are the real car's: controlled
slip up to 58 deg, about 1.6 m/s on average, and full laps without spinning out, trained with
1024 envs for 5000 epochs on one RTX 3080. The bar below is therefore ours, set from those
numbers. `bench/p1/eval_drift.py` in the fork computes it.

A trained checkpoint runs deterministically for 30 s of sim time in 32 envs, on the run's
own training env config with the out-of-bounds termination (and its reward term) off.
Upstream's play config is not used, because its reset term passes `dist_noise`, which the
reset function does not take, so it does not build. Per env, the script measures:

- laps: the unwrapped angle of the car about the oval's centre, over 2 pi;
- off track: the task's own termination test, at any step;
- spin-out: slip above 100 deg or travel clockwise along the track, for 0.5 s, above
  0.5 m/s;
- peak controlled slip: while on track, not spun out, moving counter-clockwise with v_x above
  0.5 m/s;
- mean speed.

A seed passes when at least 90 % of envs complete 3 laps with neither off-track nor spin-out,
the median peak controlled slip is at least 40 deg, and the mean speed is at least 1.2 m/s.
P1 passes when at least 4 of 5 seeds pass. The learning-efficiency threshold is the first
evaluated iteration at which a seed passes. The checkpoint for the record is one trained on
Isaac Lab 3.0.0 and Isaac Sim 6.2.

### P1's result (2026-11-28, as measured)

**P1 fails its pass bar: none of the five seeds passes at any of its 10 checkpoints (0 of 50), so
P1 has no samples-to-pass.** The bar stays as fixed before training, and P1 is recorded as failed. No
bar was moved after the results (133, 2026-11-28).

The five counted seeds are `seed1rr`, `seed2r2`, `seed3`, `seed4r2` and `seed5r2` (241's STOPS.txt).
Eight other runs were stopped by the memory guard or by /var/tmp's full disk on 11-26. They are kept
and not counted, and each was rerun from iteration 0.

Each run:

- trained at fork fef6385: every start line names it. The clean tree rests on the checkout's reflog
  and an mtime check, because the start lines record no dirty flag;
- used 1024 envs, 5000 iterations, cameras off;
- ran on 241's RTX 5090 (driver 610.57.04), shared with other work;
- used Isaac Sim 6.2.0, Isaac Lab 3.0.0, rsl-rl-lib 5.5.1 and torch 2.11.0+cu128.

The fork's `bench/p1/eval_drift.py` at fef6385 scored the checkpoints on 241's GPU0, on P2's grid
(500 to 4500 by 500, and 4999, `--envs 32 --seconds 30`).

**Completeness, by the records (issue 118): 50 of 50.**

- Each record has the checkpoint asked, 32 envs, 30 s and 32 per-env values of every item.
- Each log has its EVAL line and no traceback.
- Each record's clean share matches the one recomputed from its per-env values.
- The 50 checkpoints hash to the archived runs' copies.
- One evaluation (`seed2r2` at 2000) crashed in Kit before loading its checkpoint and was rerun. The
  crash log is kept.

**Only the clean share fails.** Each seed's best over the grid is 0.844, 0.844, 0.594, 0.750 and
0.781, against 0.9. The slip median meets 40 deg at 44 of 50 checkpoints, and the mean speed is
1.23 to 1.96 m/s at every one.

At 4999, of 32 envs:

| seed | share clean | slip median | laps median (min) | speed | off track | spun |
|---|---|---|---|---|---|---|
| `seed1rr` | 0.812 | 44.1 deg | 6.38 (4.76) | 1.81 m/s | 6 | 2 |
| `seed2r2` | 0.531 | 65.7 deg | 6.23 (2.87) | 1.78 m/s | 13 | 13 |
| `seed3` | 0.562 | 44.4 deg | 6.34 (2.98) | 1.78 m/s | 10 | 13 |
| `seed4r2` | 0.406 | 67.3 deg | 6.11 (2.00) | 1.72 m/s | 12 | 19 |
| `seed5r2` | 0.469 | 62.0 deg | 6.41 (3.64) | 1.77 m/s | 12 | 14 |

**The prediction**, committed before any record (139, 2026-11-27 23:29:56, sha256 06a5c6c5), judged
part by part:

- the mean speed is at least 1.2 m/s at 4999 for all 5 seeds: MET;
- at least one seed fails the clean share at 4999: MET (all five do);
- P1 fails: MET;
- the median of the five slip medians at 4999 is at least 40 deg: MET (62.0).

4 of 4 met. The prediction was weak, informed by P2's rows and by no stock evaluation.

Interpretation, labelled: stock, on Isaac Lab 3.0 and Isaac Sim 6.2, does not reach our bar, and it
misses the same item both P2 rows miss. So P2's "no seed passes" alone does not show ours is worse
than stock.

The records are in the NAS's P1 directory (241's seeds, STOPS.txt, provenance and evals; 139's
prediction, result and scripts).

### P2 against P1 (post hoc, 2026-11-28)

This comparison is **post hoc**: 133 asked for it after P1's result, and none of it was
pre-registered.

- **Groups:** stock is P1's five counted seeds; row a and row b are P2's five v2 seeds each. All three
  use the same eval grid and settings.
- **Hosts:** stock trained and was evaluated on 241's RTX 5090, row a on 118's RTX 4090 and row b on
  139's RTX 5090. A host effect is not separated from a row effect.
- **Interval:** a 95 % percentile bootstrap over seeds. Each group's 5 seeds are resampled with
  replacement, independently, 10000 draws, numpy seed 0, of the difference of seed means
  (ours - stock).
- **Limits:** with 5 seeds the intervals are descriptive, and the 30 per-checkpoint intervals are not
  corrected for multiplicity.

| measure (seed mean) | stock | row a | row b | a - stock | b - stock |
|---|---|---|---|---|---|
| clean share, mean over the grid | 0.548 | 0.511 | 0.359 | -0.037 [-0.177, +0.085] | -0.189 [-0.297, -0.087] |
| best clean share over the grid | 0.762 | 0.738 | 0.544 | -0.025 [-0.100, +0.062] | -0.219 [-0.344, -0.081] |
| clean share at 4999 | 0.556 | 0.675 | 0.394 | +0.119 [-0.025, +0.231] | -0.163 [-0.300, -0.044] |
| slip median at 4999 (deg) | 56.7 | 22.8 | 61.3 | -33.9 [-43.1, -24.1] | +4.6 [-7.2, +16.4] |
| mean speed at 4999 (m/s) | 1.772 | 1.674 | 1.694 | -0.099 [-0.124, -0.069] | -0.078 [-0.111, -0.042] |
| off track at 4999 (of 32) | 10.6 | 9.6 | 15.8 | -1.0 [-3.4, +1.8] | +5.2 [+3.2, +7.6] |
| spun at 4999 (of 32) | 12.2 | 5.2 | 17.2 | -7.0 [-11.4, -1.6] | +5.0 [+0.0, +10.8] |

Per checkpoint, the seed means of stock / row a / row b:

| it | clean share | slip median (deg) | speed (m/s) |
|---|---|---|---|
| 500 | 0.281 / 0.256 / 0.125 | 61.6 / 44.4 / 51.0 | 1.740 / 1.698 / 1.713 |
| 1000 | 0.588 / 0.350 / 0.369 | 60.3 / 37.1 / 51.9 | 1.876 / 1.676 / 1.833 |
| 1500 | 0.644 / 0.450 / 0.419 | 43.9 / 40.1 / 56.5 | 1.893 / 1.644 / 1.801 |
| 2000 | 0.606 / 0.431 / 0.381 | 52.1 / 44.2 / 57.5 | 1.825 / 1.645 / 1.785 |
| 2500 | 0.637 / 0.525 / 0.412 | 51.5 / 37.4 / 59.5 | 1.849 / 1.641 / 1.717 |
| 3000 | 0.631 / 0.600 / 0.356 | 50.9 / 34.4 / 60.6 | 1.825 / 1.664 / 1.716 |
| 3500 | 0.481 / 0.550 / 0.438 | 56.8 / 29.6 / 61.3 | 1.751 / 1.664 / 1.728 |
| 4000 | 0.525 / 0.625 / 0.362 | 58.8 / 24.1 / 60.1 | 1.786 / 1.672 / 1.730 |
| 4500 | 0.525 / 0.644 / 0.331 | 53.2 / 28.4 / 62.1 | 1.773 / 1.632 / 1.682 |
| 4999 | 0.556 / 0.675 / 0.394 | 56.7 / 22.8 / 61.3 | 1.772 / 1.674 / 1.694 |

Reading, post hoc and labelled:

- **Row a** keeps or exceeds stock's clean share from about 3500 on, but by drifting less: its slip
  falls from about 44 deg to 23 deg, while stock's stays at 50 to 60.
- **Row b** drifts as stock does (the slip interval includes 0), but laps cleanly less often (from
  1000 on, the interval excludes 0 at 7 of 9 checkpoints) and leaves the track more.
- **Both rows** are 0.08 to 0.25 m/s slower than stock.
- **Neither row** matches stock on clean share and slip together.

### The relative criterion for drift rows (pre-registered, 2026-11-28)

Proposed by 139, accepted by 133 with two edits (scope, eval host). This criterion was drafted after
seeing P1's and P2's results.

**Scope.** It applies to every drift-task row (P2-type, eval_drift's measures) that has no eval
records when this is committed. P4 is not covered: it is another task, judged by its own rule and its
pre-registered predictions. P1's absolute bar is still computed and reported for every row.

**Reference.** P1's five counted seeds and their frozen checkpoints. A new row uses 5 seeds, the same
grid (500 to 4500 by 500, and 4999) and the same eval_drift settings (32 envs, 30 s, cameras off).

**Eval host.** P1's frozen checkpoints are re-evaluated on each new row's eval host (about 65 min),
and the row is compared against that re-evaluation, which is the gating comparison. The comparison
against the 241 records is reported beside it.

A training-host effect cannot be removed. Where a row trained on another host than the reference
(241's RTX 5090), the result names that as a stated confound.

**Statistic.** A 95 % percentile bootstrap over seeds: each group's 5 seeds are resampled with
replacement, independently, 10000 draws, numpy seed 0, of the difference of seed means
(ours - stock).

**Co-primary measures.** Both must hold for the row to pass:

1. **Clean share:** each seed's mean clean share over the 10 grid checkpoints. Ours passes when the
   interval's lower end is above -0.10.
2. **Drift:** each seed's slip median at 4999. Ours passes when the interval's lower end is above
   -10 deg.

The margins are just under one between-seed SD of stock's measures (0.120 and 11.5 deg).

**Reported, not gating:**

- the clean share at 4999 and the best over the grid;
- the mean speed, off track and spun at 4999;
- the per-checkpoint intervals;
- P1's absolute bar.

**Power, stated.** With 5 seeds a side the intervals are about ±0.1 wide. A row passes only when it
is about equal to stock or better, which makes the test strict, and the 95 % interval limits a false
pass to about 1 in 40.

Applied post hoc to rows a and b for illustration only (it does not count):

- row a fails both measures (-0.177 and -43.1);
- row b fails (1) at -0.297 and passes (2) at -7.2.

## Steps

| Step | What | Owner | Status |
|---|---|---|---|
| P0 | The measurement harness: stage timers around the environment step and the runner's phases, GPU memory, and the learning curve, written to one CSV schema; applied unchanged to stock and to ours. Its own overhead measured and reported | 241 | in progress: `bench/wheeledlab_bench` on the fork's `isaaclab-3.0` (7ea2873), a pip package with no WheeledLab import; hooks Isaac Lab's manager-based env and rsl_rl's PPO by class; refuses a time-sliced GPU. Overhead not yet measured on an exclusive GPU |
| P1 | Stock: the MuSHR drift task (rsl_rl PPO, 1024 environments, the paper's headline task), ported (the NEWSLabNTU fork, branch `isaaclab-3.0`, upstream's base commit named), trained to its published result over 5 seeds; the pass bar fixed from the paper before training. F1TENTH drift afterwards as an extra | 241 | **done: P1 fails its pass bar** (2026-11-28; 0 of 50 checkpoints pass, only the clean share fails; see P1's result above). Before this: ported on upstream a5017ce (5a6861c, c98aa20), trains on Isaac Lab 3.0.0 / Isaac Sim 6.2; `WHEELEDLAB_ENABLE_CAMERAS=0` measures it without upstream's forced cameras (c3f286b); pass bar above. Seeds and sweep wait for an exclusive GPU. **Seeds on a shared GPU** (133, 2026-11-22: samples to pass only): 5 seeds, 3 at a time, on 241's GPU0 (fork fef6385, `/var/tmp/aeon/wl-port/p1-241-gpu0/seeds`), under a memory guard that stops one run when the GPU's free memory falls below 4096 MiB. **Two stops by the guard** (2026-11-23): seed 1 at iteration 1663 (04:48) and seed 2 at iteration 1877 (09:57), each beside two other P1 runs. The guard was to stop its newest run but took the last key of a bash associative array, which is not start order, and so stopped the oldest twice. Both are kept (logs and checkpoints in `seed1` and `seed2`), not counted, and rerun from scratch, not resumed: rsl_rl's checkpoint holds no RNG or environment state, and the env is reseeded on load. The reruns are `seed1r`, then `seed2r`. The guard now stops the run with the least elapsed time (`p1-guard.sh`), and a run it stops is rerun from scratch the same way |
| P2 | Ours, the same task: a MuSHR spec from stock's asset, the field, the drift episode as a compiled scenario with sampled starts, the control component, truth, through K2's environment; stock's rewards and PPO settings. Trained over 5 seeds | swb 139 | in progress (plan approved by 133, 2026-11-22; step 1 and 2 landed 2026-11-22: the spec, sim_vehicle_spec's `dc_motor` drive, undriven and suspension drives and `steer_law: tan`, scensim_batch's DCMotorCfg and tan law; the body's smoke on the GPU, bypassed: 2.07 m/s for 2 m/s asked, 0.83 rad/s at d 0.3): (1) the spec, `scenarios/projects/mushr_drift/vehicles/mushr_nano.yaml`, read from stock's `mushr_nano_v2.usd` (source, commit, licence named; what stock lacks named); (2) sim_vehicle_spec's articulation gains a `dc_motor` drive (Isaac Lab's DCMotorCfg) and a `tan` steer law beside Ackermann's; (3) the episode: stock's oval (straights 0.8 m, line radius 0.8 m) as a polyline world, a 5 s time-up scenario at 50 Hz on 200 Hz physics, stock's plane material; the start a distribution in the compiled scenario (a reference point along the track, position and yaw noise as stock's), drawn again on the device at every reset, each episode its own sample record (seed, reference index, noise) so any training episode replays on seats (P5); env_spacing 0 with filtered collisions, as stock; (4) the task, a ScensimEnv subclass with stock's observations (and their corruption), rewards, curriculum and terminations, and stock's event terms through Isaac Lab's event manager, renamed to our joints and bodies; rsl_rl with stock's PPO settings; (5) two rows: the action through the car's real component (MuSHR's VESC: roboracer_vesc's batch at MuSHR's values, speed mode) and bypassed (rear spin velocity targets v/r on the DC motor, steer tan(δ), as stock); `ideal` a third row only if (a)'s cost needs explaining; 241's wheeledlab_bench gains a DirectRLEnv hook (the same stages and timers, the harness version pinned on both sides). Every difference from stock is named in the table, the renamed event terms among them. Before this: planned (133, 2026-11-21), after 092 K2.2b (engine B), K2.4 and K2.2c (the device-resident path: BatchRun and the control component's torch form on cuda, bit-close to the CPU path; 133, 2026-11-21): a MuSHR spec written from stock's `mushr_nano_v2.usd`, naming its source asset, commit and that asset's licence, any value stock lacks named; its articulation body reproduces stock's joint drives (read in the WheeledLab fork, isaaclab-3.0 a35060c: the throttle an explicit DC motor, `DCMotorCfg` damping 1000, effort 0.25, saturation 1.05, velocity 450; the 2WD variant's rear effort 0.5 and its front wheels passive; the steer a position drive, both front wheels to tan(δ), not Ackermann angles; passive suspension, stiffness 1e8), so both sides are articulations and the named differences are only ours (the control component, the compiled episode, the sampler), and the table says so; the field (stock's plane material) and track (its oval) as the episode's ground; the 5 s episode at 50 Hz (200 Hz physics) as a compiled scenario, sampled starts as stock's; stock's observations, rewards, curriculum and rsl_rl PPO settings through K2's environment. Ours measured two ways: the action through our control component, and the component bypassed (the action straight to the joints, as stock), so the component's cost and its effect on learning are separate numbers. One seed as a contended smoke; 5 seeds and rates wait for an exclusive GPU. **Seeds superseded** (2026-11-22, found by P3's profile, 139): every P2 seed so far (row b's five on 139 at 780921e4 and 761286f9, row a's five on 118 at 1bb4a482 and 12e0d1db) ran the MuSHR at its USD's 32 position and 1 velocity solver iterations, not stock's config's 4 and 0, and without its sleep, stabilisation and rigid-body properties (`MUSHR_CFG`): our spawn read the USD alone. Not stock's physics, so they are kept (139's under `/var/tmp/aeon/p2runs/seeds-b-stock`, 118's under its `p2a`) and not counted, and all ten restart on the fix: sim_vehicle_spec c11ec1d's `body.asset.spawn` (stock's values, named to `MUSHR_CFG`, keyed by the USD attributes they set), applied by scensim_batch's `articulation_cfg` and read back from the stage at the env's start. 243's P3 slots of ours at 12e0d1db are superseded likewise. The body check of batch-executor.md section 5 ran at 4/0 (its script set them) and stands. **A gate-memory incident** (2026-11-23, 139): row b's restarted seeds 1 and 2 (scensim 4c5d7a7a, WheeledLab b491b13, `/var/tmp/aeon/p2runs/seeds-b-v2`) were killed by the kernel's OOM killer at iterations about 3349 and 3364 of 5000, during a full `just build && just test` gate (issue 113's) started on the same 60 GB host with 9 GB available beside the five drift seeds: not enough for a full build. Their logs and checkpoints are kept (renamed `seed1-oom`, `seed2-oom`), not counted; both rerun from scratch, not resumed (a resume replays the RNG stream; as P1's seed 1r). On that host since: a training start needs 12 GB available after it starts, and a full gate 25 GB at its start, else it runs elsewhere (133). **The evaluation** (fixed 2026-11-23 by 133, before any of the restarted seeds was evaluated): every seed of rows a and b, and P1's stock seeds wherever they are compared, on the same grid and settings: checkpoints 500 to 4500 by 500 and 4999 (10 a seed), each by scensim's `eval_drift.py` (stock's `bench/p1/eval_drift.py`, the env ours) from the seed's own scensim commit, `--run-path <seed>/train --checkpoint <it> --envs 32 --seconds 30 --row <a|b> --starts stock`, with run_p2.sh's environment (its PYTHONPATH, `SCENSIM_ASSET_ROOT`, cameras off, Kit's renderer on the run's GPU). Its pass criterion is P1's pass bar, adopted for P2 on 2026-11-23 before any evaluation (133; the bar above, fixed before training; `eval_drift.py` computes it word for word, landed 71532ff5): a seed passes at 90 % of envs with 3 clean laps, a median peak controlled slip of 40 deg and a mean speed of 1.2 m/s; samples-to-pass is the first grid iteration at which a seed passes, and the final score is 4999's. Each row is evaluated on the host it trained on (row a on 118's GPU1, row b on 139's GPU0). The fixed `eval_drift.py` (issue 118: a crash exits nonzero instead of 0; the scores are unchanged; run_p2.sh's PYTHONPATH gains aib for it) applies to P2 runs started after it lands: the evaluations under way stay on the seeds' commit's (4c5d7a7a) for both rows, so one file scores both, and their records are checked rather than their exit codes (133, 2026-11-23). **Row a's result** (2026-11-23, 118, as measured; read from the records by 139): the five v2 seeds (scensim 4c5d7a7a, WheeledLab b491b13, each seed's meta.json, not dirty; trained and evaluated on 118's RTX 4090, Isaac Sim 6.2, Isaac Lab 3.0.0), the grid above unchanged: **no seed passes at any of its 10 checkpoints, so row a has no samples-to-pass.** Two of the bar's three items fail: the share of envs with 3 clean laps (each seed's best over the grid 0.72 to 0.78, against 0.9) and the median peak controlled slip (18 to 28 deg at 4999, against 40; at or above 40 only at early checkpoints, 3500 at the latest, where the clean share is 0.59 at most (seed 3 at 2000): no checkpoint meets both); the third, the mean speed (about 1.67 m/s), passes, and the cars lap (median about 6.2 laps; 3 clean laps is part of the clean share's test, not an item of its own). At 4999, share clean / slip median / laps median (min) / speed / off track / spun, of 32 envs: seed 1 0.625 / 24.9 deg / 6.29 (1.05) / 1.66 m/s / 12 / 3; seed 2 0.688 / 19.1 / 6.13 (4.82) / 1.67 / 8 / 7; seed 3 0.625 / 23.4 / 6.18 (0.50) / 1.68 / 11 / 7; seed 4 0.688 / 18.0 / 6.19 (1.95) / 1.67 / 9 / 5; seed 5 0.750 / 28.4 / 6.23 (2.88) / 1.68 / 8 / 4. Completeness judged by the records, not by exit codes (issue 118: an Isaac script can exit 0 after an exception): 50 of 50, each JSON with the checkpoint asked, 32 envs, 30 s, every item of the bar and 32 per-env values, each log with its EVAL line and no traceback; the 50 checkpoints evaluated hash to the archived runs' SHA256SUMS. **Row b's result, partial: 3 of 5 seeds** (2026-11-24, 139, as measured): seeds 3, 4 and 5 (scensim 4c5d7a7a, WheeledLab b491b13, each seed's meta.json, not dirty; trained and evaluated on 139's RTX 5090, Isaac Sim 6.2, Isaac Lab 3.0.0, beside other training), the grid above unchanged, row a's eval.sh and check.py with the row and paths changed: **no seed passes at any of its 10 checkpoints.** One of the bar's three items fails at every checkpoint: the share of envs with 3 clean laps (each seed's best over the grid 0.41, 0.69 and 0.69, against 0.9). The median peak controlled slip meets 40 deg at every checkpoint from 2000 on (63 to 67 deg at 4999); below it only at seed 3's 500 to 1500 (39 to 40) and seed 5's 1000 (37). The mean speed (1.66 to 1.74 m/s) passes. At 4999, share clean / slip median / laps median (min) / speed / off track / spun, of 32 envs: seed 3 0.312 / 65.6 deg / 6.01 (3.77) / 1.74 m/s / 16 / 19; seed 4 0.469 / 66.6 / 5.94 (2.52) / 1.66 / 16 / 12; seed 5 0.375 / 63.5 / 6.02 (2.40) / 1.69 / 15 / 19. Complete by the records: 30 of 30, checked as row a's; the 30 checkpoints' SHA-256 are kept with the records. **No prediction was written for row b before its runs**: the bar was fixed before training, but nothing said which items row b would meet, so these three seeds confirm or refute no prediction. A prediction for seeds 1 and 2 (the reruns after the OOM kill, still training), written before their grid but **after seeing seeds 3 to 5**, so informed by them and a weak test: seeds 1 and 2 pass at no checkpoint; at 4999 their slip median is at least 40 deg, their clean share below 0.6 and their mean speed at least 1.2 m/s. An observation, not a conclusion: rows a and b miss the bar on different items so far. Row a's slip stays under 40 deg while its clean share reaches 0.72 to 0.78. Row b's seeds drift well past 40 deg, but more of their envs leave the track or spin out (at 4999 15 or 16 off track and 12 to 19 spun, of 32, against row a's 8 to 12 and 3 to 7). With 3 seeds of row b this is not yet a difference between the rows. **Row b's seeds 1 and 2: row b complete, 5 of 5 seeds** (seed 1 evaluated 2026-11-24, seed 2 2026-11-26; 139, as measured): the reruns after the OOM kill (scensim 4c5d7a7a, WheeledLab b491b13, each seed's meta.json, not dirty; trained and evaluated on 139's RTX 5090 beside other training), the grid, eval.sh and check.py as seeds 3 to 5's, the seed changed: **neither passes at any of its 10 checkpoints.** The clean share fails at every checkpoint (best 0.469 for both: seed 1 at 2500, seed 2 at 4000); the slip median meets 40 deg at every checkpoint but seed 1's 500 (30.4 deg); the mean speed (1.56 to 1.87 m/s) passes. At 4999, as above: seed 1 0.438 / 45.8 deg / 5.91 (2.58) / 1.69 m/s / 17 / 17; seed 2 0.375 / 65.0 / 5.98 (2.78) / 1.69 / 15 / 19. Complete by the records: 20 of 20, checked as seeds 3 to 5's; the 20 checkpoints' SHA-256 are kept with the records. The prediction above, judged part by part before any interpretation: seed 1 passes at no checkpoint, MET; slip at 4999 at least 40 deg, MET (45.8); clean share below 0.6, MET (0.438); mean speed at least 1.2 m/s, MET (1.69); seed 2 likewise, MET, MET (65.0), MET (0.375), MET (1.69): 8 of 8 parts met. Interpretation, labelled: the prediction was informed by seeds 3 to 5, so meeting it says only that seeds 1 and 2 behave as 3 to 5 did. **Row b, all 5 seeds: no seed passes at any of 50 checkpoints, so row b has no samples-to-pass**; only the clean share fails from 2000 on (each seed's best over the grid 0.469, 0.469, 0.41, 0.69 and 0.69, against 0.9). At 4999 row b's envs leave the track or spin out more than row a's (15 to 17 off track and 12 to 19 spun, of 32, against row a's 8 to 12 and 3 to 7), and its slip median is 45.8 to 66.6 deg against row a's 18.0 to 28.4. The comparison with P1's stock seeds, post hoc, is "P2 against P1" above; later drift rows are judged by the relative criterion above |
| P3 | The comparison: throughput by stage, learning efficiency and cross-evaluation, stock (ported) and ours, with every difference in cost explained by stage | scensim 243 | in progress: 243 is the comparison host; throughput by paired runs on its shared GPU ("P3's throughput on a shared GPU", fixed 2026-11-22). The idle-gap table is measured (2026-11-23, "P3's idle-gap table"): ours over stock 0.66 to 0.86 for row b and 0.39 to 0.55 for row a, the gap in our per-step Python stages, not PhysX; its follow-up (vectorise terminations, resets, then row a's component step) is named and not started. The contended table (the same pairs under the other user's load) is measured (2026-11-23, "P3's contended table"): only its 4096-env point at 9e114870 can be read, row a about 0.75 of stock, row b not distinguishable from stock |
| P4 | A driving task from the case studies (for example the lead car braking, or a walker crossing) on Town01's Isaac stage, with a CaRL-style reward and the other road users on the batched behaviour. Its stock side is a hand-written Isaac Lab environment of the same task, in Isaac Lab's own style; both measured as in P3 | scensim 139 (ours), scensim 241 (stock) | in progress (ours: plan approved by 133, 2026-11-22). Stock's side: WheeledLab isaaclab-3.0 `bench/p4_leadbrake` (fef6385), CS2's family straight, dry, day, the 2-8 m safe-stop bar. Ours: (1) landed dac1e072: a reset sets each slot's storyboard parameters from its record (`Storyboard.rebind`: the compile's live reads recomputed and written in place, nothing compiled again; a read compiled into the structure is fixed and a pool drawing it refused by name), so the lead brakes at its own record's onset and rate; (2) the project `scenarios/projects/leadbrake_rl`: `leadbrake.xosc` (both cars the Model 3 catalog entry, stock's lead's footprint; the lead SSv2's default vehicle; its brake the storyboard's SpeedAction at `-$decel` once its rear is at or past the onset, a state as stock's, not a crossing: a euclidean DistanceCondition from 1000 m behind the lane's start, which SSv2 runs), drawn per reset by a joint model at stock's distribution exactly (lead_speed, headway, decel, onset uniform and independent; the lead's start and the trigger their fixed shifts; 10k draws KS within 0.011 of each uniform, the gap two-sample KS against stock's sampler), on the task's world, one straight lanelet 400 m long and 3.5 m wide (`tasks.leadbrake.straight_world`, stock's plane's +x axis); (3) the task, `Scensim-LeadBrake-v0` (`tasks.leadbrake_env`): stock's observations, reward (CaRL's terms, its -1 and +1), terminations and PPO settings (its `agent.py`, verbatim), 120 Hz physics at 20 Hz, its plane and spacing; the comparable row engine B on the Model 3 spec's generated carla-0.9.16 body (stock's car's source) with stock's action law exactly: the rear drive torque, Ackermann steering, and the brake as the spin joints' implicit damping (engine B's spin drive implicit, `implicit_effort`), so the brake-law difference is gone (from 10.5 m/s to rest in 5.64 m, v^2/2g + 0.02; stock: 10.4 in 5.6); (4) the runs: `scripts/run_p4.sh` (stock's run_p4.sh's stages and sizes, its harness; `headway` stock or record, `row` joints or ecu, `engine` B or A (A on the CPU pipeline; each row its own out dir and form name); each seed evaluated on the whole grid, 100 to 1400 by 100 and 1499, as stock's curves, and `evals` completes a trained seed's grid: 133), `train_leadbrake.py` (Isaac Lab's own train.py, as stock's), `eval_leadbrake.py` (stock's tools/evaluate.py, its bar, order of end reasons and JSON line; the conditions the pool's first 256 records at seed 20261122, stock's its own draws: the same distribution and seed, not the same episodes, about +-2 points of sampling noise at 256 and p ~ 0.9; for the paired comparison stock's evaluator writes its episodes, `--samples-out` (WheeledLab isaaclab-3.0 9810846), and ours replays them, `--conditions-from`, pairing each with stock's outcome: one smoke checkpoint on 16 of stock's episodes ended all 16 off road on both sides, the end gap's min and median 11.59 and 18.74 m ours, 11.60 and 18.75 stock's). Reported (133, 2026-11-22, written before ours runs; stock: 1 seed of 5 passed, seed 2 at iteration 700 at 0.984, seed 1 at most 0.906, seeds 3 to 5 at 0, stopped 34 to 75 m back; the task is not reshaped): (i) the seeds that pass within the 1500-iteration budget, (ii) success against samples for every seed, the median and spread over 5, (iii) samples-to-pass for the seeds that pass; the same evaluator and checkpoint cadence both sides, and the paired comparison on stock seed 2's passing checkpoint's 256 episodes; a second engine-B row through the car's own drive unit and ECU (`row=ecu`: sim_vehicle_ecu's `ev`, batched as EvBatch, its torch form on the sim's GPU: the motor's envelope and lag, regen blended with the friction brakes, ABS, TC, ESC, the steer rate). The policy's action space is stock's, [-1, 1]^2; only its meaning differs (133): it is read as ev's Autoware command, acceleration lon x a_drive for lon >= 0 (the motor's peak tractive acceleration, peak torque x gear ratio / wheel radius / mass, from the spec: 5.22 m/s^2 on the carla-0.9.16 body) or lon x a_brake for lon < 0 (the tires' friction x g, 9.81), velocity the speed that acceleration reaches in a policy step (never below 0, so a stop is held), tire angle steer x max_steer_angle (0.70 rad). Its seeds run on the Model 3 after issue 106's fix (regen slip control before ABS). And engine A through the same ev and the same reading of the action (133: a pure engine comparison with the engine-B ECU row): `engine_name=A`, aib's PhysX vehicle, its Model 3 rig (aib's config/ego.yaml, spec_hash 89cc738f as sim_vehicle_spec 21bf3dc's), PhysX's CPU pipeline and Fabric off (issue 110: with it a reset's teleport never reached PhysX), both of which cost throughput apart from the method, so they stand in the row's settings beside any of its numbers (243); its cars spawn and teleport in their env prim's frame (issue 109: a world pose put env_0's car at twice its origin). Smoke: full throttle 4.7 m/s^2, full brake v^2/2g + 0.9 to 1.5 m (engine B's ECU row: + 1.1 to 1.9), held at rest (measured at N > 1 before issue 113's fix: to measure again after it). Its seeds run with the ECU row's, after issue 106; its first seeds 1-5 (scensim 5c28e146, 2026-11-23; seed 1 to iteration 187, 2-5 to about 57) are **void, issue 113**: engine A's scene had no per-env collision groups, so cars of different envs collided; they rerun from scratch after its fix, which lays engine A's slots out apart by their route boxes (1024 slots over about +-2 km: about 13 times stock's grid's coordinates, slots playing the same episode drifting about 1 cm apart across over 6 s, near the origin as far out, against the 3 m off-road bound; the far layout adds only about 5 mm per km of it, so the 13 times larger coordinates cost little; issue 113); (4) the 2-8 m bar ported; seeds wait for stock's P4 evaluations to show a pass. Named differences so far: the lead is SSv2's default vehicle braking by SSv2's SpeedAction (stock: a kinematic box, its own law); a lead that starts past its onset (0.083 % of stock's draws) brakes a step (50 ms) after stock's, as SSv2 evaluates its storyboard first a step after the start; otherwise the lead's speed trace is stock's within 1e-9 (test_leadbrake's Lead). And one of stock's, stated rather than copied (139 and 243, 2026-11-22): in ManagerBasedRLEnv.step its resets run before `command_manager.compute`, which steps every env's lead, the just-reset ones too, before the observation; so each of stock's in-training episodes (all but `env.reset()`'s first) starts with the lead v dt further ahead, its gap h v + 0.4 to 0.7 m, its headway h + 0.05 s (+5 % at h = 1, +1.7 % at h = 3), and its onset test a step early in that frame: stock trains on headways U[1.05, 3.05] in effect, ours on the records' U[1, 3], which seats replay. Its evaluation is not affected: `tools/evaluate.py` scores each condition's first episode from `env.reset()`, at the exact h (241). A difference of stock's training distribution only, kept for P4 (its seeds are trained; 241 states it in the bench's README, WheeledLab isaaclab-3.0 56da61d, and a rerun from scratch would place the lead at FRONT + h v - v dt). So that samples-to-pass compares like with like (133), the comparable row trains on stock's distribution too: `train_headway=stock` (an in-step reset's lead one policy step on, h v + v dt, as stock's; env.reset()'s and the evaluation's at h), named in its table; for a lead starting at or past its onset (0.08 % of draws) stock brakes in that first update, ours a step later (stated, not matched: 243); the default, `record`, is every episode at its record's h **Evaluation commits** (133, 2026-11-23): each row is evaluated at its own training commit, as 139's records show (they carry no provenance; run_p4.sh runs eval_leadbrake.py from its own tree): the joints row's seeds 1 and 2 at 5b32081c (seed 1's 1100 to 1400 at 64ce876c, whose task files add only the ECU and engine A branches, defaults joints and B, and whose eval_leadbrake.py is the same), the ECU row at 5c28e146, engine A at e178f268. 241's joints seeds 3 to 5 train at 5b32081c and are evaluated from c4a8bbf2, its child, which adds only run_p4.sh's `evals` stage (each seed's whole grid) and a line here: the files the scores come from are byte-identical at both (git blobs: eval_leadbrake.py 817da768, tasks/leadbrake_env.py 7357dacc, tasks/leadbrake.py afc04de4, env.py f6dcd5b4, physx_vehicle.py b5a51ccc), as is run_p4.sh's `evaluate`, so seeds 3 to 5 are scored by the same files as seeds 1 and 2. Issue 118's fixed eval_leadbrake.py (a crash exits nonzero) applies to none of these: the remaining checkpoints run on their rows' commits. Joints seed 1's 1100 to 1400, evaluated again at 5b32081c (139, 2026-11-23), match the 64ce876c records field by field (successes, rate, pass, end reasons, end gap and lateral offset; 1100 249/256, 0.9727, a pass; 1200 0.9141, 1300 0.8789, 1400 0.7266), so all 15 of seed 1's checkpoints stand at 5b32081c. The ECU row's seed 2 (5c28e146) is evaluated on its whole grid, 15 of 15 by their records: no checkpoint passes; 100 to 900 at 0 of 256, then 1000 to 1499 at 2, 4, 22, 18, 20 and 33 of 256 (1499: 0.129) |
| P5 | Evaluation on seats: the policies from P1 to P4, both sides, exported as pilots and run on sampled scenarios on Isaac with SSv2 and on CARLA by replay; the coverage report per cell; the batch-to-seats gap | | open |
| P6 | Write-up: one table each for throughput, learning efficiency, cross-evaluation and evaluation on seats, stock against ours, with GPUDrive and f1tenth_gym as outside references; what our components cost and what they buy (identity, replay, cross-fidelity evaluation) | | open |

## Exit

Stock, ported, reproduces its published result. Ours trains the same task to
the same threshold. Throughput and learning efficiency are reported for both sides with the
same harness, and every cost difference is attributed to a stage. P4 repeats the comparison
on a driving task. P5 runs every policy on seats on both simulators with a coverage report.

## Non-goals

- A training framework of our own: training stays in Isaac Lab and a published RL library
  (rsl_rl, skrl or rl_games, whichever the reference uses).
- New algorithms. The point is to measure the pipeline, not to beat a benchmark.
