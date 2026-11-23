"""scensim_batch's Isaac scripts exit nonzero when they raise (scensim issue 118).

Each runs under aib.fake_kit, with stand-ins for Isaac, Isaac Lab, WheeledLab, torch and
gymnasium, and fails just after its app starts (its first torch import, or its first Isaac Lab
call); before the fix the app's atexit close ended it with 0. And every script that starts an
app guards it and runs its main through aib.app_exit, read from the source: agreement_run's
checks before its app need a recorded run, so the scan is its test."""
import ast
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE.parents[1]
AIB = SRC / "autoware_isaac_bridge" / "src" / "aib"
SCRIPTS = HERE.parent / "scripts"
EGO = AIB / "config" / "ego.yaml"
FAKED = ("isaaclab,isaaclab_rl,isaaclab_tasks,gymnasium,torch,rsl_rl,wheeledlab,wheeledlab_rl,"
         "wheeledlab_tasks,wheeledlab_assets")
TORCH = "import:torch"
FIRST_CALL = "isaaclab_tasks.utils.parse_cfg.load_cfg_from_registry"
WORLD = "fake_kit: forced failure building the World"  # aib.fake_kit.FORCED
# a stand-in for the training script the train wrappers run: its app, then torch
TRAIN_LAB = "from isaaclab.app import AppLauncher\napp = AppLauncher().app\nimport torch\n"
TRAIN_WL = ("import argparse\nfrom wheeledlab_rl.startup import startup\n"
            "app, args = startup(parser=argparse.ArgumentParser())\nimport torch\n")


def forced(target):
    return f"fake_kit: forced failure at {target}"  # aib.fake_kit.forced


# aib.fake_kit's main runs a module; these are scripts, run by path
RUN = """
import os, runpy, sys
from aib import fake_kit
fake_kit.install(os.environ["FAKE_KIT_EXTRA"].split(","), os.environ.get("FAKE_KIT_FAIL", ""))
sys.argv = sys.argv[1:]
runpy.run_path(sys.argv[0], run_name="__main__")
"""


def run_fake(script, *args, fail=TORCH):
    """The script under aib.fake_kit: (exit status, stdout + stderr)."""
    with tempfile.TemporaryDirectory() as d:
        env = dict(os.environ, FAKE_KIT_EXTRA=FAKED, FAKE_KIT_FAIL=fail,
                   PYTHONPATH=os.pathsep.join(map(str, [
                       AIB, HERE.parent, SRC / "sim_vehicle_ecu", SRC / "sim_vehicle_spec",
                       SRC / "scensim_sampler"])))
        env.pop("DISPLAY", None)
        args = [a.replace("{tmp}", d) for a in args]
        for name, text in (("train_lab.py", TRAIN_LAB), ("train_wl.py", TRAIN_WL)):
            Path(d, name).write_text(text)
        r = subprocess.run([sys.executable, "-c", RUN, str(SCRIPTS / script), *args], env=env,
                           capture_output=True, text=True, timeout=120, cwd=d)
    return r.returncode, r.stdout + r.stderr


# script, its arguments, where it is made to fail, and the message that says it failed there
CASES = {
    "eval_drift.py": (["--run-path", "{tmp}", "--out", "{tmp}"], FIRST_CALL),
    "eval_leadbrake.py": (["--checkpoint", "none.pt"], FIRST_CALL),
    "check_resident.py": (["--n", "1"], TORCH),
    "check_engine_a_layout.py": (["--samples", "none.json"], TORCH),
    "smoke_articulation.py": (["--body", "none.yaml"], TORCH),
    "smoke_drift.py": (["--spec", "x", "--asset-root", "x", "--dist", "x"], TORCH),
    "smoke_env.py": (["--ego", "x", "--vehicle", "x"], TORCH),
    "smoke_physx_vehicle.py": (["--ego", str(EGO)], ""),
    "train_leadbrake.py": (["{tmp}/train_lab.py"], TORCH),
    "train_drift.py": (["{tmp}/train_wl.py"], TORCH),
}
# starts an app, read from the source
APP_CALLS = ("AppLauncher", "SimulationApp", "startup")


@unittest.skipUnless(AIB.is_dir(), "aib's checkout (src/autoware_isaac_bridge) is not here")
class ScriptTest(unittest.TestCase):
    def test_each_script_that_raises_exits_nonzero(self):
        for script, (args, fail) in CASES.items():
            with self.subTest(script=script):
                code, output = run_fake(script, *args, fail=fail)
                self.assertNotEqual(code, 0, output)
                # its traceback: it failed where it was made to, after its app
                self.assertIn(forced(fail) if fail else WORLD, output)


class SourceTest(unittest.TestCase):
    def test_every_app_is_guarded_and_every_main_run(self):
        missing = []
        for path in sorted(SCRIPTS.glob("*.py")):
            tree = ast.parse(path.read_text())
            names = {n.func.attr if isinstance(n.func, ast.Attribute) else getattr(n.func, "id", "")
                     for n in ast.walk(tree) if isinstance(n, ast.Call)}
            calls = {f"{n.func.value.id}.{n.func.attr}" for n in ast.walk(tree)
                     if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                     and isinstance(n.func.value, ast.Name)}
            if not names & set(APP_CALLS):
                continue
            for need in ("app_exit.guard", "app_exit.run"):
                if need not in calls:
                    missing.append(f"{path.name}: no {need}")
        self.assertEqual(missing, [])

    def test_every_script_that_starts_an_app_is_run_above(self):
        starts = {p.name for p in SCRIPTS.glob("*.py")
                  if any(f"{c}(" in p.read_text() for c in APP_CALLS)}
        self.assertEqual(starts - set(CASES), {"agreement_run.py"})


if __name__ == "__main__":
    unittest.main()
