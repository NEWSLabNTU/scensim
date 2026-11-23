# 108: the Isaac Model 3 brakes about 7 % harder than its tyre's mu allows

**Status:** fixed (aib ff5e72b, scensim_isaac_world 7e01d7b): PhysX's default tyre load filter,
confirmed by the restLoad-doubling stop, divided out by aib.
**Severity:** medium: every braking comparison of Isaac against CARLA, or against a real car,
carries it. **Found:** 2026-11-23, scensim 241, in issue 106's low-grip sweep (133 asked for it
to be measured).

## What happens

At its limit, the Isaac Model 3 stops harder than mu g allows. With its wheels locked, it stops
harder than its own friction-vs-slip curve allows.

Measured with aib.steptest `limit_brake`, a request of -12 m/s^2 from 15 m/s, at tyre friction
(`--set tire_friction`) 0.2, 0.3, 0.5 and 1.0. Each run has ABS on as shipped, or off, so the
wheels lock. The deceleration is dv/dt over the stop above 3 m/s, past the lags, less the road
load (rolling 0.0095 g, plus drag); the logged `a` agrees with dv/dt to 0.01 m/s^2.

| set mu | with ABS: decel / g | / mu | locked: decel / g | / mu |
|---|---|---|---|---|
| 0.2 | 0.212 | 1.060 | 0.193 | 0.964 |
| 0.3 | 0.320 | 1.068 | 0.287 | 0.955 |
| 0.5 | 0.539 | 1.078 | 0.478 | 0.956 |
| 1.0 | 1.069 | 1.069 | 0.959 | 0.959 |

- **With ABS:** outside the band set before the run: 0.909 at mu 0.2, 0.940 at mu 0.5. The
  band, 0.01 wide, was narrower than one ABS stop's cycling scatter, about 0.01 either way.
  Every value is under 1.0, and each matches its pre-fix stop divided by 1.154 to 0.011.
- **Accepted on the locked test and the ratio** (133, 2026-11-23). The fix claims grip scales by
  exactly 1/1.154. The clean locked test holds that at all three mu, and so does the
  stop-by-stop ratio with ABS. The ABS rows are not a pass, and the band is not redrawn. Where
  issue 106's rerun needs ABS figures from single stops, it uses repeated stops.
- **Data:** NAS `autoveh/logs/2026 SSv2 on CARLA/2026-11-23 issue 106 and 108 (241)/fixcheck`.
  The first ABS run at mu 0.2 failed fetching Isaac's asset root, a network failure; its log is
  kept, and it was run again.

**Tests.**
- aib's `test_tyre_friction.py`: the gain, the car's grip at any transfer, the per-wheel
  shares, and all four write paths.
- siw's `test_the_rig_peaks_are_spike_4as_over_the_filter`: the peaks fall by exactly
  1/FILTER_GRIP.

### Runs that stay on the pre-fix aib (133, 2026-11-23)

So that their rows compare on one plant, these keep their pinned pre-108 aib:
- P1;
- P4 ours seeds 3 to 5;
- 139's ECU-B and P2 row (b);
- 118's row (a) seed 5;
- 139's engine A reruns after issue 113.

Roadmap 094 records it and names the factor.

### Owed after the landing, on post-108 aib (nothing re-judged early)

| item | who | when |
|---|---|---|
| Issue 106's full table (regen_60, regen_30; mu 0.2, 0.3, 1.0; release 0.15 and its neighbours), judged by its written rule | 241 | done 2026-11-23: 0.15 kept, one known one-step failure (issue 106) |
| The dry set: launch, brake_100 (predicted about 42 m against 39.54), start_flat, start_up, hold_camber | 241 | done 2026-11-23: brake_100 44.58 m; start_flat a 2.5 % miss (below) |
| Issue 100's Isaac validation and reference reruns (vehicle_check, the T3 Isaac suites) | 241 | after the P4 seeds free GPU1 |
| 054 T1's surface-layer peaks: each class's peak lands where the class says | 241 | with issue 100's reruns |
| Isaac-vs-CARLA braking and cornering comparisons made before 108 | 133 assigns; 241 lists the docs that cite one when 108 lands | after the list |
| The drift retune and the race planner's refit (243's verdict below) | 243 | when the user resumes the drift work (on hold since 2026-11-02) |
| A question, not yet an issue: do our Isaac runs need the network at start? One `limit_brake` failed fetching Isaac's asset root from S3 (`add_default_ground_plane` via `get_assets_root_path`) | 241 | answered: yes, issue 117 |

### The dry set on post-108 aib: prediction (2026-11-23, before the run)

aib.steptest, shipped values (no `--set`), aib ff5e72b: launch, brake_100, regen_60,
start_flat, start_up and hold_camber, against issue 106's verified set (pre-108 aib 23ef5fb).
One run each. Issue 106's 55 runs were identical to the step on repeats, so repeats add
nothing.
- **brake_100: 42 to 46 m** (39.54 before). An ABS stop from 100 km/h is grip-limited, and the
  grip fell by 1.07 to 1.154, depending on how much load transfer the stop holds.
- **launch: 6.43 to 6.70 s** (6.428). Only the first metres can be traction-limited at mu 1.0.
- **start_flat 0.2845 m and start_up 3.65 m: unchanged within 1 %.** They are creeps far below
  any grip limit.
- **hold_camber: under 1 cm sideways in 60 s** (0.128 cm). It is held below the limit, so a
  lower cap moves it little.
- **regen_60 dry: -1.5 m/s^2 all regen, no friction torque, unchanged.**

A value outside its range is a miss, reported as one, and looked into before anything is
re-judged on it.

### The dry set on post-108 aib: result (2026-11-23)

| test | before 108 (aib 23ef5fb) | after (aib ff5e72b) | predicted | |
|---|---|---|---|---|
| brake_100 | 39.54 m, 10.62 m/s^2 mid-stop | 44.58 m, 9.29 m/s^2 | 42 to 46 m | in |
| launch, 0-100 km/h | 6.428 s (rear slip peak 1.23) | 6.448 s (1.93) | 6.43 to 6.70 s | in |
| start_flat | 0.2845 m | 0.2775 m (-2.5 %) | within 1 % | **miss** |
| start_up | 3.6467 m | 3.6629 m (+0.4 %) | within 1 % | in |
| hold_camber | 0.128 cm in 60 s | 0.128 cm | under 1 cm | in |
| regen_60 dry | -1.5 m/s^2 all regen, 0 friction torque | the same | unchanged | in |

**start_flat's miss:** the car creeps off the hold brake at about 1 cm/s (the release torque,
issue 070). After the fix it is 0.0008 m/s slower over the first 2 s, and close after (v_end
0.0159 against 0.0156). So the 2.5 % comes from the first seconds. Not looked into further:
a tyre at 1 cm/s may read a large slip, which the friction cap could reach even at these
forces, but that is not verified. Nothing depends on start_flat's distance beyond issue 070's
check that the car creeps, which still holds. Data: NAS `autoveh/logs/2026 SSv2 on CARLA/2026-11-23
issue 106 and 108 (241)/dryset`.

### The drift work (243, 2026-11-23, read only)

**Verdict:** retune and rerun, folded into the rerun of 057/058 on issue 100's slip denominator
that is already owed. Nothing is held before 108 lands. Results already recorded stand on their
pinned pre-108 aib, and no drift number is cited as current until the rerun.

- **057's ring drift** (R 100 m at 27 m/s, about 0.74 g) was tuned on 1.154 times the grip.
  The same drift now needs about 15 % more of the grip there is, so its steady speed on that
  radius is about 27 x 0.931 = 25.1 m/s. Its slip and countersteer gains need retuning.
- **058's H1 hairpin parameters** have been void since issue 023. Nothing new is lost.
- **The race planner** (autoware-drift `race_planner`) caps each wheel at mu fz, with no filter.
  Its fits against Isaac absorbed the 1.154: L1's grip 0.92, the sliding share 0.8, the fixture
  `test/data/isaac_drift_mustang_dry.npz`, and "model beta diverges from Isaac above 0.6 g".
  All of them are refitted and the fixture regenerated. The planner adopts the per-wheel cap
  exactly: mu (0.2308 fz0 + 0.9231 fz) / 1.154 for 0 <= fz <= 3 fz0, mirroring
  `aib.tyre_friction`'s `LOAD_FILTER` and `FILTER_GRIP`, with a test that the two are equal.
  Its own `PEAK_SPAN = 2.3` copy (`model.py`) becomes 2.3 / FILTER_GRIP.
- **Peak slips fall 13 %.** The drift test (rear axle at least 3 deg past the tyre's peak)
  stays defined, but every absolute slip threshold in the drift tasks and rewards is derived
  again from the new peaks.

Data: NAS `autoveh/logs/2026 SSv2 on CARLA/2026-11-23 issue 106 and 108 (241)/mueff`,
`.../restload`, `.../fixcheck`.
