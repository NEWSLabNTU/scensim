# 151: K11d's draw test loads a torch that does not work with this NumPy, and fails

**Status:** open (241; filed by 133, 2026-11-24). **Severity:** low: a test; `just test` fails on
a host whose user site holds a NumPy the system torch was not built for, on a test of code that
is fine.
**Found:** 2026-11-24, scensim 243, in the gate of issue 149 (59439b38): the only failure;
waived by 133 in 149's landing (8e818935).

## What happens

`test_behaviour.py::test_a_given_draw_is_the_threshold_on_numpy_and_torch_and_the_seed_is_unchanged`
(092 K11d, 2c0c79c3) runs its check on NumPy and on torch, and skips torch on
`(ImportError, ValueError)` from `xp.namespace("torch")`. On 243's host the system torch, built
for NumPy 1, imports a user-site NumPy 2.2.6 and fails with another exception:

```
AttributeError: _ARRAY_API not found
```

(reproduced there with a bare `env -i HOME=$HOME PATH=/usr/bin:/bin python3 -c 'import torch'`).
The test fails instead of skipping. The same file already has the right guard, `usable_torch()`:
it asks a separate interpreter whether torch imports and takes NumPy's arrays, skips on a
missing torch or on the NumPy ABI mismatch (naming it and how to run instead), and fails on any
other torch failure, without loading a torch that failed (a half-initialised torch module can
crash the interpreter). K11d's test did not use it.

Shown on 241 with a stub `torch` package that raises the same error, first on `PYTHONPATH`, with
the built workspace sourced and the user site off: K11d's test fails with
`AttributeError: _ARRAY_API not found`, while the file's other torch test,
`test_numpy_and_torch_agree_bit_for_bit`, skips with the reason.

## Fix

The test is parametrized over `numpy` and `torch`, and its torch case goes through
`usable_torch()` before touching torch, as the file's other torch tests do: the NumPy half always
runs, the torch half skips with the reason where torch does not work with this NumPy, and any
other torch failure still fails. Nothing is caught around the assertions.
