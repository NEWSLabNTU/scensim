# 129: a dataset cache edited while a stack runs loads silently

**Status:** fixed (2026-11-24, 243; found in 092 K9's CS3 work, filed by 133). **Severity:**
medium.

## What was wrong

A project's `assets/maps/<map>` is a link into the shared dataset cache
(`~/.cache/scensim/datasets/<repo>/<commit>/`), and the lock (`scensim.lock`) names each file's
sha256. Two gaps let a file that is not the locked one reach a pilot or the world:

- A stack verified the cache only when it started: `stack.plan` runs the project check, whose
  `assets.check` re-hashes every locked file whose stat key (size, mtime, ctime, inode) changed
  and refuses the stack on a mismatch. A stack already running never checked again, so a file
  edited while it ran was loaded at the next map switch or pilot restart, and the run's
  provenance did not say so.
- `testbench check` printed a lock mismatch ("differs from the lock") as a note, not a refusal.

## How it was found

On 2026-11-24, building 092 K9's CS3 map variant, a `cp -r` of `assets/maps/Town01` copied the
link, and the edit that followed went into the cache's Town01 `lanelet2_map.osm`. It was
restored within a minute (every locked file's sha256 again the lock's, the modes read-only
again); no stack ran on the host meanwhile.

## Fix

- `assets.verify_map(project, map)`: the map's locked files against the lock, by stat key, so
  only a changed file is hashed again.
- The keeper checks the maps a switch loads (the world's and the pilots', 092 K9 CS3) before it
  stops any pilot: `switch_problem` refuses the switch by file name (`map Town01 is not the
  locked one: <dataset>: Town01/lanelet2_map.osm differs from the lock (sha256 ...)`), and the
  runner refuses the run with it.
- `testbench check` marks a lock mismatch refused.
- A run that binds a pilot map variant records `maps.lanelet2_sha256` `{world, pilot}`: the
  lock's digest as verified, or the project copy's own when no dataset holds it.

Tests (`scensim/test/test_pilot_maps.py`): an edit in the test's own cache refuses the switch,
starting and stopping no pilot; `testbench check` refuses it; the digests are recorded and
change with the file. `test_assets.py`'s `test_check` now expects the refusal.
