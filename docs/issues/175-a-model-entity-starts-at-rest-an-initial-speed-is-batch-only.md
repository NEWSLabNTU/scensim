# 175: a model entity starts at rest; an initial speed is batch-only

**Status:** open; plan approved by 133 (2026-11-25), no code yet. **Severity:** medium. A
scenario that gives a model entity an initial speed gets a run that silently ignores it, and no
scenario can start a model car moving, which a platoon at speed needs.
**Found:** 2026-11-25, scensim 241, planning 092 K13 step v (the platoon search on Town05's
`west_avenue`): the model car M has to start at 22 m/s at its equilibrium gap, and nothing
starts it moving.

## What happens

- **The batch drops an initial speed without a word.** `compile_scenario` takes an Init
  `SpeedAction` (`AbsoluteTargetSpeed`) on any entity, a model entity's too, into `c.speed` and
  `c.speed_set`; the model block's reset (`core.py`, the models' `reset`) then sets every model
  entity's speed to 0. A probe (`k13_platoon_idm.xosc` with an 11.0 m/s step `SpeedAction`
  added to `follower`'s Init, on test_core's straight world) prints `compiled: speed 11.0
  speed_set True` and `after reset: model v 0.0`. A silent drop is worse than a refusal: the
  scenario reads as if the car started at that speed, and nothing says it did not.
- **In Init the rule is a convention, not a check.** The K10 and K13 scenarios say "the model
  alone moves the follower: no storyboard action names it". The Story's side is enforced: each
  Story private action the batch compiles refuses a model entity by name (a SpeedAction or a
  LaneChangeAction on one is "a model entity", a RoutingAction is the ego's only; test_compile's
  `cs1_walker_dartout.xosc` case). Init's is not: the batch's compile takes a SpeedAction on a
  model entity and skips a ControllerAction on any entity. On seats the world server spawns a
  model entity at rest and moves it only on the model's commands.
- **A model car cannot reach speed in a lane.** With the set's a (0.362 m/s^2) or K13 step v's
  range [0.2, 0.6], an IDM car from rest needs well over a minute and far more than Town05's
  372 m anchor to come near 22 m/s. Town01's platoon raised a to 1.5 ("ours") for that reason.

## The plan (133, 2026-11-25)

1. **One narrow exception, batch only.** An Init `SpeedAction` on a model entity whose target is
   `AbsoluteTargetSpeed` and whose dynamics shape is `step` sets the entity's speed at reset in
   the batch: the models' reset takes `c.speed` where `c.speed_set`, 0 elsewhere. The model's
   first decision (issue 165, on the reset observation) reads that speed.
2. **Every other action on a model entity is refused, by name**, in the batch's compile: in
   Init anything but a TeleportAction and that SpeedAction (another shape, a relative target, a
   ControllerAction, a RoutingAction); the Story's refusals stay as they are (each of its
   private actions already refuses a model entity) and get a test per action. A condition that
   reads a model entity (a trigger) is not an action and stays; nor does the refusal touch the
   model's own ObjectController in the entity's definition (its test, 133).
3. **Seats refuse the exception by name**, citing issue 175: `scensim run` before SSv2 starts
   (beside `check_commands`) and `scensim check`, for any scenario whose model entity has an
   Init `SpeedAction`. No world server or fork change.
4. **A known divergence between the batch and seats.** A scenario with it runs in the batch only,
   so no batch-against-seats agreement check (K10's, K13's check 3) may use one; the agreement
   runner refuses such a scenario by name.
5. **K13 step v's scenario lives with the batch's cases**
   (`src/scensim_sampler/examples/cases/`, beside `k13_platoon_idm.xosc`), not in a seats
   project's `scenarios/`, since seats refuse it. Its search spec stays in
   `scenarios/projects/k13_platoon/searches/`, which takes Town05 for the map.
6. **The equilibrium gap (133).** IDM's equilibrium gap at speed v behind a leader at the same
   speed is s_e = (s0 + vT) / sqrt(1 - (v/v0)^4), not s0 + vT: at v 22 m/s and v0 24.58 m/s the
   free-road term makes it about 1.67 times longer at the set's T. M is placed at s_e from each
   sample's T, s0 and v0, gap measured as the model measures it (its front to the leader's
   rear). Before any judgement, the dry run checks that M's acceleration at t = 0 satisfies
   |a| < 1e-6 m/s^2 in every slot.

**Tests.** The batch starts M at the Init speed (and a model entity with none at rest, as
before); seats (`scensim run`, `scensim check`) refuse a model entity's Init `SpeedAction`,
naming 175; another Init action on M (a linear-shape `SpeedAction`, a relative target, a
ControllerAction) and a Story action on M are refused in the batch; the agreement runner
refuses a scenario that has the exception.

**Before the code: the refusals over every tracked scenario with a model entity** (133;
2026-11-25, a scan of the 113 tracked `.xosc` files, `scan175.py`): 9 have one (the CS1 walker
in `k12_commanded`'s three and four sampler cases, the follower in `platoon_town01.xosc` and
`k13_platoon_idm.xosc`). None has an Init action on its model entity other than a TeleportAction,
so none is newly refused. The two `cs1_walker_dartout*.xosc` cases have a Story SpeedAction on
the model walker, which the batch already refuses today (test_compile, test_subset).

It lands in K13 step v's one gated landing, asking 133 first.
