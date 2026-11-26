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

## The plan: `just gate` (241, 2026-11-26; before any code)

**Goal.** One recipe in the repository that every peer runs to land a change. It proves the same
thing whoever runs it, and it prints one line a landing request can quote.

**Shape.** `just gate [commit:=HEAD] [dir:=]`. It runs from a checkout, against one commit:

1. *The commit.* The 40-character SHA from `git rev-parse <commit>^{commit}` and its tree
   (refused if the commit isn't known locally).
2. *A fresh worktree.* `git worktree add --detach <dir> <sha>`. The default dir is
   `$SCENSIM_GATE_ROOT/gate-<sha8>` (a host setting, `/var/tmp/$USER` by default). It is refused
   if the path exists: a gate never reuses a tree. Then `git submodule update --init
   --recursive`. Check that HEAD is the SHA and the tree matches.
3. *A clean environment* for every step: `env -i` with HOME, USER, TERM and a fixed PATH
   (`~/.cargo/bin`, `~/.local/bin`, `/usr/local/bin`, `/usr/bin`, `/bin`), plus `ISAAC_ROOT`
   when the host sets it (CLAUDE.md's `clean=` line).
4. *The steps, in order:* `just build`, `just test`, `just check`. After each,
   `git status --porcelain --untracked-files=no` (no `--ignore-submodules`) must be empty, or
   the gate fails naming the step and the paths.
5. *The Isaac lane.* On a host with `ISAAC_ROOT`, `just test`'s last line must say
   "Isaac-Python lane: ran"; "skipped" fails the gate there (issue 186). On a host without it,
   the summary says "Isaac lane: not on this host".
6. *A summary line* on stdout and in `<dir>/gate.txt`, for example:
   `gate ok <sha> tree <tree8> on <host> <iso time>: build test check clean;
   Isaac lane ran (937 tests)`. On failure, `gate FAILED <sha> at <step>: <reason>`.
7. *The log.* Every step's output goes to `<dir>/gate.log`. The worktree is kept until the
   landing (the record names it), and a later `just gate-clean <sha>` removes it after the same
   checks as today's (HEAD on origin, nothing tracked changed).

**Not in it:** pushing, tags, the pre-push pin check (`check_pins` runs inside `just test`
already), and docs-only moves (they keep the check_docs plus check_pins rule).

**Where.** The recipe plus `scripts/gate.sh` (bash, `set -euo pipefail`; a guarded `cd`
before any git in the worktree), and a short section in the contributor docs naming it as the
landing gate. CLAUDE.md is not edited without the user.

**Tests.** A `test_gate` over a tiny fixture repository, with no real build: `just` replaced by
a stub that passes or fails per step and can dirty a file. It checks:
- a dirty tree after any step fails;
- "skipped" with `ISAAC_ROOT` set fails;
- an existing dir is refused;
- the summary line's format.

**Predictions.**
- On 241, `just gate commit:=<the change>` at the landing of this recipe passes. It prints
  "gate ok" with the Isaac lane run, in about the time of today's scripts (35 to 45 min).
- Run on 550a8b41 (the 9-oktas code before the fmt fix), it fails at `check` naming
  profiles.rs.
- The stub tests pass in `just test`.

## `just gate`: the outcome against the plan's predictions (241, 2026-11-26)

The recipe is c34124da. 7ede1183 streams each step into `gate.log` as it runs; the first
version wrote a step's output only when the step ended, found in its own first gate. Gated on
241 by itself, with `ISAAC_ROOT` and `SCENSIM_GATE_ROOT=/var/tmp/aeon`:

- c34124da: `gate ok c34124da585fb408a0f2c7d49351b7ba550f6569 tree bab981de on
  newslab-server-241 2026-11-26T07:37:19+08:00: build test check clean; Isaac lane ran (937
  tests); colcon-cargo-ros2 0.5.5; rustfmt 1.10.0-nightly (fd7ed57dfd 2026-08-29)`, 34 min.
- 7ede1183: `gate ok 7ede1183b41899e7046e226e2d6c758feaf80a34 tree d0310436 on
  newslab-server-241 2026-11-26T08:14:02+08:00: build test check clean; Isaac lane ran (937
  tests); colcon-cargo-ros2 0.5.5; rustfmt 1.10.0-nightly (fd7ed57dfd 2026-08-29)`, 35 min.

Run on 550a8b41 (the 9-oktas code before the fmt fix): `gate FAILED
550a8b414b8aafc56eb3f808b58cdd9d430e5c41 at check: \`just check\` exited non-zero (last line:
error: recipe \`check\` failed with exit code 1)`. Build and test passed with clean trees. Its
`gate.log` names `Diff in .../profiles.rs:521` right after `== check`.

**Against the predictions:**
- Both gates passed, in the predicted 35 to 45 min, with the Isaac lane run: held.
- 550a8b41 fails at check: held. The plan also predicted the failure would name `profiles.rs`.
  It does so in `gate.log`, not in the summary line, which quotes the recipe's last line
  instead: a miss. A summary naming the first `Diff in` or `error` line of the failing step is
  a small follow-up.
- The stub tests (7) pass in `just test`: held.

## The follow-up: the summary quotes the failing step's first error (241, 2026-11-26)

On rebasing onto a6d8b2a4 (243's K9f-a), a failed step's reason keeps its last line and adds
the step's first rustfmt `Diff in` or compiler `error` line (`error:` or `error[E...]:`), the
worktree's path cut off, when it differs from the last line. A stub test covers it (8 tests).

**Predictions, before the runs:**
- `just gate` on this commit passes on 241 in 35 to 45 min, with the Isaac lane run; 243's
  K9f-a adds tests, so the lane's count may be above 937.
- `GATE_STEPS=check` on 550a8b41 fails at check, its summary line ending `first: Diff in
  src/scenario_world_bridge/src/backend/remote/profiles.rs:521:)`.

**The follow-up's outcome:**
- `just gate` on b8defc88: `gate ok b8defc88429a4bd80207e9edf21ddbcd0bbae177 tree 556b19d8 on
  newslab-server-241 2026-11-26T10:47:31+08:00: build test check clean; Isaac lane ran (942
  tests); colcon-cargo-ros2 0.5.5; rustfmt 1.10.0-nightly (fd7ed57dfd 2026-08-29)`, 42 min.
  Held. The lane counts 942 tests with K9f-a's.
- `GATE_STEPS=check` on 550a8b41: a miss in the setup, not the code. `just check` sources
  `install/setup.bash`, which only `just build` makes, so it failed on that line before
  rustfmt ran. Run as `GATE_STEPS="build check"`: `gate FAILED
  550a8b414b8aafc56eb3f808b58cdd9d430e5c41 at check: \`just check\` exited non-zero (last
  line: error: recipe \`check\` failed with exit code 1; first: Diff in
  src/scenario_world_bridge/src/backend/remote/profiles.rs:521:)`. Held: the summary line
  now names the file.

## The second follow-up: `gate-clean` after a rebase (241, 2026-11-26)

Landing 969c5f27 needed a rebase after its gate, so the gated SHAs (c34124da, 7ede1183,
b8defc88) were on no origin branch, and `gate-clean` refused them, as written. 133 asked that
it also accept a gate whose every commit is patch-equivalent on origin/main (`git cherry`, all
`-`). In that case it first sets the local tag `gate/<worktree name>` on the gated SHA and
prints it, because the issue's record cites that SHA. The three were tagged by hand the same
way: `gate/gate-c34124da`, `gate/gate-7ede1183`, `gate/gate-b8defc88`. The recipe now runs
`scripts/gate_clean.sh`, and `scripts/test_gate.py` covers it with 4 tests on a bare origin:
landed as is, landed rebased (tagged), not landed (kept), and tracked changes (kept).

**Predictions, before the gate:**
- `just gate` on this commit passes on 241 with the Isaac lane run (942 tests, or more if
  main moved), in 35 to 45 min.
- The 12 tests of `scripts/test_gate.py` pass within `just test`.

## The third follow-up: the host's settings reach the gate (241, 2026-11-26)

118 could not use `just gate`. Its steps ran under `env -i` with only HOME, USER, TERM, PATH
and ISAAC_ROOT, and a fresh worktree has no `.env` (it is gitignored). So the host settings
CLAUDE.md puts in `.env` (SCENSIM_BUILD_JOBS, the ports, AUTOWARE_TENSORRT_LIB, ...) never
reached the build, and neither did the caller's MAKEFLAGS or CARGO_BUILD_JOBS. Now:
- the calling checkout's `.env` is copied into the worktree, where just's dotenv-load reads
  it;
- of an allow-list (ISAAC_ROOT, SCENSIM_BUILD_JOBS, MAKEFLAGS, CARGO_BUILD_JOBS,
  CUDA_VISIBLE_DEVICES), those the caller sets are passed;
- `GATE_WRAP=<command>` runs every step under that command;
- the gate's line ends `carried <.env and keys>[; under <GATE_WRAP>]`.

Two stub tests cover it. With the second follow-up it lands through one gate, rebased onto
issue 189's step 3.

**Predictions, before the gate:**
- `just gate` on this commit passes on 241, with the Isaac lane run (942 on 241, whose Isaac
  venv lacks pytest; issue 186's note).
- Run from 241's landing worktree, which has no `.env`, with only ISAAC_ROOT of the
  allow-list set, its line ends `carried ISAAC_ROOT`.
- The 14 tests of `scripts/test_gate.py` pass within `just test`.
