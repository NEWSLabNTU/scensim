# 111: land_pin's gate tests a component the landing does not move as the checkout holds it

**Status:** fixed (scripts/land_pin.py `pin_others`). **Severity:** medium: a landing's gate can
test a tree that is not the tip's. A correct landing then fails, or a wrong one could pass.
**Found:** 2026-11-23, scensim 241, in issue 107's landing.

## What happens

Before the gate, `scripts/land_pin.py` puts each landing component at its new commit. It syncs
every component's `deps/` at its gitlinks (issues 094 P2 and 105). A component the landing does
not move is left as this checkout has it: on a local branch, at another commit, or with edits.
The gate builds and tests the whole workspace, that component included.

In issue 107's landing (sim_vehicle_ecu only), `src/sim_vehicle_spec` was on a local branch for
issue 106, at 9ceb8cb. It was not at the tip's 21bf3dc, and its Model 3 had the not-yet-landed
key `powertrain.regen_slip_control`. scensim's `test_the_rig_is_aibs_from_the_spec` read that
spec file, but validated it with the pinned sim_vehicle_spec (aib's deps), and refused it:

```
SpecError: .../vehicles/my_lincoln.yaml: powertrain: unknown key(s) ['regen_slip_control']
```

The landing's commits were right; a fresh clone of the tip passes. Nothing was pushed. With the
roles reversed, local work in a component that the tip needs, but does not pin, would let a
broken landing pass.

## Fix

`pin_others` runs before the gate. Every `src/` component the landing does not move is checked
out at the tip's gitlink, detached, so its branches and their commits are kept. A component with
an uncommitted change (the gate would test that too) refuses the landing by name, before
anything is pushed:

```
a component the landing does not move has uncommitted changes, so the gate cannot test the
tip's tree: commit or stash them; nothing pushed
  src/B: A  f
```

Tests in `scripts/test_land_pin.py`, both failing on the old script; all 32 land_pin tests pass:
- `test_a_component_not_landing_is_at_the_tips_gitlink_for_the_gate`: B on a local commit; the
  gate sees B at the gitlink, and the branch is kept.
- `test_an_uncommitted_change_in_a_component_not_landing_refuses_by_name`.
