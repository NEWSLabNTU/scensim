# 179: a GPU test fails where torch lacks the device's arch

**Status:** fixed in tests 2026-11-25 (139; numbered by 133). **Severity:** low. No code
under test is wrong, but `just test` fails on a host whose GPU is newer than its torch build. It
stops at the first such failure, so the suites after it never run there.
**Found:** 2026-11-25, scensim 139, gating issue 178 on main 0291abb3 on server139 (RTX 5090).

## What happens

`src/scensim/test/test_follower.py::test_torch_on_a_gpu_agrees_with_numpy` skipped only when
`torch.cuda.is_available()` was false. On server139 the gate's environment (`env -i`, user
site on) imports `~/.local`'s torch 2.0.0+cu117, whose arch list is sm_37 to sm_86. The card is
an RTX 5090, compute capability 12.0 (sm_120). `is_available()` is true there, since the driver
sees the card, but torch has no kernel for it, so the first tensor operation on the device
raised

```
RuntimeError: CUDA error: no kernel image is available for execution on the device
```

in `follower.py`. Main 0291abb3 fails it the same way. The test that should have been skipped
failed, and `just test` stopped there.

The same pattern (a device in use as soon as `is_available()` is true) was in
`scenarios/projects/roboracer/component/roboracer_vesc/test/test_torch.py`, which adds
`"cuda"` to its devices on that check alone. `src/scensim_batch/test/test_device.py` already
probed the device with a real kernel, so it skipped correctly, but its reason ("no torch 2 with a
usable GPU") did not say why.

## Fix

A GPU test now asks whether torch can run on the device before using it. The checks run in
order:

- No device: skip, "no CUDA device".
- Device without a kernel: skip naming both sides. The device's arch is read from
  `torch.cuda.get_device_capability(0)` and checked against `torch.cuda.get_arch_list()`.
  Kernels count when torch has the device's own `sm_XY`, or an `sm_X*` of the same major with
  a lower or equal minor (cubins run on later minors), or a `compute_*` PTX at or below the
  device's capability (the driver compiles it for the device). Without these the test skips
  with, for example,

  ```
  torch 2.0.0+cu117 has no kernel for NVIDIA GeForce RTX 5090 (sm_120); its arch list: sm_37 sm_50 sm_60 sm_70 sm_75 sm_80 sm_86
  ```

- Empty arch list (a CPU-only build) or no `get_arch_list`: the test runs, as before.

Applied to every GPU test with that skip pattern:

- `test_follower.py`: the check, `cuda_unusable(torch)`, lives beside `usable_torch` in
  `test_behaviour.py`, with tests on fake torch modules.
- roboracer's `test_torch.py`: its `cuda` case is always listed and skips with the reason.
  Before, it was silently absent without a device.
- `test_device.py`: the same check before its kernel probe, so its skip says why.

The torch in `~/.local` is the user's environment and is left as it is. A torch with sm_120
kernels would run these tests on this host.

## Not changed

The gate for issue 178 ran `just test` with `CUDA_VISIBLE_DEVICES` empty (waiver in d7b5eeb6's
message). With this fix that waiver is not needed.
