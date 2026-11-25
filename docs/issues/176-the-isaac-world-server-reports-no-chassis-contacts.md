# 176: the Isaac world server reports no chassis contacts

**Status:** open; plan first, after 086 C6e3 (133, 2026-11-25). **Severity:** to be shown. No
judged check rests on a contact today. **Found:** 2026-11-25, scensim 118, while writing 086
C6e3's details (numbered by 133).

## What happens

086 C6e3's spec, as 133 amended it, records each rock's contact with the chassis (the skid
plate's and the body's) "in the world server's log". The world server logs none.
`scensim_isaac_world` has no contact report for the ego's chassis, and aib logs none either
(read 2026-11-25 at scensim main 0291abb3). C6b's plate strikes came from
`scensim_isaac_world.course.fixture_drive`, a scripted drive with its own contact report, which
a scenario run (`scensim run`, the world server) does not use.

## For C6e3 (133's decision, before any run)

No code before C6e3. A rock's contact is inferred from the truth trace: where it passed (between
the wheels or under one, from the trace and the rock's place) and the body's height and pitch at
the rock against the 10 m before it. Every row and the verdict say "inferred, not measured", and
no judged check rests on one. A rock between the wheels taller than the clearance is recorded
as "a strike likely, not measured".

## The fix (to plan)

A contact report in the world server for the ego's chassis prims (the skid plate and the body),
logged per contact with the time, the other prim and the impulse, and a run attachment that
counts them. Plan first, written before any code, after C6e3.
