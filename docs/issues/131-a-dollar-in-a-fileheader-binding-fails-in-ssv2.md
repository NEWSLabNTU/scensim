# 131: a `$` parameter in a FileHeader binding fails in SSv2

**Status:** fixed (2026-11-24, 243; found in 092 K9's CS3 runs, the syntax chosen by 133).
**Severity:** high.

## What was wrong

scensim's bindings live in a scenario's FileHeader `Properties`: `scensim.knob.<knob>`
(093 D2), a knob profile's breakpoints and `scensim.anchor.<parameter>` (092 K9), and
`scensim.pilot_map` (092 K9, CS3). Each named a scenario parameter as `$<name>`. OpenSCENARIO
evaluates a FileHeader property before the scenario's `ParameterDeclarations` are in scope, so
such a file fails in any OpenSCENARIO tool; SSv2's preprocessor refused it:

```
The preprocessor refused .../cs3_stale_map.xosc: No such variable named "pm" of type Expression
```

D2's knob binding was marked implemented on main, but it had never run on seats with a `$`
parameter: the only `$` bindings were the sampler's examples (CS5's profile, CS6, walker_dartout),
which ran in the sampler and the batch only. Seats projects that use `$` (isaac_soil,
isaac_verge) put it in entity properties, which SSv2 evaluates in scope. So every knob, profile,
anchor-with-a-parameter and pilot-map binding by `$` would have failed on seats as an error run.

## How it was found

092 K9's CS3 runs (2026-11-24): `scensim.pilot_map = $pm` gave two SSv2 error runs before the
ego moved, after the stack had switched the pilots to the variant correctly.

## Fix (133's choice: a syntax no OpenSCENARIO tool substitutes)

- A binding names a parameter as `param:<name>`: `param:surface`, `time: 0 1000; 12
  param:fog_end`, `exit_n.lanelet_at(param:cyclist_s)`, `param:pm`
  (`scensim_sampler.bindings`; scenario-description.md section 3). The file SSv2 runs is the
  file the run records: no rewrite.
- A `$` in any `scensim.*` FileHeader property is refused by name, with the form to write
  (`... write 'param:pm'`), by the sampler (`Scenario`), so by `testbench check` and by `scensim
  run` before any run: a check-time refusal, not an SSv2 error run.
- Migrated: CS5's profile, CS6, walker_dartout, k9_cs3. Messages and `result.json` `anchors`
  show the written form.
- Tests: `scensim_sampler/test/test_bindings.py` (each kind resolves from `param:`, a `$` in
  each is refused with its form, other properties untouched); `test_pilot_maps.py` (a `$`
  binding refused by resolve, `scensim run` and `testbench check`); the binding tests of the
  sampler, knobs and anchors moved to `param:`.
