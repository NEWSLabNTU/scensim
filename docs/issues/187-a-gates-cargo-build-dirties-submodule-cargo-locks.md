# 187: a gate's cargo build rewrites submodule Cargo.lock files ([[patch.unused]] entries) and dirties the tree

**Status:** open; root cause found (241, 2026-11-26); the scensim-side cleanup held pending a fix in colcon-cargo-ros2 (133).
**Severity:** low. Nothing that lands is changed, but every gate checkout ends with two dirty
submodules, so a pre-push "clean tree" check fails on files the gate itself wrote.
**Found:** 2026-11-25, scensim 118, landing 1ed265d7; scensim 139 before it (wt-178, wt-179).

## What happens

`just build` in the superproject runs colcon with colcon-cargo-ros2, which writes a
`[patch.crates-io]` block into the workspace's `.cargo/config.toml` (git-ignored, `.gitignore`
line 26), one `path` entry per ROS message crate it generated under `build/`:
`action_msgs`, `builtin_interfaces`, `example_interfaces`, `rcl_interfaces`, `rmw_dds_common`,
`scensim_interfaces`, `test_msgs`, `unique_identifier_msgs`.

Cargo reads every `.cargo/config.toml` from the build's directory up to the root, so the cargo
builds inside the submodules see that block too. Two of them use none of those crates, and cargo
records each patch it did not use in their lock file. After the gate at 1ed265d7
(gate-c5c, 2026-11-25 22:00:58 to 22:18:49, rc 0), `git status` in the superproject showed:

     M src/scensim_carla_world
     M src/scensim_world_protocol

Both were at their pinned commits (676480ec, e63aaea7, shown as `-dirty`). In each, the only
change was `Cargo.lock`: 32 lines appended, eight blocks of this form, one per crate above:

    [[patch.unused]]
    name = "action_msgs"
    version = "0.0.0"

## Effect

- The landing's guarded push checks for a clean tree. Its first attempt stopped there, and
  nothing was pushed; the retry used `git status --porcelain --untracked-files=no
  --ignore-submodules=dirty`, which still catches a moved pin but ignores files changed
  inside a submodule. 133 accepted that as the guard.
- A `git commit -a`, or a `git add` of a submodule, from such a checkout would carry nothing (a
  dirty submodule's commit is unchanged), but the lock files differ from the submodules'
  committed ones until someone resets them.

## Evidence

- 118: gate-c5c after the 1ed265d7 gate, above.
- 139: scensim 139's worktrees wt-178 and wt-179, each after an `env -i` `just build && just
  test`; the diffs were saved before the worktrees were removed, at server139
  `/var/tmp/aeon/p2runs/gate-cargo-lock-unused-patches.diff` (scensim_carla_world) and
  `gate-cargo-lock-unused-patches-protocol.diff` (scensim_world_protocol), with
  `gate-cargo-lock-unused-patches.sha256`.
- The same bytes on both hosts. The sha256 of each submodule's `git diff` of `Cargo.lock`:

      65ba42245693d7da3708641f43970d628c8ff0e4575c1e046fa7cfe2413d3216  scensim_carla_world (118 gate-c5c, 139 wt-178, wt-179)
      ee88984d64a75b342165059e7f69145f0e0223a91d793dcc641edebcb320aeaa  scensim_world_protocol (118 gate-c5c, 139 wt-178, wt-179)

## The fix wanted (a plan before any code)

Options to weigh: build the submodules without the superproject's patches (a cargo config the
submodule builds do not inherit, for example the patches in a config passed only to the
workspace's own cargo calls); or have the submodules commit lock files that already hold the
entries (fragile: they follow the generated crate list); or restore the lock files after the
build. Then the check: a full gate leaves `git status --porcelain` empty with no
`--ignore-submodules`.

## Root cause (241, 2026-11-26)

colcon-cargo-ros2 0.5.4 (`jerry73204/colcon-cargo-ros2`, pinned by `just setup`) writes one
`.cargo/config.toml` per Cargo workspace it finds (`_write_cargo_configs`,
`_detect_cargo_workspace_root`): the superproject's, for its root `[workspace]`, with the eight
message patches, and one in each of `src/scensim_carla_world` and `src/scensim_world_protocol`
with an empty patch block. Cargo merges every `.cargo/config.toml` from the build's directory up
to the filesystem root, so every cargo command inside those two (colcon's build of them, which
is when the locks were written: their mtimes fall inside the gate's `just build`; and `just
test`'s nextest calls) also gets the root's patches. Neither depends on a message crate, so
cargo records each as `[[patch.unused]]`. The tool's per-workspace configs assume each
workspace sees only its own; cargo's hierarchical config breaks that for a nested one.

**Evidence** (the finished 186 gate worktree, d780baf7's build; every file restored after):

| component | `cargo metadata --offline`, root config present | root config moved aside |
|---|---|---|
| `src/scensim_world_protocol` | `Cargo.lock` +32 -0, 8 `[[patch.unused]]` | no change |
| `src/scensim_carla_world` | `Cargo.lock` +32 -0, 8 `[[patch.unused]]` | no change |

`src/autoware_carla_bridge`, which uses the message crates, and `third_party/cuda_ndt_matcher`,
built on its own with no config, stay clean.

## The options, weighed (133 decided, 2026-11-26)

- **(a) `--locked` or `--frozen`:** rejected. `cargo metadata --locked` in a component with the
  root config exits 101 ("patch `action_msgs ...` was not used in the crate graph"): the build
  would fail instead of writing the lock.
- **(b) The components commit the `[[patch.unused]]` blocks:** rejected. Each component's own
  `just build`, with no root config, would strip them again, and the list follows the
  superproject's generated crate set, so each new message package would need a component
  commit and a pin move.
- **(c) A scensim-side cleanup** (strip the unused-patch blocks after each cargo call, only when
  they are the lock's whole change and only for the root's patch names): **held pending (d).**
  It would rewrite tracked submodule files after every build to remove dirt that harms nothing:
  pins are commits, the dirt never reaches one, and the push guard's
  `git status --porcelain --untracked-files=no --ignore-submodules=dirty` already passes it.
  Revisited if the user declines (d).
- **(d) Fix it in colcon-cargo-ros2:** a nested workspace must not inherit an outer workspace's
  patches; for instance the outer patches passed as `--config` on the tool's own cargo calls (a
  bare cargo command and IDEs then lose them), or a manifest-level `[patch.crates-io]` for the
  outer workspace (which does not leak, but is a tracked file). The user's own repository: a
  draft issue (cause, the repro above, the two designs and their costs) went to 133 for the
  user, `~/nas/home/2026-11-26 colcon-cargo-ros2 issue draft (241)/`; nothing posted there.

Meanwhile a landing's clean-tree guard uses `--ignore-submodules=dirty`, which still catches a
moved pin.

