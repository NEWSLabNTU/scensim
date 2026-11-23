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

## Steps

| Step | What | Owner | Status |
|---|---|---|---|
| P0 | The measurement harness: stage timers around the environment step and the runner's phases, GPU memory, and the learning curve, written to one CSV schema; applied unchanged to stock and to ours. Its own overhead measured and reported | 241 | in progress: `bench/wheeledlab_bench` on the fork's `isaaclab-3.0` (7ea2873), a pip package with no WheeledLab import; hooks Isaac Lab's manager-based env and rsl_rl's PPO by class; refuses a time-sliced GPU. Overhead not yet measured on an exclusive GPU |
| P1 | Stock: the MuSHR drift task (rsl_rl PPO, 1024 environments, the paper's headline task), ported (the NEWSLabNTU fork, branch `isaaclab-3.0`, upstream's base commit named), trained to its published result over 5 seeds; the pass bar fixed from the paper before training. F1TENTH drift afterwards as an extra | 241 | in progress: ported on upstream a5017ce (5a6861c, c98aa20), trains on Isaac Lab 3.0.0 / Isaac Sim 6.2; `WHEELEDLAB_ENABLE_CAMERAS=0` measures it without upstream's forced cameras (c3f286b); pass bar above. Seeds and sweep wait for an exclusive GPU. **Seeds on a shared GPU** (133, 2026-11-22: samples to pass only): 5 seeds, 3 at a time, on 241's GPU0 (fork fef6385, `/var/tmp/aeon/wl-port/p1-241-gpu0/seeds`), under a memory guard that stops one run when the GPU's free memory falls below 4096 MiB. **Two stops by the guard** (2026-11-23): seed 1 at iteration 1663 (04:48) and seed 2 at iteration 1877 (09:57), each beside two other P1 runs. The guard was to stop its newest run but took the last key of a bash associative array, which is not start order, and so stopped the oldest twice. Both are kept (logs and checkpoints in `seed1` and `seed2`), not counted, and rerun from scratch, not resumed: rsl_rl's checkpoint holds no RNG or environment state, and the env is reseeded on load. The reruns are `seed1r`, then `seed2r`. The guard now stops the run with the least elapsed time (`p1-guard.sh`), and a run it stops is rerun from scratch the same way |
| P2 | Ours, the same task: a MuSHR spec from stock's asset, the field, the drift episode as a compiled scenario with sampled starts, the control component, truth, through K2's environment; stock's rewards and PPO settings. Trained over 5 seeds | swb 139 | in progress (plan approved by 133, 2026-11-22; step 1 and 2 landed 2026-11-22: the spec, sim_vehicle_spec's `dc_motor` drive, undriven and suspension drives and `steer_law: tan`, scensim_batch's DCMotorCfg and tan law; the body's smoke on the GPU, bypassed: 2.07 m/s for 2 m/s asked, 0.83 rad/s at d 0.3): (1) the spec, `scenarios/projects/mushr_drift/vehicles/mushr_nano.yaml`, read from stock's `mushr_nano_v2.usd` (source, commit, licence named; what stock lacks named); (2) sim_vehicle_spec's articulation gains a `dc_motor` drive (Isaac Lab's DCMotorCfg) and a `tan` steer law beside Ackermann's; (3) the episode: stock's oval (straights 0.8 m, line radius 0.8 m) as a polyline world, a 5 s time-up scenario at 50 Hz on 200 Hz physics, stock's plane material; the start a distribution in the compiled scenario (a reference point along the track, position and yaw noise as stock's), drawn again on the device at every reset, each episode its own sample record (seed, reference index, noise) so any training episode replays on seats (P5); env_spacing 0 with filtered collisions, as stock; (4) the task, a ScensimEnv subclass with stock's observations (and their corruption), rewards, curriculum and terminations, and stock's event terms through Isaac Lab's event manager, renamed to our joints and bodies; rsl_rl with stock's PPO settings; (5) two rows: the action through the car's real component (MuSHR's VESC: roboracer_vesc's batch at MuSHR's values, speed mode) and bypassed (rear spin velocity targets v/r on the DC motor, steer tan(δ), as stock); `ideal` a third row only if (a)'s cost needs explaining; 241's wheeledlab_bench gains a DirectRLEnv hook (the same stages and timers, the harness version pinned on both sides). Every difference from stock is named in the table, the renamed event terms among them. Before this: planned (133, 2026-11-21), after 092 K2.2b (engine B), K2.4 and K2.2c (the device-resident path: BatchRun and the control component's torch form on cuda, bit-close to the CPU path; 133, 2026-11-21): a MuSHR spec written from stock's `mushr_nano_v2.usd`, naming its source asset, commit and that asset's licence, any value stock lacks named; its articulation body reproduces stock's joint drives (read in the WheeledLab fork, isaaclab-3.0 a35060c: the throttle an explicit DC motor, `DCMotorCfg` damping 1000, effort 0.25, saturation 1.05, velocity 450; the 2WD variant's rear effort 0.5 and its front wheels passive; the steer a position drive, both front wheels to tan(δ), not Ackermann angles; passive suspension, stiffness 1e8), so both sides are articulations and the named differences are only ours (the control component, the compiled episode, the sampler), and the table says so; the field (stock's plane material) and track (its oval) as the episode's ground; the 5 s episode at 50 Hz (200 Hz physics) as a compiled scenario, sampled starts as stock's; stock's observations, rewards, curriculum and rsl_rl PPO settings through K2's environment. Ours measured two ways: the action through our control component, and the component bypassed (the action straight to the joints, as stock), so the component's cost and its effect on learning are separate numbers. One seed as a contended smoke; 5 seeds and rates wait for an exclusive GPU. **Seeds superseded** (2026-11-22, found by P3's profile, 139): every P2 seed so far (row b's five on 139 at 780921e4 and 761286f9, row a's five on 118 at 1bb4a482 and 12e0d1db) ran the MuSHR at its USD's 32 position and 1 velocity solver iterations, not stock's config's 4 and 0, and without its sleep, stabilisation and rigid-body properties (`MUSHR_CFG`): our spawn read the USD alone. Not stock's physics, so they are kept (139's under `/var/tmp/aeon/p2runs/seeds-b-stock`, 118's under its `p2a`) and not counted, and all ten restart on the fix: sim_vehicle_spec c11ec1d's `body.asset.spawn` (stock's values, named to `MUSHR_CFG`, keyed by the USD attributes they set), applied by scensim_batch's `articulation_cfg` and read back from the stage at the env's start. 243's P3 slots of ours at 12e0d1db are superseded likewise. The body check of batch-executor.md section 5 ran at 4/0 (its script set them) and stands. **A gate-memory incident** (2026-11-23, 139): row b's restarted seeds 1 and 2 (scensim 4c5d7a7a, WheeledLab b491b13, `/var/tmp/aeon/p2runs/seeds-b-v2`) were killed by the kernel's OOM killer at iterations about 3349 and 3364 of 5000, during a full `just build && just test` gate (issue 113's) started on the same 60 GB host with 9 GB available beside the five drift seeds: not enough for a full build. Their logs and checkpoints are kept (renamed `seed1-oom`, `seed2-oom`), not counted; both rerun from scratch, not resumed (a resume replays the RNG stream; as P1's seed 1r). On that host since: a training start needs 12 GB available after it starts, and a full gate 25 GB at its start, else it runs elsewhere (133). **The evaluation** (fixed 2026-11-23 by 133, before any of the restarted seeds was evaluated): every seed of rows a and b, and P1's stock seeds wherever they are compared, on the same grid and settings: checkpoints 500 to 4500 by 500 and 4999 (10 a seed), each by scensim's `eval_drift.py` (stock's `bench/p1/eval_drift.py`, the env ours) from the seed's own scensim commit, `--run-path <seed>/train --checkpoint <it> --envs 32 --seconds 30 --row <a|b> --starts stock`, with run_p2.sh's environment (its PYTHONPATH, `SCENSIM_ASSET_ROOT`, cameras off, Kit's renderer on the run's GPU). Its pass criterion is P1's pass bar, adopted for P2 on 2026-11-23 before any evaluation (133; the bar above, fixed before training; `eval_drift.py` computes it word for word, landed 71532ff5): a seed passes at 90 % of envs with 3 clean laps, a median peak controlled slip of 40 deg and a mean speed of 1.2 m/s; samples-to-pass is the first grid iteration at which a seed passes, and the final score is 4999's. Each row is evaluated on the host it trained on (row a on 118's GPU1, row b on 139's GPU0). The fixed `eval_drift.py` (issue 118: a crash exits nonzero instead of 0; the scores are unchanged; run_p2.sh's PYTHONPATH gains aib for it) applies to P2 runs started after it lands: the evaluations under way stay on the seeds' commit's (4c5d7a7a) for both rows, so one file scores both, and their records are checked rather than their exit codes (133, 2026-11-23) |
| P3 | The comparison: throughput by stage, learning efficiency and cross-evaluation, stock (ported) and ours, with every difference in cost explained by stage | scensim 243 | in progress: 243 is the comparison host; throughput by paired runs on its shared GPU ("P3's throughput on a shared GPU", fixed 2026-11-22). The idle-gap table is measured (2026-11-23, "P3's idle-gap table"): ours over stock 0.66 to 0.86 for row b and 0.39 to 0.55 for row a, the gap in our per-step Python stages, not PhysX; its follow-up (vectorise terminations, resets, then row a's component step) is named and not started. The contended table (the same pairs under the other user's load) is measured (2026-11-23, "P3's contended table"): only its 4096-env point at 9e114870 can be read, row a about 0.75 of stock, row b not distinguishable from stock |
| P4 | A driving task from the case studies (for example the lead car braking, or a walker crossing) on Town01's Isaac stage, with a CaRL-style reward and the other road users on the batched behaviour. Its stock side is a hand-written Isaac Lab environment of the same task, in Isaac Lab's own style; both measured as in P3 | scensim 139 (ours), scensim 241 (stock) | in progress (ours: plan approved by 133, 2026-11-22). Stock's side: WheeledLab isaaclab-3.0 `bench/p4_leadbrake` (fef6385), CS2's family straight, dry, day, the 2-8 m safe-stop bar. Ours: (1) landed dac1e072: a reset sets each slot's storyboard parameters from its record (`Storyboard.rebind`: the compile's live reads recomputed and written in place, nothing compiled again; a read compiled into the structure is fixed and a pool drawing it refused by name), so the lead brakes at its own record's onset and rate; (2) the project `scenarios/projects/leadbrake_rl`: `leadbrake.xosc` (both cars the Model 3 catalog entry, stock's lead's footprint; the lead SSv2's default vehicle; its brake the storyboard's SpeedAction at `-$decel` once its rear is at or past the onset, a state as stock's, not a crossing: a euclidean DistanceCondition from 1000 m behind the lane's start, which SSv2 runs), drawn per reset by a joint model at stock's distribution exactly (lead_speed, headway, decel, onset uniform and independent; the lead's start and the trigger their fixed shifts; 10k draws KS within 0.011 of each uniform, the gap two-sample KS against stock's sampler), on the task's world, one straight lanelet 400 m long and 3.5 m wide (`tasks.leadbrake.straight_world`, stock's plane's +x axis); (3) the task, `Scensim-LeadBrake-v0` (`tasks.leadbrake_env`): stock's observations, reward (CaRL's terms, its -1 and +1), terminations and PPO settings (its `agent.py`, verbatim), 120 Hz physics at 20 Hz, its plane and spacing; the comparable row engine B on the Model 3 spec's generated carla-0.9.16 body (stock's car's source) with stock's action law exactly: the rear drive torque, Ackermann steering, and the brake as the spin joints' implicit damping (engine B's spin drive implicit, `implicit_effort`), so the brake-law difference is gone (from 10.5 m/s to rest in 5.64 m, v^2/2g + 0.02; stock: 10.4 in 5.6); (4) the runs: `scripts/run_p4.sh` (stock's run_p4.sh's stages and sizes, its harness; `headway` stock or record, `row` joints or ecu, `engine` B or A (A on the CPU pipeline; each row its own out dir and form name); each seed evaluated on the whole grid, 100 to 1400 by 100 and 1499, as stock's curves, and `evals` completes a trained seed's grid: 133), `train_leadbrake.py` (Isaac Lab's own train.py, as stock's), `eval_leadbrake.py` (stock's tools/evaluate.py, its bar, order of end reasons and JSON line; the conditions the pool's first 256 records at seed 20261122, stock's its own draws: the same distribution and seed, not the same episodes, about +-2 points of sampling noise at 256 and p ~ 0.9; for the paired comparison stock's evaluator writes its episodes, `--samples-out` (WheeledLab isaaclab-3.0 9810846), and ours replays them, `--conditions-from`, pairing each with stock's outcome: one smoke checkpoint on 16 of stock's episodes ended all 16 off road on both sides, the end gap's min and median 11.59 and 18.74 m ours, 11.60 and 18.75 stock's). Reported (133, 2026-11-22, written before ours runs; stock: 1 seed of 5 passed, seed 2 at iteration 700 at 0.984, seed 1 at most 0.906, seeds 3 to 5 at 0, stopped 34 to 75 m back; the task is not reshaped): (i) the seeds that pass within the 1500-iteration budget, (ii) success against samples for every seed, the median and spread over 5, (iii) samples-to-pass for the seeds that pass; the same evaluator and checkpoint cadence both sides, and the paired comparison on stock seed 2's passing checkpoint's 256 episodes; a second engine-B row through the car's own drive unit and ECU (`row=ecu`: sim_vehicle_ecu's `ev`, batched as EvBatch, its torch form on the sim's GPU: the motor's envelope and lag, regen blended with the friction brakes, ABS, TC, ESC, the steer rate). The policy's action space is stock's, [-1, 1]^2; only its meaning differs (133): it is read as ev's Autoware command, acceleration lon x a_drive for lon >= 0 (the motor's peak tractive acceleration, peak torque x gear ratio / wheel radius / mass, from the spec: 5.22 m/s^2 on the carla-0.9.16 body) or lon x a_brake for lon < 0 (the tires' friction x g, 9.81), velocity the speed that acceleration reaches in a policy step (never below 0, so a stop is held), tire angle steer x max_steer_angle (0.70 rad). Its seeds run on the Model 3 after issue 106's fix (regen slip control before ABS). And engine A through the same ev and the same reading of the action (133: a pure engine comparison with the engine-B ECU row): `engine_name=A`, aib's PhysX vehicle, its Model 3 rig (aib's config/ego.yaml, spec_hash 89cc738f as sim_vehicle_spec 21bf3dc's), PhysX's CPU pipeline and Fabric off (issue 110: with it a reset's teleport never reached PhysX), both of which cost throughput apart from the method, so they stand in the row's settings beside any of its numbers (243); its cars spawn and teleport in their env prim's frame (issue 109: a world pose put env_0's car at twice its origin). Smoke: full throttle 4.7 m/s^2, full brake v^2/2g + 0.9 to 1.5 m (engine B's ECU row: + 1.1 to 1.9), held at rest (measured at N > 1 before issue 113's fix: to measure again after it). Its seeds run with the ECU row's, after issue 106; its first seeds 1-5 (scensim 5c28e146, 2026-11-23; seed 1 to iteration 187, 2-5 to about 57) are **void, issue 113**: engine A's scene had no per-env collision groups, so cars of different envs collided; they rerun from scratch after its fix, which lays engine A's slots out apart by their route boxes (1024 slots over about +-2 km: about 13 times stock's grid's coordinates, slots playing the same episode drifting about 1 cm apart across over 6 s, near the origin as far out, against the 3 m off-road bound; the far layout adds only about 5 mm per km of it, so the 13 times larger coordinates cost little; issue 113); (4) the 2-8 m bar ported; seeds wait for stock's P4 evaluations to show a pass. Named differences so far: the lead is SSv2's default vehicle braking by SSv2's SpeedAction (stock: a kinematic box, its own law); a lead that starts past its onset (0.083 % of stock's draws) brakes a step (50 ms) after stock's, as SSv2 evaluates its storyboard first a step after the start; otherwise the lead's speed trace is stock's within 1e-9 (test_leadbrake's Lead). And one of stock's, stated rather than copied (139 and 243, 2026-11-22): in ManagerBasedRLEnv.step its resets run before `command_manager.compute`, which steps every env's lead, the just-reset ones too, before the observation; so each of stock's in-training episodes (all but `env.reset()`'s first) starts with the lead v dt further ahead, its gap h v + 0.4 to 0.7 m, its headway h + 0.05 s (+5 % at h = 1, +1.7 % at h = 3), and its onset test a step early in that frame: stock trains on headways U[1.05, 3.05] in effect, ours on the records' U[1, 3], which seats replay. Its evaluation is not affected: `tools/evaluate.py` scores each condition's first episode from `env.reset()`, at the exact h (241). A difference of stock's training distribution only, kept for P4 (its seeds are trained; 241 states it in the bench's README, WheeledLab isaaclab-3.0 56da61d, and a rerun from scratch would place the lead at FRONT + h v - v dt). So that samples-to-pass compares like with like (133), the comparable row trains on stock's distribution too: `train_headway=stock` (an in-step reset's lead one policy step on, h v + v dt, as stock's; env.reset()'s and the evaluation's at h), named in its table; for a lead starting at or past its onset (0.08 % of draws) stock brakes in that first update, ours a step later (stated, not matched: 243); the default, `record`, is every episode at its record's h |
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
