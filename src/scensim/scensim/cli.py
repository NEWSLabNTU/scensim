"""``scensim <command> ...``: one entry for every scensim command (roadmap 081 step 3).
``scensim run ...`` is ``scensim run ...``; 082's front end puts ``scensim`` on PATH."""
import importlib
import os
import subprocess
import sys

# command: (module, its entry, what it does), in the order `scensim --help` lists them
COMMANDS = {
    "run": ("scensim.run", "cli", "run a testbench, a suite or a scenario"),
    "runs": ("scensim.runs", "main", "list, show and explain past runs"),
    "stack": ("scensim.stack_cli", "main", "start, stop or list a testbench's stack"),
    "testbench": ("scensim.testbench_cli", "main", "new, list and check testbenches"),
    "assets": ("scensim.assets", "main", "fetch and check maps and datasets"),
    "seat": ("scensim.seat", "main", "this host's seats: ports and domains"),
    "project": ("scensim.project", "main", "new and check a project directory (the form before testbenches)"),
    "drive": ("scensim.drive", "main", "drive a car by hand"),
    "isaac": ("scensim.isaac", "main", "Isaac Sim on this host"),
    "autoware": ("scensim.autoware", "main", "Autoware's carried fixes and runtime"),
}


# the pip front end's own commands (082): after a release's setup.bash, this entry is first on
# PATH and the front end's `scensim` is shadowed, so these are passed to it when it is
# installed, and answered here (a source build, or a release without it) when it is not
FRONT_END = ("install", "setup", "autoware-side", "carla", "--version", "-V")
FRONT_END_MODULE = "scensim_frontend.cli"


def _front_end():
    """The pip front end's ``main(argv) -> int``, or None when it is not installed.

    It is found in this Python first (``pip install --user``), then on PATH: a front end
    installed in a virtual environment (Ubuntu 24.04's form, install.md) runs on that
    environment's Python, which this entry's (the system's, ``#!/usr/bin/python3``) cannot
    import, and a release's setup.bash puts this entry before it on PATH."""
    try:
        return importlib.import_module(FRONT_END_MODULE).main
    except ImportError:
        return _front_end_on_path()


def _shebang_python(path: str):
    """The interpreter a ``scensim`` script on PATH names, when it is a Python, else None."""
    try:
        with open(path, "rb") as f:
            line = f.readline(512).decode("utf-8", "replace").strip()
    except OSError:
        return None
    if not line.startswith("#!"):
        return None
    words = line[2:].split()
    if not words or "python" not in os.path.basename(words[0]):
        return None
    return words[0]


def _can_import_front_end(python: str) -> bool:
    return subprocess.call([python, "-c", f"import {FRONT_END_MODULE}"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0


def _front_end_on_path():
    """A front end installed for another Python, found by its ``scensim`` script on PATH, as a
    ``main(argv) -> int`` that runs it in that Python; None when there is none."""
    # not realpath: a venv's python is a link to the system's, and the venv is known by the
    # link's own place (its pyvenv.cfg beside it), so resolving it would skip the venv
    own = os.path.abspath(sys.executable)
    seen = set()
    for d in os.environ.get("PATH", "").split(os.pathsep):
        path = os.path.join(d or ".", "scensim")
        if not (os.path.isfile(path) and os.access(path, os.X_OK)):
            continue
        python = _shebang_python(path)
        if python is None or os.path.abspath(python) in seen | {own}:
            continue
        seen.add(os.path.abspath(python))
        if _can_import_front_end(python):
            return lambda argv: subprocess.call([python, "-m", "scensim_frontend"] + list(argv))
    return None


def own_version() -> str:
    """``--version`` without the front end: a release's version (its scensim-release.yaml), or
    a source build's package version and commit, and where it is."""
    from scensim import testbench as tbmod
    b = tbmod.built_over()
    prefix = b.get("prefix")
    from pathlib import Path
    release = bool(prefix) and (Path(prefix) / tbmod.RELEASE_FILE).is_file()
    what = "release" if release else "source build"
    return f"scensim {b.get('scensim') or '?'} ({what}{f' at {prefix}' if prefix else ''})"


def front_end_command(cmd: str, rest: list) -> int:
    fn = _front_end()
    if fn is not None:
        return fn([cmd] + rest)
    if cmd in ("--version", "-V"):
        print(own_version())
        return 0
    from scensim import testbench as tbmod
    from pathlib import Path
    prefix = tbmod.built_over().get("prefix")
    if prefix and (Path(prefix) / tbmod.RELEASE_FILE).is_file():
        sys.stderr.write(f"scensim {cmd}: refused: the pip front end is not installed "
                         f"(fix: pip install scensim, then scensim {cmd})\n")
    else:
        hint = ("set it up with `just setup`" if cmd in ("setup", "autoware-side", "carla")
                else "update it with git and colcon (git pull --rebase, then colcon build)")
        sys.stderr.write(f"scensim {cmd}: refused: this scensim is a source build; {hint}\n")
    return 3


def usage() -> str:
    return ("usage: scensim <command> [args...]\n\ncommands:\n"
            + "".join(f"  {c:10} {d}\n" for c, (_, _, d) in COMMANDS.items())
            + "\n`scensim <command> --help` for each; `scensim --version`; `scensim install` "
              "(the pip front end's)\n")


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help"):
        sys.stdout.write(usage())
        return 0
    cmd, rest = argv[0], argv[1:]
    if cmd in FRONT_END:
        return front_end_command(cmd, rest)
    if cmd not in COMMANDS:
        sys.stderr.write(f"scensim: no command {cmd}\n{usage()}")
        return 3
    mod, entry, _ = COMMANDS[cmd]
    fn = getattr(importlib.import_module(mod), entry)
    # every entry reads sys.argv when given no argv: give it this command's own
    sys.argv = [f"scensim {cmd}"] + rest
    return fn(rest)


if __name__ == "__main__":
    sys.exit(main())
