# 191: landing gates are per-peer scripts; one skipped `just check`, and 187, 188 and the 9-oktas change landed without fmt or clippy

**Status:** open. The immediate fix lands with this record (c7a45833, fmt only); the remedy,
a `just gate` recipe every peer uses, is to be planned (133, 2026-11-26).
**Severity:** medium. Main failed `just check` (`cargo +nightly fmt --check`) from 550a8b41 until
the fix. A peer whose own gate runs `just check` (243's K9f-a) was blocked by a file it never
touched.
**Found:** 2026-11-26, scensim 243 (rustfmt 1.9.0-nightly 2026-04-19); reproduced on 133
(nightly 2026-07-07) and 241 (rustfmt 1.10.0-nightly 2026-08-29).

## What happened

Each peer gates a landing with a script of its own. 241's (its scratchpad `i187_gate.sh`, then
copies for each landing) ran, in a fresh worktree with `env -i` and `ISAAC_ROOT`: `just build`,
`just test`, and for 187 a second `just build`, with `git status --porcelain
--untracked-files=no` after each step. It never ran `just check` (`cargo +nightly fmt --check`,
then `cargo clippy --all-targets -- -D warnings`). Landings gated that way:

- 188 (70cbde08 and its records): `justfile` and `scripts/isaac_lane.sh`, no Rust. A check
  would have run on main's Rust unchanged by it.
- 187 (b82fa372, 0bcfad0e and records): the root `Cargo.toml`'s patch block and the
  `_check-colcon-cargo-ros2` recipe; no `.rs`. Clippy did run over the changed manifest's
  graph in no gate.
- The 9-oktas change (550a8b41, gated first as 62148d96 and then as cc9b5a40): a test in
  `src/scenario_world_bridge/src/backend/remote/profiles.rs` with two asserts over rustfmt's
  width. This is the one that broke `just check`: main failed `fmt --check` from 550a8b41
  (2026-11-26 04:25 +08:00 commit time) to the fix.

## The fix

c7a45833: `rustfmt` on that file only. The two asserts are split across lines, nothing else.
241's gate script now runs `just check` after `just test`, with the same status check after it.
The fix's own gate was the first to run it, on 241 at c7a45833 in a fresh worktree with `env -i`
and `ISAAC_ROOT` (2026-11-26, check 06:56:00 to 06:56:11). It passed: build, test ("Isaac-Python
lane: ran (937 tests in 3 suites, OK)"), and `just check`, both `fmt --check` and clippy
`-D warnings`. `git status --porcelain --untracked-files=no` was empty after each step. So
clippy finds nothing more on main. The check prints cargo's own warning that seven of the root
manifest's eight generated message patches are unused in the crate graph (187's
patches-in-manifest). That is a warning, not a clippy finding, and it does not fail.

## The cause, and the remedy to plan

The gate is not in the repository. Every peer writes its own, so what a landing proves depends
on who landed it, and a missed step is invisible to the others. The remedy, to plan before any
code: a `just gate` recipe in the repository that every peer runs to land. It would:

- run in a clean environment, with `ISAAC_ROOT` passed where the host has one;
- run `just build`, `just test` and `just check`;
- show `git status --porcelain --untracked-files=no` (no `--ignore-submodules`) after each
  step, and fail when it is not empty;
- require the Isaac lane's "ran" on a host with Isaac;
- print one summary line naming the commit, so a landing request can quote it.
