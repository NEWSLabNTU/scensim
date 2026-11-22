# 107: the scalar ECU component fails on "no command yet"

**Status:** fixed (sim_vehicle_ecu a248958). **Severity:** low: no shipped host passes None
today, but a host that follows the component contract would crash on its first step. **Found:**
2026-11-23, by 139, in 241's review of EvBatch.

## What happens

sim_vehicle_ecu's component contract (`component.py`) says that an `autoware` component's `step`
gets None for the command before the first one arrives. The scalar `EcuComponent.step` passed
the command straight to `Ecu.step`, which reads `request.tire_angle`:

```
>>> Ev(spec).step(None, None, 1 / 60)
AttributeError: 'NoneType' object has no attribute 'tire_angle'
```

EvBatch, the batched form (139), already treats None as `Request()`, the car standing in drive.
So the scalar and the batch disagreed on the contract's first step.

## Fix

`EcuComponent.step` steps `Request()` when the command is None, as EvBatch does. Test:
`test_no_autoware_command_yet_is_the_default_request`, for `Ev` and `Ideal`, with and without
sensors. It fails on the old code with the AttributeError above. sim_vehicle_ecu: 180 passed,
1 skipped (CUDA).
