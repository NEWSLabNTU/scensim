# 125: the sweep wheel query moves a loose rock far less than raycast

**Status:** open, a record; no work on it yet (133). **Severity:** to be judged when the work
starts. A study config uses sweep: scensim's `scenarios/projects/isaac_verge/testbench.yaml`
sets `isaac.wheel_query: sweep` for the curb onto the walkway (issue 077). aib's rigs default to
raycast. **Found:** 2026-11-23, scensim 118, 086 C6b's fixtures rerun after issue 123.

## What happens

086 C6b's fixtures on fixture_c6b (siw 2ef3001, aib ff5e72b, 60 Hz, the plate and the detail's
colliders on, no base contact by issue 123's self-check), raycast / sweep:

| fixture | moved | largest speed | "moves at least 5 cm" |
|---|---|---|---|
| loose_15 (13.2 kg, 15 cm), 40 km/h | 1.67 m / 2.5 cm | 5.5 / 1.3 m/s | passes / fails |
| loose_8 (2.0 kg, 8 cm), 40 km/h | 1.1 cm / 5.0 cm | 0.44 / 1.1 m/s | fails / fails |

In raycast the rear wheel threw loose_15 0.73 m on and 1.5 m aside, the order of 066 R4's slice
(0.2 to 0.5 m on, 0.9 to 1.0 m aside). In sweep it moved 2.5 cm. The check has no physical
source (issue 122), so this is a difference between the two queries, not a judged failure of
sweep.

Caveat: loose_15 run alone in raycast moved 6.6 cm (issue 123's trace hypothesis' result), so a
single raycast run does not fix its outcome. Whether the queries differ consistently needs
repeated runs, not yet made.

NAS: "2026-11-23 086 C6b rock fixtures after issue 123 (118)".
