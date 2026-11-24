# 162: a golden hash of the road's heights holds on one host only

**Status:** fixed: scensim_isaac_world ba33b82 (the hash removed, `NoProfilePath` in its place).
**Severity:** low: a test that failed on a correct tree, no physics or result affected. **Found:**
2026-11-25, scensim 241, at 092 K13's landing gate (numbered by 133).

## What happened

086 C6c1 added `test_course_c6c.Unchanged` (scensim_isaac_world 8429497, landed with 30eb19a): the
sha256 of a corridor's heights on a grid (every road-detail feature but C6c's new `profiles`),
computed at 7813843, before C6c, and checked against each later tree, so that C6c could not move
an existing road. It was computed on 118 (numpy 1.21.5) and skipped on any other numpy, on the
belief that the roughness's FFT is the only thing that rounds differently.

On 241's host (numpy 1.21.5, reference BLAS, a CPU with AVX2 and no AVX512) the same test gave
another hash, `091eacd80f5eebea5c84647ef6ff5e18304841d8bd7a5e0ba1b5063677c380c3`, at 7813843,
8429497, 30eb19a and 31adacc alike (241's evidence: `~/nas/autoveh/logs/k13-gate/gate-53a15bf9.log`).
7813843 is the code before C6c, so the heights had not changed: the hash differs by host. The
likely cause, not traced to an operation: the roughness field is built by FFT and array
arithmetic that BLAS and the CPU's vector width round differently, so the same numpy version on
two hosts gives heights equal to rounding, not to the byte.

**092 K13 landed at 73575ba9 with this test waived** (133's call, at K13's gate on 241); K13's
commit messages do not say so, and 241 adds a line to 092.

## The fix

The test is removed (scensim_isaac_world ba33b82, on 1ca5f50). Its purpose, that a corridor
without `profiles` is the road it was before C6c, is held by `test_course_c6c.NoProfilePath`
(b2d4917): such a corridor's tiles are built with `road_detail.Profile.h` and
`iso8608_profile` patched to raise, so the profile code cannot have run, on any host; and a
control shows the patch would catch it with a profile present. Equality of heights across hosts
is not a property the code has, and no test claims it.

The lesson for golden values: a hash of floating-point output is the host's, not the code's.
Compare such output by a tolerance, or test the code path instead.
