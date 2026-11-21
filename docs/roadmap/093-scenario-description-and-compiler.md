# Phase 093: Scenario description and the scenario-to-world compiler (design exploration)

Explore how a scenario is described for vehicle risk studies, and how the compiler turns
that description into a world on each target, through worked case studies. This phase
produces designs and specification drafts, not product code. Phase 092's specifications (S1
the sample record, S2 the compilable subset) and components (K1 the sampler, K2 the Isaac Lab
adapter, K3 replay) are built from what this phase settles.

**Status**: started 2026-11-20 (user: "Have a phase on the design exploration of the scenario
to world compiler. Explore the scenario description design on risk and case studies"). **Closed 2026-11-21 as a design phase** (133's review): D1, D4, D5
and D6 done; D2 done for knobs; D3 left a draft; D7 re-checked. What remains to be built moved
to 092: K8 (the rules of gaps 2 and 4 to 7), K9 (D2's anchors, profiles and pilot map
variants), K10 (D3's behaviour models), K11 (D4's search).

**Source**: phase 092's design and its two studies,
[survey-risk-categories.md](../design/survey-risk-categories.md) and
[survey-vehicle-risk-taxonomy.md](../design/survey-vehicle-risk-taxonomy.md). Decisions
already made by the user:

- scenario and world are separate, joined by the compiler (option A);
- the purposes are a realistic risk rate (A) and failure-mode search (B);
- the realistic base is fitted from public highway and intersection datasets;
- scensim provides components and specifications, not a framework.

**Design**: [scenario-description.md](../design/scenario-description.md).

## Questions

1. **Expressiveness.** What must a scenario say to describe a risk case, encounter-relative
   and realistic, for each of the eight risk families? How much of it does OpenSCENARIO 1.3
   already carry, and what needs an extension point (`UserDefinedDistribution`,
   `UserDefinedAction`, `ObjectController` properties)?
2. **The world interface.** Which anchors (lanes, regions, conflict points) and knobs
   (surfaces, weather, map variant, props) does a world expose, and how does a scenario bind
   to them by name?
3. **Behaviour models.** How does a scenario name a behaviour model for another road user,
   and where does it run on each target: a batched model in Isaac Lab, an SSv2 controller, or
   a pilot on seats?
4. **Sampling in the description.** How does a scenario name its joint base, constraints,
   proposal (importance sampling) and search strategy, and what lands in the sample record?
5. **Compilation.** For each case study: what compiles to an Isaac Lab batch, what only runs
   on seats, and why. This becomes the S2 draft.
6. **Coverage.** How do category ids and cells attach to a scenario, so the coverage report
   can count them?

## Method

Write case studies across the risk families, each in four parts:

1. the functional description;
2. the logical scenario (OpenSCENARIO with its distribution);
3. a sample record;
4. the compiled form on each target, with the gaps found.

Then generalise the cross-cutting designs from them.

## Work items

| Item | What | Owner | Status |
|---|---|---|---|
| D1 | Case studies: a walker dart-out from occlusion (R2), the lead car braking in a curve on a wet road (R1 × R5 × R4), a stale map (R3), a sensor dropout during a cut-in (R6 × R1), weather onset mid-run (R8 × R4) | 133 | done: CS1 to CS5 in scenario-description.md section 2, each with its example in `src/scensim_sampler/examples/cases/` (`cs1_*` to `cs5_*`). Checked 2026-11-21 with `scensim-sample compilable` on main 1b9673fd: CS1 to CS5 compile with the ego as the batch's policy, each with its stated conditions; `cs1_walker_dartout_ttc` is refused on its TimeToCollisionCondition, which is that variant's purpose (the derived-distance rule, CS1) |
| D2 | The world interface: anchors and knobs, their declaration in a world, binding by name, the check | 133 | knobs done, anchors not. Done on main: the binding (`scensim.knob.<knob> = $<parameter>`, the sampler and `scensim.knobs`), the value applied before the run and read back into `result.json` `knobs`, a mismatch an error run, an undeclared knob or value and a knob the target cannot apply refused by name, cells computed from bound knobs. The knobs are declared under `world.knobs` in testbench.yaml, a subset of section 3's `world.yaml`. Remains: anchors (lanes, regions, conflict points, curves) and their check, anchor attributes in derived values (gap 7), knob profiles (`profile: true`, CS5), the pilot's map variants (`maps.pilot_variants`, CS3) |
| D3 | Behaviour models: naming, parameters, and where each runs per target | 133 | still a draft (section 4). The naming is read: the checker recognises an ObjectController `model` (CS1's `scensim.behaviour:gap_acceptance_walker`) and conditions the batch on its batched form. Not built: a behaviour model as a per-entity pilot on seats, any batched model, the starter models; open question 1 (the relay's latency for a walker's reaction) unmeasured |
| D4 | Sampling in the description: base, constraints, proposal, search; the sample record's fields (feeds 092 S1) | 133 | done through 092 S1 and K1 (sample-record.md, `scensim-sample draw`): the base with its header and hash, constraints with the rejection count, a proposal with weights, knobs the constraints read. Remains: the search (purpose B), whose record field `search` is reserved and written null; latent variables (gap 2) |
| D5 | The compilable subset, drafted from the case studies (feeds 092 S2) | 133 | done through 092 S2 (compilable-subset.md, `scensim-sample compilable`; section 6 is superseded), including gap 8 (SSv2's unimplemented constructs refused by name). Remains: the checker rules of gaps 4 to 6 (below) |
| D6 | Coverage tagging: category ids and cells in the scenario | 133 | done through 092 K7 (`scensim.category`, `scensim.cell_attributes`, computed cells, `scensim-sample coverage`, `scensim runs coverage`); a derived cell attribute that reads a latent value is refused. 092 K7 keeps its open item (the weighted interval under heavy weights) |
| D7 | Review: the drafts checked against two more case studies not used to write them | swb 243 | re-checked 2026-11-21 (below): every gap has a written rule, and CS6 and CS7 compile; 5 of the 7 proposed rules are not implemented, so both still carry workarounds. First pass: gaps found; exit not met (2026-11-21): CS6 (a cut-out reveals a stopped car, R1) and CS7 (a cyclist overtaken at an intersection exit under low sun, R2 × R4), scenario-description.md section 2a, `src/scensim_sampler/examples/cases/cs6_*`, `cs7_*`. Gaps: (1) sampled knobs did not reach the world (rule: sections 3 and 7, 139 builds it); (2) latent variables; (3) optional entities; (4) a static vehicle; (5) isBlind; (6) a per-sample entity class; (7) anchor geometry in derived values; each with a proposed rule in 2a; (8) the description needed a construct SSv2 does not implement (LaneOffsetAction; S2's checker now refuses the unimplemented, and CS7 swerves by a lane change); (9) small points |

### D7's exit, re-checked (2026-11-21, main 1b9673fd)

`scensim-sample compilable` on both scenarios and their distribution files:

- CS6 compiles with the ego as the batch's policy, conditional on a slot camera
  (`illumination`, bound to the world's knob) and a batched form of SSv2's default traffic
  behaviour.
- CS7 compiles with the ego as the batch's policy, conditional on that default behaviour, a
  slot camera (`TimeOfDay`, `Sun`), and RoadCondition, which scensim_batch does not run yet
  (092 K2.3).

Neither needs a construct outside the drafts: each of the nine gaps has a rule in section 2a.
The rules' state on main:

| Gap | Rule | On main | What CS6 or CS7 does instead |
|---|---|---|---|
| 1 | knobs bound by `scensim.knob.<name>`, applied and read back; cells computed | implemented | CS6 binds `illumination` |
| 2 | `latent: true` on a model variable | implemented after the re-check (092 K8, swb 243): recorded under the record's `latent` | CS6's `time_headway` and `reveal_time` are latent; the scenario no longer declares them |
| 3 | `scensim.present` on an optional entity | not implemented | not needed by CS6 or CS7 |
| 4 | `scensim.static` on a stopped vehicle | implemented after the re-check (092 K8, swb 243), with SSv2's `maxSpeed = 0`; executor pending in the batch | CS6's stopped car is static; its Init SpeedAction of 0 and its default-behaviour condition are gone |
| 5 | `isBlind` in the subset, with lane following alone as the condition | not implemented: the checker gives the whole default traffic behaviour as the condition | CS6's lead is blind; its condition is the wider one |
| 6 | a parameter in an entity's category or model conditional on per-slot assets | implemented after the re-check (092 K8, swb 243): the checker names the parameter and its values as a condition | CS6's stopped car: `$stopped_kind` (car, truck, motorbike) is now a condition |
| 7 | anchor attributes in derived values (`anchor.<name>.<attribute>`) | not implemented: no anchors on main (D2) | CS7 declares `exit_heading`, a constant, as the exit lane's heading |
| 8 | SSv2's unimplemented constructs refused by name | implemented (092 S2) | CS7 swerves by a lane change |
| 9 | small points | fixed or covered by the rules above | |

So the exit holds as a design statement and not yet in the tools. Gap 6 mattered most before a
batch run, since the checker said nothing where a condition was due; it was implemented first.

## Exit

The design note covers D1 to D6. 092's S1 and S2 can be written from it without new design
questions. D7's two fresh case studies are expressible with no construct the drafts lack.

Assessed 2026-11-21 (243; reviewed by 133):

- **met:** S1 and S2 were written from the note and are done in 092, and D7's re-check finds no
  construct missing from the drafts;
- **not met:** D3 is a first draft, and D2's anchors are a design only.

Closed as a design phase, D3 left a draft (133's review, 2026-11-21). What remains to be built
is in 092:

- K8: the rules of gaps 2 and 4 to 7;
- K9: D2's anchors, profiles and map variants;
- K10: D3's per-entity pilot and batched models;
- K11: D4's search.

Once each rule lands, its workaround comes out of CS6 and CS7.
