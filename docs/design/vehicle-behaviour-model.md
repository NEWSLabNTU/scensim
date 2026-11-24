# Vehicle behaviour model: the car-follower (092 K13, plan)

Status: plan, 2026-11-25 (241); approved by 133 the same day, with the notes folded in below. The user approved a vehicle
behaviour model on 2026-11-25 (through 133); this note is its design. It extends
[scenario-description.md](scenario-description.md) section 4 (behaviour models, as K10 and K12
built them for the walker) to vehicles, and changes nothing there that is not named here.

## 1. The model: the Intelligent Driver Model

**Chosen:** the Intelligent Driver Model (IDM): M. Treiber, A. Hennecke and D. Helbing,
"Congested traffic states in empirical observations and microscopic simulations", Physical
Review E 62, 1805-1824 (2000), doi:10.1103/PhysRevE.62.1805. A follower at speed v, gap s to its
leader's rear and approach rate dv = v - v_leader accelerates at

```
a_idm = a * (1 - (v / v0)^delta - (s_star / s)^2)
s_star = s0 + v * T + v * dv / (2 * sqrt(a * b))
```

with desired speed v0, jam gap s0, time gap T, maximum acceleration a, comfortable deceleration
b and exponent delta (4). Without a leader the second term is 0.

**Its coefficients, a named set, as the walker's** (`sets/<name>.yaml`, the record naming the
set and its sha256): `zhang2024_highd_car`, from C. Zhang and L. Sun, "Bayesian Calibration of
the Intelligent Driver Model", IEEE Transactions on Intelligent Transportation Systems (2024),
doi:10.1109/TITS.2024.3354102, arXiv:2210.03571 (CC BY 4.0), Table I, row "Pooled MA-IDM
(car)": v0 12.244, s0 2.833, T 1.133, a 0.362, b 2.140, delta fixed at 4 by the paper. Checked
against the PDF (arXiv v2) on 2026-11-25. The plan first named the hierarchical MA-IDM's
population row (16.919, 3.538, 1.183, 0.553, 2.147); the PDF shows that population spans the
paper's 10 car and 10 truck followers, so for a car the car-only pooled row is the one taken.
Fitted on highD (German motorways, drone video, 60 recordings, 25 Hz downsampled to 5 Hz,
sections of 420 m): car-following of 50 s or more, 20 leader-follower pairs drawn, 10 with a
car following: **10 car followers, a small sample**; its truck row is a second set if a scenario needs one. **s0, T,
a and b are motorway-fitted**; v0 comes from the lane's speed limit, not the set (section 3; the
paper itself calls v0 hard to identify from car-following), so a Town lane keeps its own speed,
but its following behaviour is a German motorway driver's.

**Why it fits.**
- It is the standard car-following model, the one SUMO and most traffic studies ship, and its
  five parameters each mean something a scenario can state or sample (a cautious driver is a
  larger T and smaller a, b).
- Its braking grows smoothly as the gap closes, which is what CS2 and CS6 need from a lead car
  the ego follows: a human-like braking profile rather than a storyboard's step. Uncapped, it
  is collision-free in its own dynamics; that guarantee rests on its deceleration being
  unbounded, so the cap below breaks it (see "Emergency braking").
- Its step is + - * /, one sqrt and an integer power (delta = 4, computed as two squares), with
  no draws: one code over `sim_vehicle_ecu.xp`. numpy and torch on the CPU, in float64, with
  the same order of operations and `(v / v0)^4` written as two squarings (not a power), agree bit
  for bit, as the walker's do. On a GPU, sim_vehicle_ecu.xp runs one operation per CUDA kernel
  with nothing fused, so torch there is **expected bit for bit, not yet run on a GPU**: the test
  compares bytes and runs only where a GPU is present.
- Its action is longitudinal, so it maps onto K12's channel as it is (section 2).

**What it leaves out**, said in the record and in section 4 of the description:
- **Lane changes.** IDM follows one lane. The standard companion, MOBIL (A. Kesting, M. Treiber
  and D. Helbing, Transportation Research Record 1999, 86-94, 2007), is a later step; a cut-in
  needs it, or a storyboard lane change, which K12 makes a semantic error on a commanded entity.
- **Aggression and human error.** IDM has no reaction time, no estimation error and no
  risk-taking; the Human Driver Model (Treiber, Kesting and Helbing, Physica A 360, 71-88, 2006)
  adds them and is not built. Aggression here is only what its parameters express (a short T, a
  large a).
- **Driver spread.** The set gives one driver, the population mean. The paper publishes no
  population spread (its hyperparameters' posteriors are not tabled), so the sampler's bases for
  T, a, b and s0 are **invented**, labelled so as K11c's base was, their ranges bracketing the
  set's means (133, 2026-11-25). A published spread is future work.
- **Emergency braking.** IDM's deceleration is unbounded when the gap closes fast, and its
  freedom from collisions depends on that. The model caps it at the entity's catalog
  `maxDeceleration` and reports each frame the cap binds as a `capped` event: a collision of the
  model's own can appear only after one, and the record counts them.

## 2. The vehicle side of K12's channel

K12's channel carries, per commanded entity and frame, `speed heading accel_limit` (D4), and the
world integrates `v += clamp(speed - v, +-accel_limit dt)`, the yaw set to the heading, the
position moved `v dt` along it (D5). The car-follower uses it as it is, no field added:

- **Speed and acceleration.** The model commands `speed = max(0, v + a_cmd dt)` and
  `accel_limit = max(|a_cmd|, eps)`, so the world applies exactly `a_cmd` over the frame (or
  stops at 0). `a_cmd` is `a_idm`, capped below at `-maxDeceleration` and above at
  `maxAcceleration` from the entity's catalog Performance.
- **Path.** The model holds a lane: its `lane` property names a lane anchor (K9:
  `anchor.<name>`, with `heading_s`, `heading`, `start_x`, `start_y` and `length`). Its state is
  its arc position s on that lane; its heading command is the lane's heading at s, so the
  world's kinematic step moves it along the centreline (on a curve, by the chord error of one
  frame's step, which is reported). A lane ends where the anchor ends; the model stops there
  (an event).
- **Its leader.** The `leader` property names an entity (or `ego`). Each frame the leader's truth
  pose is projected onto the lane; the gap is the difference in s less half of each vehicle's
  length (catalog BoundingBox). A leader off the lane, or behind, is no leader (free road).
- **SSv2.** K12 D1 named the step: the fork's `SimulatorDrivenVehicleEntity::drives()` gains
  controller `model`; `scensim run`'s refusal of a commanded vehicle is lifted; storyboard speed,
  lane-change and route actions on it stay semantic errors. SSv2 adopts the world's pose, as for
  the walker.
- **The world.** CARLA: the world server spawns the vehicle with physics off and sets its
  transform each tick, as the walker's (its wheels do not turn; its lights and its box are a
  car's). Isaac: refused by name, as K12 D3 refuses any commanded entity there.

## 3. Parameter schema and step

As the walker's (`params_schema`; each parameter's type, default, range, and source: `set` or
`ours`): `parameter_set` (`zhang2024_highd_car`), `lane` (an anchor name), `leader` (an entity
name, or none), `v0` (default the lane anchor's `speed_limit`, else the set's), `T`, `s0`, `a`,
`b` (defaults the set's; ranges ours, wide enough for the sampler: T 0.3-3.0 s, s0 0.5-6 m, a
0.1-4 m/s^2, b 0.5-6 m/s^2), `delta` (the set's 4, not a parameter). A parameter beyond the
entity's catalog Performance is refused by name.

`Model(params, seeds, anchors, xp)` for every slot at once; `reset(mask)` sets each slot's s from
its Init pose projected onto its lane; `step(obs, dt) -> (action, events)` with `obs` the slot's
own pose and velocity and its leader's (`leader_x`, `leader_y`, `leader_vx`, `leader_vy`,
`leader_valid`). Events: `follow` and `free` (on a change), `capped` (the deceleration cap
bound), `stopped`, `lane_end`. No randomness: the seed is unused, said in the record.

## 4. Checks

- **The model alone:** steady following at v keeps IDM's equilibrium gap,
  `(s0 + v T) / sqrt(1 - (v / v0)^4)`; from rest on a free road it approaches v0 without
  overshoot; behind a standing car it stops at s0; numpy and torch bit for bit over the
  walker's test's grid of slots and steps on the CPU in float64; on a GPU expected bit for bit,
  not yet run there.
- **On seats (CARLA 0.9.16):** a lockstep run with lag 1 at every frame, the vehicle within its
  lane (lateral offset from the centreline, p95 and max, reported against a bound fixed before
  the run).
- **Seats against the batch:** K10's agreement, for the follower: the same record on both, the
  follower's truth against the batch's model at the channel's lag; events at the same frames,
  the follower's position within a bound fixed before the run. This is CARLA's seats against the
  batch, whose Isaac-side engines place model entities kinematically, not in PhysX. An agreement
  with the Isaac world server itself needs K12 D3's follow-up (a tick gate and `READS_BACK` for
  Isaac), its own item after K13 (133).
- **A first search:** a platoon on a lane anchor of 50 km/h or more, on a map of the dataset
  with a lanelet export (Town04 or Town05 first; a K9 anchor added there; Town01's limit is not
  raised; 133): a scripted lead-lead car L brakes (sampled
  deceleration and onset), the model car M follows it under IDM (sampled T, a, b), and the ego
  follows M. The failure is the ego's (a collision with M, or its time to collision below the
  scenario's bound). K11's search runs over L's braking and M's parameters in the batch; the
  realism the model adds is M's braking profile, which the ego must answer. A cut-in waits for
  lane changes.
