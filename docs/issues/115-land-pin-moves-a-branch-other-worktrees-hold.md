# 115: land_pin moves the land-pin branch under other worktrees

**Status:** fixed (scripts/land_pin.py: the pins committed on a detached HEAD;
`checked_out_elsewhere`). **Severity:** medium: a worktree is left on a branch that moved under
it, its old files staged against the new commit, so a commit there would revert everything
between. **Found:** 2026-11-23, scensim 118, after 086 C5d's landing.

## What happened

`scripts/land_pin.py` made its pin commit after `git checkout -q -B land-pin <base>`, in the
checkout it was run from. A repository's worktrees share their branches, and git 2.34 (118's)
does not refuse `checkout -B` of a branch another worktree has checked out. So every landing
moved `refs/heads/land-pin` in every worktree that had it checked out, without touching their
files or indexes. Such a worktree then showed its old tree staged as changes against the new
commit.

On 118 two worktrees of one repository held land-pin:

- `w10c`, since 086 C5b's landing was run from it (2026-11-23 06:33). The landings of C5c
  (10:14) and C5d (11:59), run from another worktree, moved its branch to f98f1cd1. Its index
  was still 61ad6d58's: 10 files staged as the inverse of C5c and C5d.
- `landrev/scensim` (the repository's main worktree), on land-pin since 2026-11-20 18:44
  (59f9dc7e). Every landing since, from other worktrees, moved its branch: 436 files staged.

Neither held work of its own: each index was its old HEAD's tree exactly (`git diff --cached
<old HEAD>` empty), and w10c's only other changes were build-written Cargo.lock files in two
components. A commit in either would have reverted main by the staged inverse.

The same pattern was in the cascade: a component's `git checkout -B main origin/main` in its
checkout moves `main` under any other worktree of that component's repository (on 118, the
siw worktrees `siw-c5a`/`siw-c5b`/`siw-c5c` are worktrees of w10c's
`src/scensim_isaac_world`).

## Repair (2026-11-23, local only)

Each worktree detached at its old HEAD, `git checkout --detach 61ad6d58` (w10c) and `59f9dc7e`
(landrev/scensim): `git diff --cached` empty after, w10c's Cargo.lock edits still unstaged. The
land-pin ref itself was left where it was.

## The fix

- This repository's pin commit is made on a detached HEAD (`git checkout --detach <base>`): no
  branch is created or moved, so no other worktree can be moved by it. Nothing in the landing
  named the branch: the pushes push the built SHAs.
- A cascading component's main is still reset to origin/main (the landing's bookkeeping reads
  `main` there), but the landing refuses, naming the worktree, when another worktree of that
  component's repository has main checked out (`checked_out_elsewhere`, by the worktrees' git
  directories: `git worktree list` names a submodule's main worktree by its git directory under
  the superproject's `.git/modules`, not by its checkout).
- Tests (scripts/test_land_pin.py): a worktree on land-pin keeps its branch and a clean index
  through a landing, which ends on a detached HEAD at origin/main; a component whose main another
  worktree holds refuses the landing, nothing pushed.

133 asked for a per-run branch name deleted at the end with a refusal when it is checked out;
a detached HEAD needs no branch at all, so there is nothing to refuse or delete. Other hosts
(139, 241, 243) were asked by 133 to check their worktrees before their next landing:
`git worktree list` showing `[land-pin]` on more than one line is this issue.
