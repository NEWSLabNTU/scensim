"""A P2 or P4 evaluation that raises exits nonzero (scensim issue 118). Each runs under
aib.fake_kit, with stand-ins for Isaac, Isaac Lab, torch and gymnasium, and fails at its first
Isaac Lab call; before the fix the app's atexit close ended it with 0."""
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
FAIL = "isaaclab_tasks.utils.parse_cfg.load_cfg_from_registry"  # each main's first call
FORCED = f"fake_kit: forced failure at {FAIL}"  # aib.fake_kit.forced(FAIL)
FAKED = "isaaclab,isaaclab_rl,isaaclab_tasks,gymnasium,torch,rsl_rl,wheeledlab,wheeledlab_tasks"
# wheeledlab_rl's startup builds the app (Isaac Lab's AppLauncher): the stand-in's
STARTUP = """
def startup(parser):
    from aib.fake_kit import SimulationApp
    return SimulationApp(), parser.parse_args()
"""


def run_fake(script, *args):
    """The script under aib.fake_kit: (exit status, stdout + stderr)."""
    with tempfile.TemporaryDirectory() as d:
        pkg = Path(d) / "wheeledlab_rl"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")
        (pkg / "startup.py").write_text(STARTUP)
        (pkg / "utils.py").write_text("ClipAction = object\n")
        env = dict(os.environ, FAKE_KIT_EXTRA=FAKED, FAKE_KIT_FAIL=FAIL,
                   PYTHONPATH=os.pathsep.join(map(str, [
                       d, AIB, HERE.parent, SRC / "sim_vehicle_ecu", SRC / "sim_vehicle_spec",
                       SRC / "scensim_sampler"])))
        env.pop("DISPLAY", None)
        r = subprocess.run([sys.executable, "-c", RUN, str(SCRIPTS / script), *args], env=env,
                           capture_output=True, text=True, timeout=120, cwd=d)
    return r.returncode, r.stdout + r.stderr


# aib.fake_kit's main runs a module; these are scripts, run by path
RUN = """
import runpy, sys
from aib import fake_kit
fake_kit.install(fake_kit.os.environ["FAKE_KIT_EXTRA"].split(","),
                 fake_kit.os.environ["FAKE_KIT_FAIL"])
sys.argv = sys.argv[1:]
runpy.run_path(sys.argv[0], run_name="__main__")
"""


@unittest.skipUnless(AIB.is_dir(), "aib's checkout (src/autoware_isaac_bridge) is not here")
class EvaluationTest(unittest.TestCase):
    def assert_failed(self, code, output):
        self.assertNotEqual(code, 0, output)
        self.assertIn(FORCED, output)  # its traceback: it failed where it was made to

    def test_eval_drift(self):
        with tempfile.TemporaryDirectory() as out:
            self.assert_failed(*run_fake("eval_drift.py", "--run-path", out, "--out", out))

    def test_eval_leadbrake(self):
        self.assert_failed(*run_fake("eval_leadbrake.py", "--checkpoint", "none.pt"))


if __name__ == "__main__":
    unittest.main()
