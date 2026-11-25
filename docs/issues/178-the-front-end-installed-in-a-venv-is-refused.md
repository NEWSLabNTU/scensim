# 178: the front end installed in a virtual environment is refused

**Status:** fixed in code and tests 2026-11-25 (fix by coop 118; reviewed, extended and landed
by 139; numbered by 133). **Severity:** medium. Ubuntu 24.04's documented install form leaves
four of the front end's commands refused, so a release cannot be set up or extended that way.
**Found:** 2026-11-25, coop 118, moving a downstream testbench to the 0.2.1 release with the
front end in a venv (so that it shadows no other checkout's `scensim`).

## What happens

`docs/getting-started/install.md` gives two forms for Ubuntu 24.04, whose system Python refuses
`pip install` outside a virtual environment (PEP 668). The second is

```bash
python3 -m venv --system-site-packages ~/.venvs/scensim
source ~/.venvs/scensim/bin/activate
pip install scensim
```

A release's `setup.bash` then puts the release's own `bin/scensim` first on PATH. That entry is
`scensim.cli` on the system Python (`#!/usr/bin/python3`). It passes the front end's commands
(`install`, `setup`, `autoware-side`, `carla`, `--version`, `-V`) to the front end by importing
`scensim_frontend.cli`, and the system Python cannot import a package installed in the venv. So
it answered, for example,

```
scensim autoware-side: refused: the pip front end is not installed (fix: pip install scensim, then scensim autoware-side)
```

although the front end was installed, and its own `scensim` was on PATH after the release's.
`pip install --user` (the first form) is not affected: the system Python imports from the user
site.

## Repro (coop 118, 0.2.1)

1. Install the front end in a venv as above, then `scensim install` a 0.2.1 release.
2. In a new shell: `source ~/.venvs/scensim/bin/activate`, then the release's `setup.bash`.
3. `scensim autoware-side build`: refused as above. `scensim --version` printed only the
   release's own version, not the front end's.

## Fix

`scensim.cli._front_end` still tries the import first. When it fails, it walks PATH for an
executable `scensim` whose shebang names another Python, checks that Python can import
`scensim_frontend.cli`, and runs `python -m scensim_frontend <command> ...` in it
(`scensim_frontend/__main__.py` calls its `main()`, which reads `sys.argv`). Interpreters are
compared by their own path, not the resolved one: a venv's `python3` is a link to the system's
and is known by where the link lives. A `#!/usr/bin/env python3` shebang (pipx, hand-written
scripts) is followed to the Python `env` would pick on the same PATH; options and `VAR=value`
words are skipped.

Tests: `src/scensim/test/test_testbenches.py`,
`test_a_front_end_in_a_virtual_environment_is_found_on_path` and
`test_an_env_shebang_names_the_python_env_would_pick`.

Coop 118 checked the fix live against 0.2.1 (the fixed `cli.py` first on PYTHONPATH):
`scensim autoware-side build` and `scensim --version` reached the venv's front end. 139 has not
repeated the live check.

## Known limits

- `env -S` splitting is not followed: `#!/usr/bin/env -S python3 -u` is read as `python3`.
- Each failed import costs one `python -c "import scensim_frontend.cli"` per distinct Python
  found on PATH, once per command.
